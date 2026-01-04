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

    def get_image_by_id(self, image_id: int) -> Optional[dict]:
        """Get image record by ID"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor(dictionary=True)
            try:
                query = "SELECT * FROM images WHERE id = %s"
                cursor.execute(query, (image_id,))
                return cursor.fetchone()
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting image by ID: {e}")
            raise

    def get_total_images_count(self) -> int:
        """Get total count of images"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = "SELECT COUNT(*) FROM images"
                cursor.execute(query)
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
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = "SELECT COUNT(*) FROM water_meters WHERE is_active = 1"
                cursor.execute(query)
                result = cursor.fetchone()
                return result[0] if result else 0
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting total water meters count: {e}")
            raise

    def get_total_consumers_count(self) -> int:
        """Get total count of consumers"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = "SELECT COUNT(*) FROM consumers"
                cursor.execute(query)
                result = cursor.fetchone()
                return result[0] if result else 0
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting total consumers count: {e}")
            raise

    def get_images_by_water_meter(self) -> dict:
        """Get image count grouped by water_meter_id"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = "SELECT water_meter_id, COUNT(*) as count FROM images GROUP BY water_meter_id"
                cursor.execute(query)
                results = cursor.fetchall()
                # Convert to dictionary
                return {str(row[0]): row[1] for row in results}
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting images by water meter: {e}")
            raise

    def check_database_connection(self) -> bool:
        """Check if database connection is healthy"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
                return True
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    def update_image_processed(self, image_id: int, processed: bool = True) -> bool:
        """Update processed status of an image"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = "UPDATE images SET processed = %s WHERE id = %s"
                cursor.execute(query, (1 if processed else 0, image_id))
                self.connection.commit()
                return cursor.rowcount > 0
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error updating image processed status: {e}")
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
