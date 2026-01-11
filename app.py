# ... početak fajla ostaje isti ...

@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    waterMeterId: int = Form(... ),
    current_user: dict = Depends(verify_token)
):
    # ... postojeći kod ...
    
    return {
        "message": "Image uploaded successfully",
        "image_id": image_id,
        "image_url": image_path,
        "ocr_task_id": task.id,
        "ocr_status": "queued"
    }


@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    Proveri status Celery task-a
    
    Args:
        task_id: ID task-a koji je vraćen sa /upload endpoint-a
        
    Returns:
        dict: Status task-a (pending, success, failure)
    """
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id, app=celery_app)
    
    if task_result.state == 'PENDING': 
        # Task još čeka u queue-u ili se izvršava
        return {
            "task_id":  task_id,
            "status": "pending",
            "message": "Task is waiting in queue or being processed"
        }
    
    elif task_result.state == 'SUCCESS':
        # Task je uspešno izvršen
        result = task_result. result
        return {
            "task_id": task_id,
            "status": "success",
            "result": result
        }
    
    elif task_result.state == 'FAILURE':
        # Task je pao sa greškom
        return {
            "task_id": task_id,
            "status":  "failure",
            "error":  str(task_result.info)
        }
    
    else:
        return {
            "task_id": task_id,
            "status": task_result.state.lower()
        }