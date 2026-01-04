import os
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path
import shutil
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from database import Database, get_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ecitko Image Upload API")

UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/srv/ecitko/uploads')
ALLOWED_EXTENSIONS = {'jpeg', 'jpg', 'png'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
CHUNK_SIZE = 1024 * 1024  # 1MB per chunk


# Pydantic model za notify_upload request
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


async def verify_token(authorization: str = Header(None)):
    """
    Verify API token from Authorization header.
    
    Expected format: Bearer <token>
    Token is compared against API_TOKEN environment variable.
    """
    if not authorization:
        logger.warning("Authentication failed: Authorization header missing")
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("Authentication failed: Invalid authorization header format")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = parts[1]
    expected_token = os.getenv("API_TOKEN", "")
    
    if not expected_token:
        logger.error("API_TOKEN environment variable is not set")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error"
        )
    
    if token != expected_token:
        logger.warning("Authentication failed: Invalid token")
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )
    
    logger.info("Authentication successful")
    return token


@app.post("/upload")
async def upload_image(
    waterMeterId: int = Form(...),
    file: UploadFile = File(...),
    db: Database = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Upload an image for a water meter.
    
    Args:
        waterMeterId: The ID of the water meter
        file: The image file to upload (JPEG, JPG, or PNG)
        db: Database dependency
        token: API token for authentication
    
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
    unique_id = str(uuid.uuid4())[:16]
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
                    raise HTTPException(
                        status_code=400,
                        detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
                    )
                
                f.write(chunk)
    except HTTPException as e:
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
    """
    Health check endpoint - proverava da li sistem radi
    """
    checks = {
        "api": "ok",
        "database": "unknown",
        "uploads_directory": "unknown",
        "disk_space": "unknown"
    }
    
    status = "healthy"
    
    # Check database connection
    try:
        db.connect()
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = f"error: {str(e)}"
        status = "unhealthy"
    
    # Check uploads directory
    upload_path = Path(UPLOAD_DIR)
    if upload_path.exists() and upload_path.is_dir():
        checks["uploads_directory"] = "ok"
    else:
        checks["uploads_directory"] = "error: directory not found"
        status = "unhealthy"
    
    # Check disk space
    try:
        disk_usage = shutil.disk_usage(UPLOAD_DIR)
        available_gb = disk_usage.free / (1024 ** 3)
        total_gb = disk_usage.total / (1024 ** 3)
        used_gb = disk_usage.used / (1024 ** 3)
        
        if available_gb < 1:
            checks["disk_space"] = "warning: low disk space"
            status = "unhealthy"
        else:
            checks["disk_space"] = "ok"
        
        return JSONResponse(
            status_code=200 if status == "healthy" else 503,
            content={
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "checks": checks,
                "disk_usage_gb": round(used_gb, 2),
                "disk_available_gb": round(available_gb, 2),
                "disk_total_gb": round(total_gb, 2)
            }
        )
    except Exception as e:
        logger.error(f"Disk space check failed: {e}")
        checks["disk_space"] = f"error: {str(e)}"
        status = "unhealthy"
    
    return JSONResponse(
        status_code=200 if status == "healthy" else 503,
        content={
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "checks": checks
        }
    )


@app.get("/metrics")
async def get_metrics(db: Database = Depends(get_database)):
    """
    Metrics endpoint - vraća statistiku sistema
    """
    try:
        # Get total counts
        total_images = db.get_total_images_count()
        total_water_meters = db.get_total_water_meters_count()
        total_consumers = db.get_total_consumers_count()
        
        # Get images by water meter
        images_by_meter = db.get_images_by_water_meter()
        
        # Calculate disk usage
        disk_usage_bytes = 0
        upload_path = Path(UPLOAD_DIR)
        if upload_path.exists():
            for file_path in upload_path.glob("*"):
                if file_path.is_file():
                    disk_usage_bytes += file_path.stat().st_size
        
        disk_usage_mb = disk_usage_bytes / (1024 ** 2)
        
        return JSONResponse(
            status_code=200,
            content={
                "total_images": total_images,
                "total_water_meters": total_water_meters,
                "total_consumers": total_consumers,
                "images_by_water_meter": images_by_meter,
                "disk_usage_mb": round(disk_usage_mb, 2),
                "uploads_directory": UPLOAD_DIR,
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Metrics endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


@app.post("/notify_upload")
async def notify_upload(
    request: NotifyUploadRequest,
    db: Database = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Notify upload endpoint - potvrda da je slika upload-ovana
    """
    try:
        # Get image from database
        image = db.get_image_by_id(request.image_id)
        
        if not image:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {request.image_id} not found"
            )
        
        # Validate water_meter_id matches
        if image['water_meter_id'] != request.water_meter_id:
            raise HTTPException(
                status_code=400,
                detail=f"Water meter ID {request.water_meter_id} does not match image record"
            )
        
        # Check if file exists on disk
        file_path = Path(image['image_url'])
        file_exists = file_path.exists() and file_path.is_file()
        
        # Log notification
        logger.info(
            f"Upload notification received: image_id={request.image_id}, "
            f"water_meter_id={request.water_meter_id}, status={request.status}, "
            f"file_exists={file_exists}"
        )
        
        # Update processed flag if status is "processed"
        if request.status == "processed":
            db.update_image_processed(request.image_id, processed=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Upload notification received",
                "image_id": request.image_id,
                "water_meter_id": request.water_meter_id,
                "verified": True,
                "file_exists": file_exists,
                "timestamp": datetime.now().isoformat()
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notify upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process notification: {str(e)}"
        )
