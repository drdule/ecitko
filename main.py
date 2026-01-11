import os
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path
import shutil
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from database import Database, get_database
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from celery import Celery

# Celery configuration
celery_app = Celery(
    'ecitko_worker',  # <-- ISTO IME KAO U worker.  py
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()
# Rate limiter - max 100 requests per minute per IP
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI(
    title="Ecitko Image Upload API",
    version="1.2.0",
    description="API for uploading water meter images with Bearer token authentication and rate limiting"
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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


def is_allowed_file(filename:  str) -> bool:
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


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify API token from Authorization header.
    
    Expected format: Bearer <token>
    Token is compared against API_TOKEN environment variable.
    """
    token = credentials.credentials
    expected_token = os.getenv("API_TOKEN", "")
    
    if not expected_token:
        logger.error("API_TOKEN environment variable is not set")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error"
        )
    
    if token != expected_token: 
        logger.warning(f"Authentication failed: Invalid token")
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )
    
    logger.info("Authentication successful")
    return token


@app.post("/upload")
@limiter.limit("20/minute")
async def upload_image(
    request: Request,
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
        logger.warning(f"Invalid file type rejected: {sanitized_filename} from IP={get_remote_address(request)}")
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
                    logger.warning(f"File too large:  {file_size} bytes from IP={get_remote_address(request)}")
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
    
    # Log upload attempt
    logger.info(
        f"Upload attempt:  IP={get_remote_address(request)}, "
        f"waterMeterId={waterMeterId}, filename={sanitized_filename}, "
        f"size={file_size} bytes"
    )
    
    # Insert record into database
    image_url = str(file_path)
    try:
        image_id = db.insert_image(waterMeterId, image_url)
        
        logger.info(
            f"Upload successful: image_id={image_id}, "
            f"file={sanitized_filename}, size={file_size} bytes"
        )
        
        # Send OCR task to Celery queue
        task = celery_app.send_task(
            'ecitko_worker.ocr_task',
            args=[image_id],
            queue='celery'
        )
        
        logger.info(f"OCR task queued: task_id={task.id}, image_id={image_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "message":  "Image uploaded successfully",
                "image_id":  image_id,
                "image_url": image_url,
                "ocr_task_id": task.id,
                "ocr_status": "queued"
            }
        )
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail="Failed to save image record to database"
        )


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Ecitko Image Upload API"}


@app.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request, db: Database = Depends(get_database)):
    """
    Health check endpoint - proverava da li sistem radi
    """
    checks = {
        "api":  "ok",
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
@limiter.limit("30/minute")
async def get_metrics(request: Request, db: Database = Depends(get_database)):
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


@app.get("/rate-limit-status")
@limiter.limit("10/minute")
async def rate_limit_status(request: Request):
    """
    Check rate limit status for current IP
    """
    client_ip = get_remote_address(request)
    
    return JSONResponse(
        status_code=200,
        content={
            "message": "Rate limit information",
            "your_ip": client_ip,
            "limits": {
                "upload": "20 requests per minute",
                "health": "60 requests per minute",
                "metrics": "30 requests per minute",
                "notify_upload": "50 requests per minute",
                "default": "100 requests per minute"
            },
            "note": "Limits are per IP address",
            "timestamp": datetime.now().isoformat()
        }
    )
@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    Proveri status Celery task-a
    """
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id, app=celery_app)
    
    if task_result.state == 'PENDING':
        return {
            "task_id": task_id,
            "status":  "pending",
            "message": "Task is waiting in queue or being processed"
        }
    
    elif task_result.state == 'SUCCESS':
        result = task_result.result
        return {
            "task_id": task_id,
            "status": "success",
            "result": result
        }
    
    elif task_result.state == 'FAILURE':
        return {
            "task_id": task_id,
            "status": "failure",
            "error": str(task_result.info)
        }
    
    else: 
        return {
            "task_id": task_id,
            "status": task_result.state.lower()
        }