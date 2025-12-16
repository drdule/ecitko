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

    def consumer_exists(self, consumer_id: int) -> bool:
        """Check if a consumer exists"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = "SELECT id FROM consumers WHERE id = %s"
                cursor.execute(query, (consumer_id,))
                result = cursor.fetchone()
                return result is not None
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error checking consumer existence: {e}")
            raise

    def insert_image(self, consumer_id: int, image_url: str) -> Optional[int]:
        """Insert image record into database and return the image_id"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            try:
                query = """
                    INSERT INTO images (consumer_id, image_url, processed, created_at)
                    VALUES (%s, %s, 0, NOW())
                """
                cursor.execute(query, (consumer_id, image_url))
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

    def get_consumer_info(self, consumer_id: int) -> Optional[dict]:
        """Get consumer information"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor(dictionary=True)
            try:
                query = """
                    SELECT 
                        id,
                        name,
                        address,
                        created_at
                    FROM consumers
                    WHERE id = %s
                """
                cursor.execute(query, (consumer_id,))
                return cursor.fetchone()
            finally:
                cursor.close()
        except Error as e:
            logger.error(f"Error getting consumer info: {e}")
            raise


def get_database():
    """Dependency to get database instance"""
    db = Database()
    try:
        db.connect()
        yield db
    finally:
        db.disconnect()
