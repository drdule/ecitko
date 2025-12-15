-- Initialize database schema for ecitko application

CREATE TABLE IF NOT EXISTS consumers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    image_url VARCHAR(512) NOT NULL,
    processed TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);

CREATE TABLE IF NOT EXISTS readings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    reading_value DECIMAL(10,2),
    image_path VARCHAR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);

-- Insert sample data for testing
INSERT INTO consumers (name, address) VALUES 
    ('Petar Petrović', 'Kralja Petra 1, Beograd'),
    ('Marija Marković', 'Bulevar oslobođenja 23, Novi Sad'),
    ('Jovan Jovanović', 'Kneza Miloša 45, Niš');
