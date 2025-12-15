import os
import re
import uuid
import imghdr
import logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from database import Database, get_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ecitko Image Upload API")

UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/srv/ecitko/uploads')
ALLOWED_EXTENSIONS = {'jpeg', 'jpg', 'png'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
CHUNK_SIZE = 1024 * 1024  # 1MB per chunk


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
    image_type = imghdr.what(None, h=file_content[:32])
    return image_type in ['jpeg', 'png']


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
    
    # Read file contents
    try:
        contents = await file.read()
    except Exception as e:
        logger.error(f"Failed to read file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while processing upload"
        )
    
    # Validate file size
    file_size = len(contents)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )
    
    # Validate actual image content
    if not validate_image_content(contents):
        raise HTTPException(
            status_code=400,
            detail="File content is not a valid image"
        )
    
    # Create upload directory if it doesn't exist
    upload_path = Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp and UUID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]  # Short UUID
    extension = get_file_extension(sanitized_filename)
    new_filename = f"{waterMeterId}_{timestamp}_{unique_id}.{extension}"
    file_path = upload_path / new_filename
    
    # Save file to disk using chunks
    try:
        with open(file_path, "wb") as f:
            # Write contents in chunks
            offset = 0
            while offset < len(contents):
                chunk = contents[offset:offset + CHUNK_SIZE]
                f.write(chunk)
                offset += CHUNK_SIZE
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while processing upload"
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
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
