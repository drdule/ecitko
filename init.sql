-- Database initialization script for Ecitko water meter reading system
-- This script creates the necessary tables and inserts sample data

-- ============================================================================
-- TABLE: consumers
-- Purpose: Store consumer information with unique customer codes
-- ============================================================================
CREATE TABLE IF NOT EXISTS consumers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: water_meters
-- Purpose: Store water meter information, allowing multiple meters per consumer
-- ============================================================================
CREATE TABLE IF NOT EXISTS water_meters (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    meter_code VARCHAR(50) UNIQUE NOT NULL,
    location VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);

-- ============================================================================
-- TABLE: images
-- Purpose: Store images of water meters for OCR processing
-- ============================================================================
CREATE TABLE IF NOT EXISTS images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    water_meter_id INT NOT NULL,
    image_url VARCHAR(255) NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (water_meter_id) REFERENCES water_meters(id)
);

-- ============================================================================
-- TABLE: ocr_results
-- Purpose: Store OCR processing results for each uploaded image
-- ============================================================================
CREATE TABLE IF NOT EXISTS ocr_results (
    id INT PRIMARY KEY AUTO_INCREMENT,
    image_id INT NOT NULL,
    task_id VARCHAR(50) UNIQUE NOT NULL,
    value VARCHAR(50),
    raw_text TEXT,
    confidence FLOAT,
    status VARCHAR(20),
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

-- Insert sample consumers
INSERT INTO consumers (customer_code, name) VALUES 
    ('K-001', 'Petar Petrović'),
    ('K-002', 'Marija Marković'),
    ('K-003', 'Jovan Jovanović');

-- Insert sample water meters (showing consumer K-001 has 2 meters)
INSERT INTO water_meters (consumer_id, meter_code, location) VALUES
    ((SELECT id FROM consumers WHERE customer_code = 'K-001'), 'VM-001-A', 'Glavni vodomer'),
    ((SELECT id FROM consumers WHERE customer_code = 'K-001'), 'VM-001-B', 'Vodomer u bašti'),
    ((SELECT id FROM consumers WHERE customer_code = 'K-002'), 'VM-002-A', 'Stan'),
    ((SELECT id FROM consumers WHERE customer_code = 'K-003'), 'VM-003-A', 'Kuća');
