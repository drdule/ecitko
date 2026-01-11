import os
import logging
from typing import Optional
import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        # Get environment variables without defaults
        self.host = os.getenv('DB_HOST')
        self.user = os.getenv('DB_USER')
        self.password = os.getenv('DB_PASSWORD')
        self.database = os.getenv('DB_NAME')
        
        # Validate that all required environment variables are set
        missing = []
        if not self.host:
            missing. append('DB_HOST')
        if not self.user:
            missing.append('DB_USER')
        if not self.password:
            missing.append('DB_PASSWORD')
        if not self. database:
            missing.append('DB_NAME')
        if missing:
            raise RuntimeError(f"Missing required database environment variables: {', '.join(missing)}")
        
        self.pool = None
        self.connection = None

    def connect(self):
        """Establish database connection using connection pool"""
        try:
            # Create connection pool if it doesn't exist
            if not self.pool:
                self.pool = MySQLConnectionPool(
                    pool_name="ecitko_pool",
                    pool_size=5,
                    host=self. host,
                    user=self.user,
                    password=self.password,
                    database=self.database
                )
            
            # Get connection from pool
            self.connection = self. pool.get_connection()
            
        except Error as e: 
            logger.error(f"Error connecting to MySQL: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def water_meter_exists(self, water_meter_id:  int) -> bool:
        """Check if a water meter exists and is active"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = "SELECT id FROM water_meters WHERE id = %s AND is_active = 1"
                cursor.execute(query, (water_meter_id,))
                result = cursor.fetchone()
                return result is not None
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error checking water meter existence: {e}")
            raise

    def insert_image(self, water_meter_id: int, image_url: str) -> Optional[int]:
        """Insert image record into database and return the image_id"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self. connection.cursor()
            try:
                query = """
                    INSERT INTO images (water_meter_id, image_url, processed, created_at)
                    VALUES (%s, %s, 0, NOW())
                """
                cursor.execute(query, (water_meter_id, image_url))
                self.connection. commit()
                image_id = cursor.lastrowid
                return image_id
            finally: 
                cursor.close()
        except Error as e:
            logger. error(f"Error inserting image: {e}")
            if self.connection:
                self.connection.rollback()
            raise

    def get_water_meter_info(self, water_meter_id: int) -> Optional[dict]:
        """Get water meter information including consumer details"""
        try: 
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor(dictionary=True)
            try:
                query = """
                    SELECT 
                        wm.id as meter_id,
                        wm.meter_code,
                        wm.location,
                        wm.is_active,
                        c.id as consumer_id,
                        c.customer_code,
                        c.name as consumer_name
                    FROM water_meters wm
                    JOIN consumers c ON wm.consumer_id = c.id
                    WHERE wm.id = %s
                """
                cursor.execute(query, (water_meter_id,))
                return cursor. fetchone()
            finally: 
                cursor.close()
        except Error as e:
            logger. error(f"Error getting water meter info: {e}")
            raise

    def get_total_images_count(self) -> int:
        """Get total count of images"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM images")
                result = cursor.fetchone()
                return result[0] if result else 0
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting total images count: {e}")
            raise

    def get_total_water_meters_count(self) -> int:
        """Get count of active water meters"""
        try: 
            if not self.connection or not self.connection. is_connected():
                self. connect()
            
            cursor = self.connection.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM water_meters WHERE is_active = 1")
                result = cursor.fetchone()
                return result[0] if result else 0
            finally:
                cursor.close()
        except Error as e:  
            logger.error(f"Error getting water meters count: {e}")
            raise

    def get_total_consumers_count(self) -> int:
        """Get total count of consumers"""
        try:
            if not self. connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM consumers")
                result = cursor.fetchone()
                return result[0] if result else 0
            finally: 
                cursor.close()
        except Error as e: 
            logger.error(f"Error getting consumers count: {e}")
            raise

    def get_images_by_water_meter(self) -> dict:
        """Get image count grouped by water_meter_id"""
        try: 
            if not self.connection or not self. connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                cursor. execute("""
                    SELECT water_meter_id, COUNT(*) as count 
                    FROM images 
                    GROUP BY water_meter_id
                """)
                results = cursor.fetchall()
                return {str(row[0]): row[1] for row in results}
            finally: 
                cursor.close()
        except Error as e: 
            logger.error(f"Error getting images by water meter: {e}")
            raise

    def get_image_by_id(self, image_id: int) -> Optional[dict]:
        """Get image record by ID"""
        try:  
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self. connection.cursor(dictionary=True)
            try:
                cursor. execute("SELECT * FROM images WHERE id = %s", (image_id,))
                return cursor.fetchone()
            finally:
                cursor.close()
        except Error as e: 
            logger.error(f"Error getting image by ID: {e}")
            raise

    def update_image_processed(self, image_id: int, processed: bool = True):
        """Update processed flag for an image"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self. connection.cursor()
            try:
                query = "UPDATE images SET processed = %s WHERE id = %s"
                cursor.execute(query, (1 if processed else 0, image_id))
                self.connection.commit()
            finally:
                cursor.close()
        except Error as e: 
            logger.error(f"Error updating image processed flag: {e}")
            if self.connection:
                self.connection.rollback()
            raise

    def save_ocr_result(
        self,
        image_id: int,
        task_id: str,
        value:  str,
        raw_text:  str,
        confidence: float,
        status: str,
        error_message: str = None
    ) -> int:
        """
        Save OCR result to database
        
        Args:
            image_id:  ID of the image
            task_id: Celery task ID
            value: Extracted value (water meter reading)
            raw_text: Raw OCR text
            confidence: OCR confidence score (0-100)
            status: Status ('success' or 'error')
            error_message: Error message if status='error'
            
        Returns: 
            int: ID of inserted OCR result
        """
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = """
                    INSERT INTO ocr_results 
                    (image_id, task_id, value, raw_text, confidence, status, error_message, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """
                
                cursor.execute(query, (
                    image_id,
                    task_id,
                    value,
                    raw_text,
                    confidence,
                    status,
                    error_message
                ))
                
                self.connection.commit()
                ocr_result_id = cursor.lastrowid
                return ocr_result_id
            finally:
                cursor. close()
        except Error as e:
            logger.error(f"Error saving OCR result: {e}")
            if self.connection:
                self.connection.rollback()
            raise


def get_database():
    """Dependency to get database instance"""
    db = Database()
    try:
        db.connect()
        yield db
    finally:
        db.disconnect()