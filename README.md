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

Upload slika za vodomer.

**Requires authentication via Bearer token.**

### Request
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Parameters**:
  - `waterMeterId` (int, required): ID vodomera
  - `file` (file, required): Slika fajl (JPEG, JPG, PNG)

### Response

**Success (200)**:
```json
{
  "message": "Image uploaded successfully",
  "image_id": 1,
  "image_url": "/srv/ecitko/uploads/1_20231215_143022_a1b2c3d4.jpg"
}
```

**Error (400)** - Invalid file format:
```json
{
  "detail": "Invalid file format. Allowed formats: JPEG, JPG, PNG"
}
```

**Error (404)** - Water meter not found:
```json
{
  "detail": "Water meter with ID 1 not found or inactive"
}
```

### Primer cURL zahteva:

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "Authorization: Bearer your_secret_token_here" \
  -F "waterMeterId=1" \
  -F "file=@meter_reading.jpg"
```

## Authentication

All image upload endpoints require API token authentication.

### Setup

1. Set the API token in `.env` file:
   ```
   API_TOKEN=your_secret_token_here
   ```

2. Include the token in the Authorization header:
   ```
   Authorization: Bearer your_secret_token_here
   ```

### Example

```bash
curl -X POST http://your-server:8002/upload \
  -H "Authorization: Bearer your_secret_token_here" \
  -F "waterMeterId=1" \
  -F "file=@image.jpg"
```

### Protected Endpoints

- `POST /upload` - Upload image
- `POST /notify_upload` - Notify upload

### Public Endpoints

- `GET /` - Root
- `GET /health` - Health check
- `GET /metrics` - System metrics

## MySQL Schema

Aplikacija očekuje sledeće tabele:

```sql
CREATE TABLE consumers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE water_meters (
    id INT PRIMARY KEY AUTO_INCREMENT,
    consumer_id INT NOT NULL,
    meter_code VARCHAR(50) UNIQUE NOT NULL,
    location VARCHAR(255),
    installation_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(id)
);

CREATE TABLE images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    water_meter_id INT NOT NULL,
    image_url VARCHAR(512) NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (water_meter_id) REFERENCES water_meters(id)
);

CREATE TABLE readings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    water_meter_id INT NOT NULL,
    reading_value DECIMAL(10,2),
    image_path VARCHAR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (water_meter_id) REFERENCES water_meters(id)
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
└── README.md           # Dokumentacija
```

## Testiranje

Za testiranje endpointa, prvo pokreni aplikaciju, a zatim možeš koristiti:

### cURL
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "waterMeterId=1" \
  -F "file=@meter_reading.jpg"
```

### Swagger UI
Otvori browser i idi na `http://localhost:8000/docs` za interaktivnu API dokumentaciju.

## Bezbednosne karakteristike

- **Validacija environment varijabli**: Sve neophodne env varijable moraju biti postavljene
- **Connection pooling**: Thread-safe pristup bazi podataka
- **Cursor leak prevention**: Svi cursor-i se pravilno zatvaraju
- **File size validation**: Maksimalna veličina fajla je 5MB
- **Filename sanitization**: Sprečavanje path traversal napada
- **Image content validation**: Provera magic bytes za validnost slike
- **Error message sanitization**: Interni detalji se ne prikazuju korisnicima
- **UUID u imenu fajla**: Dodatna zaštita od kolizije fajlova
- **Chunked file upload**: Efikasno upravljanje memorijom