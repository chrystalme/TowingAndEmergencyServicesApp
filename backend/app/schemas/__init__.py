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
    description: str = Field(..., min_length=1, max_length=2000)
    location: str = Field(..., min_length=1, max_length=500)


class ServiceRequestCreate(ServiceRequestBase):
    pass


class ServiceRequestUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    location: Optional[str] = Field(None, min_length=1, max_length=500)
    status: Optional[str] = Field(None, pattern="^(pending|assigned|in_progress|completed|cancelled)$")


class ServiceRequestRead(ServiceRequestBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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