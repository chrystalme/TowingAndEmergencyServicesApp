"""Pydantic schemas for request/response validation.

These schemas are used by the API layer to validate incoming data and
serialize outgoing data. They are decoupled from the SQLAlchemy models
so that internal database changes don't leak into the public API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------
class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=72)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


class UserRead(UserBase):
    id: int
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# ServiceRequest schemas
# ---------------------------------------------------------------------------
class ServiceRequestBase(BaseModel):
    service_type: str = Field("towing", min_length=1, max_length=50)
    vehicle_type: str = Field("car", min_length=1, max_length=50)
    name: str = Field("", min_length=0, max_length=200)
    phone_number: str = Field("", min_length=0, max_length=30)
    description: str = Field(..., min_length=1, max_length=2000)
    location: str = Field(..., min_length=1, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class ServiceRequestCreate(ServiceRequestBase):
    pass


class ServiceRequestUpdate(BaseModel):
    service_type: Optional[str] = Field(None, min_length=1, max_length=50)
    vehicle_type: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = None
    phone_number: Optional[str] = Field(None, min_length=0, max_length=30)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    location: Optional[str] = Field(None, min_length=1, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    status: Optional[str] = Field(None, pattern="^(pending|assigned|enroute|in_progress|completed|cancelled)$")


class ServiceRequestRead(ServiceRequestBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    # Admin / management display extras. Populated server-side when a dispatch
    # exists and the caller is allowed to see the broader picture. These are not
    # ORM attributes, so they default to None unless explicitly set.
    requester_email: Optional[str] = None
    requester_name: Optional[str] = None
    dispatch_status: Optional[str] = None
    driver_email: Optional[str] = None
    driver_lat: Optional[float] = None
    driver_lng: Optional[float] = None
    price: Optional[float] = None
    distance_km: Optional[float] = None
    eta_minutes: Optional[float] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Driver schemas (availability + live position)
# ---------------------------------------------------------------------------
class DriverUpdate(BaseModel):
    is_online: Optional[bool] = None
    # available | enroute | off_duty
    current_status: Optional[str] = Field(
        None, pattern="^(available|enroute|off_duty)$"
    )
    current_lat: Optional[float] = Field(None, ge=-90, le=90)
    current_lng: Optional[float] = Field(None, ge=-180, le=180)


class DriverRead(BaseModel):
    id: int
    user_id: int
    is_online: bool
    current_status: str
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    last_position_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dispatch schemas (a matched driver<->request assignment)
# ---------------------------------------------------------------------------
class DispatchRead(BaseModel):
    id: int
    request_id: int
    driver_id: int
    status: str
    distance_km: Optional[float] = None
    eta_minutes: Optional[float] = None
    price: Optional[float] = None
    created_at: datetime
    responded_at: Optional[datetime] = None
    # Denormalized for display convenience: who was matched and where they are.
    driver_name: Optional[str] = None
    driver_email: Optional[str] = None
    driver_lat: Optional[float] = None
    driver_lng: Optional[float] = None

    class Config:
        from_attributes = True


# Describes a nearby candidate driver returned by the matcher before assignment.
class DriverCandidate(BaseModel):
    driver_id: int
    name: Optional[str] = None
    email: str
    current_lat: float
    current_lng: float
    distance_km: float
    eta_minutes: float


class DispatchMatchResponse(BaseModel):
    dispatch: DispatchRead
    request_status: str
    candidates: list[DriverCandidate]


# ---------------------------------------------------------------------------
# Vehicle schemas
# ---------------------------------------------------------------------------
class VehicleBase(BaseModel):
    make: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1900, le=2100)
    plate_number: str = Field(..., min_length=1, max_length=20)


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    make: Optional[str] = Field(None, min_length=1, max_length=100)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    plate_number: Optional[str] = Field(None, min_length=1, max_length=20)


class VehicleRead(VehicleBase):
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# EmergencyLog schemas
# ---------------------------------------------------------------------------
class EmergencyLogBase(BaseModel):
    incident_type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=3000)


class EmergencyLogCreate(EmergencyLogBase):
    pass


class EmergencyLogUpdate(BaseModel):
    incident_type: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1, max_length=3000)
    resolved: Optional[bool] = None


class EmergencyLogRead(EmergencyLogBase):
    id: int
    reporter_id: int
    timestamp: datetime
    resolved: bool

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Token / Auth schemas (for FastAPI-Users integration)
# ---------------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[int] = None
    exp: Optional[int] = None