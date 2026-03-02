import os
import logging
from celery import Celery
from pathlib import Path
import pytesseract
from database import Database
from preprocessing import preprocess_for_ocr, load_base_image_for_ocr
from ocr_utils import average_confidence, extract_water_meter_value, pick_best_reading


def _pick_best_digits(*texts: str) -> str:
    best = ""
    for text in texts:
        if not text:
            continue
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) > len(best):
            best = digits
    return best


def _digit_ocr_texts(image, lang: str) -> list[str]:
    configs = [
        "--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789",
        "--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789",
        "--oem 1 --psm 8 -c tessedit_char_whitelist=0123456789",
        "--oem 1 --psm 11 -c tessedit_char_whitelist=0123456789",
    ]
    out = []
    for cfg in configs:
        out.append(pytesseract.image_to_string(image, lang=lang, config=cfg))
    return out

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
        
        base_image = load_base_image_for_ocr(image_path)
        processed_image = preprocess_for_ocr(image_path)

        digits_lang = "eng"

        raw_ocr_text = pytesseract.image_to_string(base_image, lang='srp')
        raw_ocr_data = pytesseract.image_to_data(
            base_image,
            lang='srp',
            output_type=pytesseract.Output.DICT,
        )
        raw_confidence = average_confidence(raw_ocr_data)

        raw_digit_texts = _digit_ocr_texts(base_image, digits_lang)

        processed_ocr_text = pytesseract.image_to_string(processed_image, lang='srp')
        processed_ocr_data = pytesseract.image_to_data(
            processed_image,
            lang='srp',
            output_type=pytesseract.Output.DICT,
        )
        processed_confidence = average_confidence(processed_ocr_data)

        processed_digit_texts = _digit_ocr_texts(processed_image, digits_lang)

        raw_text_clean = (raw_ocr_text or "").strip()
        processed_text_clean = (processed_ocr_text or "").strip()

        if processed_text_clean and not raw_text_clean:
            ocr_result = processed_ocr_text
            avg_confidence = processed_confidence
        elif raw_text_clean and not processed_text_clean:
            ocr_result = raw_ocr_text
            avg_confidence = raw_confidence
        else:
            ocr_result = processed_ocr_text if processed_confidence >= raw_confidence else raw_ocr_text
            avg_confidence = max(raw_confidence, processed_confidence)

        reading = pick_best_reading(processed_digit_texts + raw_digit_texts)
        digits_text = _pick_best_digits(*(processed_digit_texts + raw_digit_texts))
        value = reading if reading else extract_water_meter_value(digits_text if digits_text else ocr_result)
        import re
        numbers = re.findall(r'\d+', ocr_result)
        
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