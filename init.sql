-- Database initialization script for Ecitko consumer image upload system
-- This script creates the necessary tables and inserts sample data

-- ============================================================================
-- TABLE: consumers
-- Purpose: Store consumer information
-- ============================================================================
CREATE TABLE IF NOT EXISTS consumers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: images
-- Purpose: Store images of consumers for OCR processing
-- ============================================================================
CREATE TABLE IF NOT EXISTS images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    image_url VARCHAR(255) NOT NULL,
    processed TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

-- Insert sample consumers
INSERT INTO consumers (name, address) VALUES 
    ('Petar Petrović', 'Kralja Petra 1, Beograd'),
    ('Marija Marković', 'Bulevar oslobođenja 23, Novi Sad'),
    ('Jovan Jovanović', 'Kneza Miloša 45, Niš');
