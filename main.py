import os
import re
import uuid
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database import Database, get_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ecitko Image Upload API")

UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/srv/ecitko/uploads')
ALLOWED_EXTENSIONS = {'jpeg', 'jpg', 'png'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
CHUNK_SIZE = 1024 * 1024  # 1MB per chunk


# Pydantic models
class NotifyUploadRequest(BaseModel):
    image_id: int
    water_meter_id: int
    status: str = "uploaded"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and special characters"""
    # Remove path components
    filename = os.path.basename(filename)
    # Remove special characters except dots, underscores, hyphens
    filename = re.sub(r'[^\w\s.-]', '', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    return filename


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename"""
    if '.' not in filename:
        return ''
    parts = filename.rsplit('.', 1)
    return parts[1].lower() if len(parts) == 2 and parts[1] else ''


def is_allowed_file(filename: str) -> bool:
    """Check if file has an allowed extension"""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


def validate_image_content(file_content: bytes) -> bool:
    """Validate image content using magic bytes"""
    if len(file_content) < 12:
        return False
    
    # Check for JPEG magic bytes (FF D8 FF)
    if file_content[0:3] == b'\xff\xd8\xff':
        return True
    
    # Check for PNG magic bytes (89 50 4E 47 0D 0A 1A 0A)
    if file_content[0:8] == b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a':
        return True
    
    return False


@app.post("/upload")
async def upload_image(
    waterMeterId: int = Form(...),
    file: UploadFile = File(...),
    db: Database = Depends(get_database)
):
    """
    Upload an image for a water meter.
    
    Args:
        waterMeterId: The ID of the water meter
        file: The image file to upload (JPEG, JPG, or PNG)
        db: Database dependency
    
    Returns:
        JSON response with message, image_id, and image_url
    """
    
    # Validate filename exists and is not empty
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing or empty")
    
    # Sanitize filename
    sanitized_filename = sanitize_filename(file.filename)
    
    # Validate file format by extension
    if not is_allowed_file(sanitized_filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Allowed formats: {', '.join(ALLOWED_EXTENSIONS).upper()}"
        )
    
    # Validate water meter exists and is active
    if not db.water_meter_exists(waterMeterId):
        raise HTTPException(
            status_code=404,
            detail=f"Water meter with ID {waterMeterId} not found or inactive"
        )
    
    # Create upload directory if it doesn't exist
    upload_path = Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp and UUID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:16]  # Use 16 characters for better uniqueness
    extension = get_file_extension(sanitized_filename)
    new_filename = f"{waterMeterId}_{timestamp}_{unique_id}.{extension}"
    file_path = upload_path / new_filename
    
    # Save file to disk using chunks and validate simultaneously
    file_size = 0
    first_chunk = None
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                # Store first chunk for validation
                if first_chunk is None:
                    first_chunk = chunk
                
                # Check file size
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    # File will be cleaned up after with block
                    raise HTTPException(
                        status_code=400,
                        detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
                    )
                
                f.write(chunk)
    except HTTPException as e:
        # Clean up partial file on validation errors
        if file_path.exists():
            file_path.unlink()
        raise
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while processing upload"
        )
    
    # Validate actual image content using first chunk
    if not first_chunk or not validate_image_content(first_chunk):
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=400,
            detail="File content is not a valid image"
        )
    
    # Insert record into database
    image_url = str(file_path)
    try:
        image_id = db.insert_image(waterMeterId, image_url)
    except Exception as e:
        # Clean up file if database insert fails
        logger.error(f"Database error for water_meter_id {waterMeterId}: {str(e)}")
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while processing upload"
        )
    
    return JSONResponse(
        status_code=200,
        content={
            "message": "Image uploaded successfully",
            "image_id": image_id,
            "image_url": image_url
        }
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Ecitko Image Upload API"}


@app.get("/health")
async def health_check(db: Database = Depends(get_database)):
    """Health check endpoint - checks API, database, uploads directory, and disk space"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    checks = {}
    overall_status = "healthy"
    
    # Check API status (if we reached here, API is running)
    checks["api"] = "ok"
    
    # Check database connection
    try:
        if db.check_database_connection():
            checks["database"] = "ok"
        else:
            checks["database"] = "error: connection failed"
            overall_status = "unhealthy"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        overall_status = "unhealthy"
    
    # Check uploads directory exists
    upload_path = Path(UPLOAD_DIR)
    if upload_path.exists() and upload_path.is_dir():
        checks["uploads_directory"] = "ok"
    else:
        checks["uploads_directory"] = "error: directory not found"
        overall_status = "unhealthy"
    
    # Check disk space
    disk_usage_gb = 0.0
    disk_available_gb = 0.0
    try:
        stat = shutil.disk_usage(UPLOAD_DIR if upload_path.exists() else "/")
        disk_usage_gb = round((stat.total - stat.free) / (1024**3), 2)
        disk_available_gb = round(stat.free / (1024**3), 2)
        
        # Warn if less than 1GB available
        if disk_available_gb < 1.0:
            checks["disk_space"] = "warning: low disk space"
            overall_status = "unhealthy"
        else:
            checks["disk_space"] = "ok"
    except Exception as e:
        checks["disk_space"] = f"error: {str(e)}"
        overall_status = "unhealthy"
    
    response_data = {
        "status": overall_status,
        "timestamp": timestamp,
        "checks": checks,
        "disk_usage_gb": disk_usage_gb,
        "disk_available_gb": disk_available_gb
    }
    
    # Return 503 if unhealthy, otherwise 200
    status_code = 503 if overall_status == "unhealthy" else 200
    return JSONResponse(status_code=status_code, content=response_data)


@app.get("/metrics")
async def get_metrics(db: Database = Depends(get_database)):
    """Metrics endpoint - returns statistics about images, water meters, and consumers"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    try:
        # Get counts from database
        total_images = db.get_total_images_count()
        total_water_meters = db.get_total_water_meters_count()
        total_consumers = db.get_total_consumers_count()
        images_by_water_meter = db.get_images_by_water_meter()
        
        # Get all active water meters and ensure they're in the images_by_water_meter dict
        # This ensures water meters with 0 images are shown
        all_water_meters_dict = {}
        cursor = db.connection.cursor()
        try:
            cursor.execute("SELECT id FROM water_meters WHERE is_active = 1")
            for (meter_id,) in cursor.fetchall():
                all_water_meters_dict[str(meter_id)] = images_by_water_meter.get(str(meter_id), 0)
        finally:
            cursor.close()
        
        # Calculate disk usage for uploads directory
        disk_usage_mb = 0.0
        upload_path = Path(UPLOAD_DIR)
        if upload_path.exists() and upload_path.is_dir():
            total_size = 0
            for file_path in upload_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            disk_usage_mb = round(total_size / (1024**2), 2)
        
        response_data = {
            "total_images": total_images,
            "total_water_meters": total_water_meters,
            "total_consumers": total_consumers,
            "images_by_water_meter": all_water_meters_dict,
            "disk_usage_mb": disk_usage_mb,
            "uploads_directory": UPLOAD_DIR,
            "timestamp": timestamp
        }
        
        return JSONResponse(status_code=200, content=response_data)
        
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred while getting metrics")


@app.post("/notify_upload")
async def notify_upload(request: NotifyUploadRequest, db: Database = Depends(get_database)):
    """Notify endpoint for upload completion - validates and logs upload notifications"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    try:
        # Validate that image_id exists
        image = db.get_image_by_id(request.image_id)
        if not image:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {request.image_id} not found"
            )
        
        # Validate that water_meter_id matches the image
        if image['water_meter_id'] != request.water_meter_id:
            raise HTTPException(
                status_code=400,
                detail=f"Water meter ID {request.water_meter_id} does not match image record (expected {image['water_meter_id']})"
            )
        
        # Check if image file exists on disk
        image_path = Path(image['image_url'])
        file_exists = image_path.exists() and image_path.is_file()
        
        # Log the notification
        logger.info(
            f"Upload notification received - "
            f"image_id: {request.image_id}, "
            f"water_meter_id: {request.water_meter_id}, "
            f"status: {request.status}, "
            f"file_exists: {file_exists}, "
            f"image_url: {image['image_url']}"
        )
        
        # Update processed status if status is "processed"
        if request.status == "processed":
            db.update_image_processed(request.image_id, True)
            logger.info(f"Updated image {request.image_id} processed status to True")
        
        response_data = {
            "message": "Upload notification received",
            "image_id": request.image_id,
            "water_meter_id": request.water_meter_id,
            "verified": True,
            "file_exists": file_exists,
            "timestamp": timestamp
        }
        
        return JSONResponse(status_code=200, content=response_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing upload notification: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while processing notification"
        )
