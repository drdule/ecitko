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
            missing.append('DB_HOST')
        if not self.user:
            missing.append('DB_USER')
        if not self.password:
            missing.append('DB_PASSWORD')
        if not self.database:
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
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database
                )
            
            # Get connection from pool
            self.connection = self.pool.get_connection()
            
        except Error as e:
            logger.error(f"Error connecting to MySQL: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def water_meter_exists(self, water_meter_id: int) -> bool:
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
            
            cursor = self.connection.cursor()
            try:
                query = """
                    INSERT INTO images (water_meter_id, image_url, processed, created_at)
                    VALUES (%s, %s, 0, NOW())
                """
                cursor.execute(query, (water_meter_id, image_url))
                self.connection.commit()
                image_id = cursor.lastrowid
                return image_id
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error inserting image: {e}")
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
                return cursor.fetchone()
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting water meter info: {e}")
            raise

    def get_metrics(self) -> dict:
        """Get system metrics including image and water meter counts"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                # Get total images count
                cursor.execute("SELECT COUNT(*) as total FROM images")
                result = cursor.fetchone()
                total_images = result[0] if result else 0
                
                # Get processed images count
                cursor.execute("SELECT COUNT(*) as total FROM images WHERE processed = 1")
                result = cursor.fetchone()
                processed_images = result[0] if result else 0
                
                # Get active water meters count
                cursor.execute("SELECT COUNT(*) as total FROM water_meters WHERE is_active = 1")
                result = cursor.fetchone()
                active_meters = result[0] if result else 0
                
                return {
                    "total_images": total_images,
                    "processed_images": processed_images,
                    "active_water_meters": active_meters
                }
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting metrics: {e}")
            raise


def get_database():
    """Dependency to get database instance"""
    db = Database()
    try:
        db.connect()
        yield db
    finally:
        db.disconnect()
