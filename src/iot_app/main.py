# src/iot_app/main.py
"""
IoT Ingestion Service - Smart Campus Platform
Provides API endpoints for ingesting sensor telemetry data.
"""

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import uuid
import os
from contextlib import asynccontextmanager

# Configuration
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# In-memory storage (for lab purposes)
readings_store = []
rate_limit_counter = {}


class SensorMetric(str):
    """Sensor metric types"""
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    MOTION = "motion"
    SMOKE = "smoke"


class ProblemDetails(BaseModel):
    """RFC 7807 Problem Details for error responses"""
    type: str
    title: str
    status: int
    detail: str
    instance: Optional[str] = None


class SensorReadingCreate(BaseModel):
    """Request model for creating a sensor reading"""
    device_id: str = Field(..., min_length=3, example="ESP32-LAB-A01")
    metric: str = Field(..., description="Sensor metric type")
    value: float = Field(..., description="Sensor value")
    unit: str = Field(..., description="Unit of measurement")
    timestamp: str = Field(..., description="ISO 8601 timestamp")

    @field_validator('metric')
    def validate_metric(cls, v):
        allowed = ['temperature', 'humidity', 'motion', 'smoke']
        if v not in allowed:
            raise ValueError(f'metric must be one of {allowed}')
        return v

    @field_validator('value')
    def validate_value(cls, v, info):
        metric = info.data.get('metric')
        if metric == 'temperature':
            if v < -40 or v > 80:
                raise ValueError('temperature must be between -40 and 80')
        elif metric == 'humidity':
            if v < 0 or v > 100:
                raise ValueError('humidity must be between 0 and 100')
        elif metric == 'motion':
            if v not in [0, 1]:
                raise ValueError('motion must be 0 or 1')
        elif metric == 'smoke':
            if v < 0 or v > 1000:
                raise ValueError('smoke must be between 0 and 1000')
        return v

    @field_validator('unit')
    def validate_unit(cls, v, info):
        metric = info.data.get('metric')
        unit_map = {
            'temperature': ['celsius'],
            'humidity': ['percent'],
            'motion': ['boolean'],
            'smoke': ['ppm']
        }
        allowed = unit_map.get(metric, [])
        if v not in allowed:
            raise ValueError(f'unit for {metric} must be {allowed}')
        return v


class SensorReadingCreated(BaseModel):
    """Response model for created sensor reading"""
    reading_id: str
    device_id: str
    metric: str
    accepted: bool
    created_at: str


class SensorReading(SensorReadingCreate):
    """Full sensor reading model with ID"""
    reading_id: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str


# Create FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("IoT Ingestion Service starting...")
    yield
    # Shutdown
    print("IoT Ingestion Service shutting down...")


app = FastAPI(
    title="Smart Campus — IoT Ingestion API",
    version="0.4.0",
    description="API for ingesting sensor telemetry from IoT devices",
    lifespan=lifespan
)


# Middleware for authentication
@app.middleware("http")
async def authenticate(request: Request, call_next):
    # Skip auth for health endpoint
    if request.url.path == "/health":
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "type": "https://smart-campus.local/problems/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Missing Authorization header",
                "instance": request.url.path
            }
        )

    # Check Bearer token
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "type": "https://smart-campus.local/problems/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid authorization scheme. Use Bearer token",
                "instance": request.url.path
            }
        )

    token = auth_header.split(" ")[1]
    if token != AUTH_TOKEN:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "type": "https://smart-campus.local/problems/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid token",
                "instance": request.url.path
            }
        )

    return await call_next(request)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "type": "https://smart-campus.local/problems/validation-error",
            "title": "Validation error",
            "status": 400,
            "detail": jsonable_encoder(exc.errors()),
            "instance": request.url.path
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "type": "https://smart-campus.local/problems/validation-error",
            "title": "Validation error",
            "status": 400,
            "detail": str(exc),
            "instance": request.url.path
        }
    )


# Health check endpoint
@app.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse, tags=["system"])
async def health_check():
    """Check if the service is running"""
    return HealthResponse(
        status="ok",
        service="iot-ingestion",
        version="0.4.0"
    )


# Create reading endpoint
@app.post("/readings", response_model=SensorReadingCreated, status_code=status.HTTP_201_CREATED, tags=["readings"])
async def create_reading(reading: SensorReadingCreate):
    """Ingest a new sensor reading from an IoT device"""
    reading_id = f"R-{datetime.now().strftime('%Y%m%d')}-{len(readings_store) + 1:04d}"

    # Store the reading
    stored_reading = reading.model_dump()
    stored_reading["reading_id"] = reading_id
    readings_store.append(stored_reading)

    return SensorReadingCreated(
        reading_id=reading_id,
        device_id=reading.device_id,
        metric=reading.metric,
        accepted=True,
        created_at=datetime.now().isoformat()
    )


# Get latest readings endpoint
@app.get("/readings/latest", tags=["readings"])
async def get_latest_readings(
    device_id: Optional[str] = None,
    limit: int = 10
):
    """Get the most recent sensor readings"""
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 100"
        )

    # Filter by device_id if provided
    filtered = readings_store
    if device_id:
        filtered = [r for r in filtered if r["device_id"] == device_id]

    # Get latest by reversing (most recent first)
    latest = filtered[::-1][:limit]

    return {"items": latest}


# Get reading by ID
@app.get("/readings/{reading_id}", tags=["readings"])
async def get_reading(reading_id: str):
    """Get a specific sensor reading by ID"""
    for reading in readings_store:
        if reading["reading_id"] == reading_id:
            return reading
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Reading {reading_id} not found"
    )