from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Consumer(Base):
    __tablename__ = 'consumers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class WaterMeter(Base):
    __tablename__ = 'water_meters'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    consumer_id = Column(Integer, ForeignKey('consumers.id'), nullable=False)
    meter_code = Column(String(50), unique=True, nullable=False)
    location = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func. now())


class Image(Base):
    __tablename__ = 'images'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    water_meter_id = Column(Integer, ForeignKey('water_meters.id'), nullable=False)
    image_url = Column(String(255), nullable=False)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class OCRResult(Base):
    __tablename__ = 'ocr_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_id = Column(Integer, ForeignKey('images.id'), nullable=False)
    task_id = Column(String(50), unique=True, nullable=False)
    value = Column(String(50))
    raw_text = Column(Text)
    confidence = Column(Float)
    status = Column(String(20))
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
