-- Database initialization script for Ecitko water meter reading system
-- This script creates the necessary tables and inserts sample data

-- ============================================================================
-- TABLE: consumers
-- Purpose: Store consumer information with unique customer codes
-- ============================================================================
CREATE TABLE IF NOT EXISTS consumers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: water_meters
-- Purpose: Store water meter information, allowing multiple meters per consumer
-- ============================================================================
CREATE TABLE IF NOT EXISTS water_meters (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    meter_code VARCHAR(50) UNIQUE NOT NULL,
    location VARCHAR(255),
    installation_date DATE,
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);

-- ============================================================================
-- TABLE: images
-- Purpose: Store images of water meters for OCR processing
-- ============================================================================
CREATE TABLE IF NOT EXISTS images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    water_meter_id INT NOT NULL,
    image_url VARCHAR(512) NOT NULL,
    processed TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (water_meter_id) REFERENCES water_meters(id)
);

-- ============================================================================
-- TABLE: readings
-- Purpose: Store water meter readings
-- ============================================================================
CREATE TABLE IF NOT EXISTS readings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    water_meter_id INT NOT NULL,
    reading_value DECIMAL(10,2),
    image_path VARCHAR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (water_meter_id) REFERENCES water_meters(id)
);

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

-- Insert sample consumers
INSERT INTO consumers (customer_code, name, address) VALUES 
    ('K-001', 'Petar Petrović', 'Kralja Petra 1, Beograd'),
    ('K-002', 'Marija Marković', 'Bulevar oslobođenja 23, Novi Sad'),
    ('K-003', 'Jovan Jovanović', 'Kneza Miloša 45, Niš');

-- Insert sample water meters (showing consumer K-001 has 2 meters)
INSERT INTO water_meters (consumer_id, meter_code, location, installation_date) VALUES
    (1, 'VM-001-A', 'Glavni vodomer', '2024-01-15'),
    (1, 'VM-001-B', 'Vodomer u bašti', '2024-01-15'),
    (2, 'VM-002-A', 'Stan', '2024-02-10'),
    (3, 'VM-003-A', 'Kuća', '2024-03-05');
