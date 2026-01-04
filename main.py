from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
from typing import Optional

app = FastAPI(title="Ecitko API", version="1.0.0")

# Security scheme for Swagger UI
security = HTTPBearer()

# Get API token from environment variable
API_TOKEN = os.getenv("API_TOKEN", "your-secret-token")

# Token verification dependency
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify the Bearer token from the Authorization header.
    """
    token = credentials.credentials
    
    if token != API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

# Models
class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

# Public endpoint
@app.get("/")
async def root():
    """
    Public endpoint - no authentication required.
    """
    return {"message": "Welcome to Ecitko API"}

# Protected endpoints
@app.get("/protected")
async def protected_route(token: str = Depends(verify_token)):
    """
    Protected endpoint - requires Bearer token authentication.
    """
    return {"message": "This is a protected route", "authenticated": True}

@app.post("/items/")
async def create_item(item: Item, token: str = Depends(verify_token)):
    """
    Create a new item - requires Bearer token authentication.
    """
    item_dict = item.dict()
    if item.tax:
        price_with_tax = item.price + item.tax
        item_dict.update({"price_with_tax": price_with_tax})
    return item_dict

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Optional[str] = None, token: str = Depends(verify_token)):
    """
    Get item by ID - requires Bearer token authentication.
    """
    result = {"item_id": item_id}
    if q:
        result.update({"q": q})
    return result
