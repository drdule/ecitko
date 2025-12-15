import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from database import Database, get_database

app = FastAPI(title="Ecitko Image Upload API")

UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/srv/ecitko/uploads')
ALLOWED_EXTENSIONS = {'jpeg', 'jpg', 'png'}


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename"""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def is_allowed_file(filename: str) -> bool:
    """Check if file has an allowed extension"""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


@app.post("/upload")
async def upload_image(
    consumerId: int = Form(...),
    file: UploadFile = File(...),
    db: Database = Depends(get_database)
):
    """
    Upload an image for a consumer.
    
    Args:
        consumerId: The ID of the consumer
        file: The image file to upload (JPEG, JPG, or PNG)
        db: Database dependency
    
    Returns:
        JSON response with message, image_id, and image_url
    """
    
    # Validate file format
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Allowed formats: {', '.join(ALLOWED_EXTENSIONS).upper()}"
        )
    
    # Validate consumer exists
    if not db.consumer_exists(consumerId):
        raise HTTPException(
            status_code=404,
            detail=f"Consumer with ID {consumerId} not found"
        )
    
    # Create upload directory if it doesn't exist
    upload_path = Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{consumerId}_{timestamp}_{file.filename}"
    file_path = upload_path / new_filename
    
    # Save file to disk
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Insert record into database
    image_url = str(file_path)
    try:
        image_id = db.insert_image(consumerId, image_url)
        if image_id is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to insert image record into database"
            )
    except Exception as e:
        # Clean up file if database insert fails
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
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
