import os
import logging
from celery import Celery
from pathlib import Path
import pytesseract
from PIL import Image
from database import Database

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery app
celery_app = Celery(
    'ecitko_worker',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Belgrade',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
)


@celery_app.task(bind=True, name='ecitko_worker.ocr_task')
def ocr_task(self, image_id:  int):
    """
    Celery task for OCR processing
    
    Args:
        image_id: ID of the image in database
        
    Returns: 
        dict: OCR result with value and confidence
    """
    logger.info(f"Starting OCR task for image_id={image_id}")
    
    db = Database()
    
    try:
        # Connect to database
        db.connect()
        
        # Get image from database
        image = db.get_image_by_id(image_id)
        
        if not image: 
            logger.error(f"Image with ID {image_id} not found in database")
            return {
                'status': 'error',
                'error': f'Image with ID {image_id} not found'
            }
        
        image_path = image['image_url']
        
        # Check if file exists
        if not Path(image_path).exists():
            logger.error(f"Image file not found: {image_path}")
            return {
                'status': 'error',
                'error': f'Image file not found: {image_path}'
            }
        
        logger.info(f"Processing image: {image_path}")
        
        # Load image
        img = Image.open(image_path)
        
        # Perform OCR with Serbian language
        # You can add preprocessing here later (Task 13)
        ocr_result = pytesseract.image_to_string(img, lang='srp')
        
        # Get confidence (detailed data)
        ocr_data = pytesseract.image_to_data(img, lang='srp', output_type=pytesseract.Output.DICT)
        
        # Calculate average confidence (only for non-empty text)
        confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Extract numbers (for water meter reading)
        # Simple extraction - will improve in Task 13
        import re
        numbers = re.findall(r'\d+', ocr_result)
        value = ''.join(numbers) if numbers else ocr_result.strip()
        
        logger.info(f"OCR completed for image_id={image_id}, value={value}, confidence={avg_confidence:.2f}%")
        
        result = {
            'status': 'success',
            'image_id': image_id,
            'value': value,
            'raw_text': ocr_result.strip(),
            'confidence': round(avg_confidence, 2),
            'numbers_found': numbers
        }
        
        logger.info(f"OCR Result:  {result}")
        
        # Save OCR result to database
        try:
            ocr_id = db.save_ocr_result(
                image_id=image_id,
                task_id=self.request.id,
                value=value,
                raw_text=ocr_result.strip(),
                confidence=avg_confidence,
                status='success'
            )
            logger.info(f"OCR result saved to database with ID: {ocr_id}")
            result['ocr_result_id'] = ocr_id
        except Exception as db_error:
            logger.error(f"Failed to save OCR result to database: {db_error}")
            # Don't fail the task if database save fails
        
        return result
        
    except Exception as e: 
        logger.error(f"OCR task failed for image_id={image_id}: {str(e)}", exc_info=True)
        
        # Save error to database
        try:
            db.save_ocr_result(
                image_id=image_id,
                task_id=self.request.id,
                value=None,
                raw_text=None,
                confidence=0.0,
                status='error',
                error_message=str(e)
            )
        except Exception as db_error:
            logger.error(f"Failed to save error to database:  {db_error}")
        
        return {
            'status':  'error',
            'error': str(e)
        }
    
    finally:
        db.disconnect()