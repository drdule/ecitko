# ecitko

FastAPI aplikacija za upload slika potrošača brojila.

## Instalacija i pokretanje

### Opcija 1: Docker (preporučeno)

1. Pokreni aplikaciju sa Docker Compose:
```bash
docker-compose up -d
```

2. API će biti dostupan na `http://localhost:8000`
3. MySQL baza će biti automatski inicijalizovana sa test podacima

### Opcija 2: Lokalna instalacija

1. Instaliraj dependencies:
```bash
pip install -r requirements.txt
```

2. Kopiraj `.env.example` u `.env` i podesi konfiguraciju:
```bash
cp .env.example .env
```

3. Ažuriraj `.env` fajl sa pravim kredencijalima za bazu.

4. Kreiraj MySQL bazu i tabele (koristi `init.sql` skripta):
```bash
mysql -u root -p < init.sql
```

5. Pokreni aplikaciju:
```bash
uvicorn main:app --reload
```

API će biti dostupan na `http://localhost:8000`

## Dokumentacija

FastAPI automatski generiše dokumentaciju:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Endpoint: POST /upload

Upload slika za potrošača.

### Request
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Parameters**:
  - `consumerId` (int, required): ID potrošača
  - `file` (file, required): Slika fajl (JPEG, JPG, PNG)

### Response

**Success (200)**:
```json
{
  "message": "Image uploaded successfully",
  "image_id": 1,
  "image_url": "/srv/ecitko/uploads/123_20231215_143022_image.jpg"
}
```

**Error (400)** - Invalid file format:
```json
{
  "detail": "Invalid file format. Allowed formats: JPEG, JPG, PNG"
}
```

**Error (404)** - Consumer not found:
```json
{
  "detail": "Consumer with ID 123 not found"
}
```

### Primer cURL zahteva:

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "consumerId=1" \
  -F "file=@/path/to/image.jpg"
```

## MySQL Schema

Aplikacija očekuje sledeće tabele:

```sql
CREATE TABLE consumers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    image_url VARCHAR(512) NOT NULL,
    processed TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);

CREATE TABLE readings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    reading_value DECIMAL(10,2),
    image_path VARCHAR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);
```

## Struktura projekta

```
ecitko/
├── main.py              # FastAPI aplikacija i endpoint
├── database.py          # MySQL konekcija i helper funkcije
├── requirements.txt     # Python dependencies
├── .env.example         # Primer environment varijabli
├── .gitignore          # Git ignore rules
├── Dockerfile          # Docker image konfiguracija
├── docker-compose.yml  # Docker Compose setup
├── init.sql            # MySQL schema i test podaci
├── test_upload.py      # Primer test skripta
└── README.md           # Dokumentacija
```

## Testiranje

Za testiranje endpointa, prvo pokreni aplikaciju, a zatim možeš koristiti:

### cURL
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "consumerId=1" \
  -F "file=@/path/to/image.jpg"
```

### Python test script
```bash
python test_upload.py
```

### Swagger UI
Otvori browser i idi na `http://localhost:8000/docs` za interaktivnu API dokumentaciju.