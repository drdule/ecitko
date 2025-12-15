import os
from typing import Optional
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()


class Database:
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.user = os.getenv('DB_USER', 'ecitko_user')
        self.password = os.getenv('DB_PASSWORD', 'strongpassword')
        self.database = os.getenv('DB_NAME', 'ecitko_db')
        self.connection = None

    def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            return self.connection
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def consumer_exists(self, consumer_id: int) -> bool:
        """Check if a consumer exists in the database"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            query = "SELECT id FROM consumers WHERE id = %s"
            cursor.execute(query, (consumer_id,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Error as e:
            print(f"Error checking consumer existence: {e}")
            return False

    def insert_image(self, consumer_id: int, image_url: str) -> Optional[int]:
        """Insert image record into database and return the image_id"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor()
            query = """
                INSERT INTO images (consumer_id, image_url, processed, created_at)
                VALUES (%s, %s, 0, NOW())
            """
            cursor.execute(query, (consumer_id, image_url))
            self.connection.commit()
            image_id = cursor.lastrowid
            cursor.close()
            return image_id
        except Error as e:
            print(f"Error inserting image: {e}")
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
