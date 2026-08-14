"""SQLAlchemy models for the Towing & Emergency Services backend.

We keep a single ``Base`` that Alembic can discover for autogeneration.

Geography is stored as plain float ``latitude``/``longitude`` columns (cross
dialect so unit tests can run on aiosqlite and production on Postgres). Distance
ranking is done in Python (Haversine) via ``app/services/geo.py``; a PostGIS or
routing-engine upgrade slots into ``app/services/dispatch.py`` later without
changing the public API.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Float, Numeric,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional
from ..core.database import engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


# ---------- User model (FastAPI Users compatible) ----------
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Role: commuter (default), driver, company, admin. Used by dispatch to
    # decide who is eligible to accept jobs and by the UI to gate surfaces.
    role: Mapped[str] = mapped_column(String, default="commuter", nullable=False)

    # Relationships
    service_requests = relationship("ServiceRequest", back_populates="user")
    vehicles = relationship("Vehicle", back_populates="owner")
    emergency_logs = relationship("EmergencyLog", back_populates="reporter")
    driver_profile = relationship("Driver", back_populates="user", uselist=False)
    dispatches = relationship("Dispatch", back_populates="driver", foreign_keys="Dispatch.driver_id")


# ---------- ServiceRequest model ----------
class ServiceRequest(Base):
    __tablename__ = "service_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    # Dispatch-relevant fields (persisted from the request form so matching and
    # pricing can run server-side and clients can read them back).
    service_type: Mapped[str] = mapped_column(String, default="towing", nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String, default="car", nullable=False)
    name: Mapped[str] = mapped_column(String, default="", nullable=False)
    phone_number: Mapped[str] = mapped_column(String, default="", nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="service_requests")
    dispatch = relationship("Dispatch", back_populates="request", uselist=False)


# ---------- Vehicle model ----------
class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    make: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    plate_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="vehicles")


# ---------- EmergencyLog model ----------
class EmergencyLog(Base):
    __tablename__ = "emergency_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    incident_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    reporter = relationship("User", back_populates="emergency_logs")


# ---------- Driver profile (availability + live position) ----------
class Driver(Base):
    """Per-driver live state used by the dispatcher to find the nearest driver.

    One row per user who goes online as a driver; upserted via
    ``PUT /api/drivers/me`` or the WebSocket position stream.
    """
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    # available | enroute | off_duty
    current_status: Mapped[str] = mapped_column(String, default="off_duty")
    current_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_position_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="driver_profile", foreign_keys=[user_id])


# ---------- Dispatch (an assignment of a driver to a request) ----------
class Dispatch(Base):
    """A matched assignment: which driver was routed to which request.

    ``status``: assigned | accepted | declined | enroute | arrived | completed |
    cancelled. Distance/ETA are snapshotted at match time; price is computed
    server-side from distance + service/vehicle type.
    """
    __tablename__ = "dispatches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="assigned")
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eta_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    request = relationship("ServiceRequest", back_populates="dispatch", foreign_keys=[request_id])
    driver = relationship("User", back_populates="dispatches", foreign_keys=[driver_id])
