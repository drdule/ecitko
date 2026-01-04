import os
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Header
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


class NotifyUploadRequest(BaseModel):
    """Request model for notify_upload endpoint"""
    image_id: int
    water_meter_id: int
    status: str


async def verify_token(authorization: Optional[str] = Header(None)):
    """
    Verify API token from Authorization header.
    
    Expected format: Authorization: Bearer <token>
    
    Args:
        authorization: Authorization header value
        
    Returns:
        str: The validated token
        
    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = parts[1]
    expected_token = os.getenv("API_TOKEN", "")
    
    if not expected_token:
        logger.error("API_TOKEN not configured in environment variables")
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured"
        )
    
    if token != expected_token:
        logger.warning(f"Invalid token attempt: {token[:10]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )
    
    return token


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
    db: Database = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Upload an image for a water meter.
    
    Requires authentication via Bearer token in Authorization header.
    
    Args:
        waterMeterId: The ID of the water meter
        file: The image file to upload (JPEG, JPG, or PNG)
        db: Database dependency
        token: Validated API token (from Authorization header)
    
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


@app.post("/notify_upload")
async def notify_upload(
    request: NotifyUploadRequest,
    db: Database = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Notify upload endpoint - potvrda da je slika upload-ovana.
    
    Requires authentication via Bearer token in Authorization header.
    
    Args:
        request: Notification request data
        db: Database dependency
        token: Validated API token (from Authorization header)
    
    Returns:
        JSON response with verification status
    """
    # Verify that the image exists in database
    try:
        if not db.connection or not db.connection.is_connected():
            db.connect()
        
        cursor = db.connection.cursor(dictionary=True)
        try:
            query = """
                SELECT i.id, i.water_meter_id, i.image_url, i.created_at
                FROM images i
                WHERE i.id = %s AND i.water_meter_id = %s
            """
            cursor.execute(query, (request.image_id, request.water_meter_id))
            image_record = cursor.fetchone()
        finally:
            cursor.close()
        
        if not image_record:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {request.image_id} not found for water meter {request.water_meter_id}"
            )
        
        # Check if file exists on disk
        image_path = Path(image_record['image_url'])
        file_exists = image_path.exists()
        
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
        logger.error(f"Error processing notify_upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while processing notification"
        )


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Ecitko Image Upload API"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics(db: Database = Depends(get_database)):
    """
    Metrics endpoint - provides system statistics.
    
    Public endpoint - no authentication required.
    
    Args:
        db: Database dependency
        
    Returns:
        JSON response with system metrics
    """
    try:
        if not db.connection or not db.connection.is_connected():
            db.connect()
        
        cursor = db.connection.cursor(dictionary=True)
        try:
            # Get total images count
            cursor.execute("SELECT COUNT(*) as total FROM images")
            total_images = cursor.fetchone()['total']
            
            # Get images count by water meter
            cursor.execute("""
                SELECT water_meter_id, COUNT(*) as count
                FROM images
                GROUP BY water_meter_id
            """)
            images_by_meter = cursor.fetchall()
            
            # Get total water meters count
            cursor.execute("SELECT COUNT(*) as total FROM water_meters WHERE is_active = 1")
            total_meters = cursor.fetchone()['total']
            
            return JSONResponse(
                status_code=200,
                content={
                    "total_images": total_images,
                    "total_active_meters": total_meters,
                    "images_by_meter": images_by_meter,
                    "upload_directory": UPLOAD_DIR,
                    "max_file_size_mb": MAX_FILE_SIZE / (1024 * 1024),
                    "allowed_formats": list(ALLOWED_EXTENSIONS)
                }
            )
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while retrieving metrics"
        )
