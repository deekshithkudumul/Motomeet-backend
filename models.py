from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String, nullable=False)
    email          = Column(String, unique=True, index=True, nullable=False)
    password_hash  = Column(String, nullable=False)
    bio            = Column(Text, default="")
    bike_model     = Column(String, default="")
    experience     = Column(String, default="Beginner")  # Beginner/Intermediate/Expert
    city           = Column(String, default="")
    avatar_url     = Column(String, default="")
    total_km       = Column(Float, default=0.0)
    created_at     = Column(DateTime, server_default=func.now())
    progress       = relationship("UserProgress", back_populates="user")
    batches        = relationship("BatchMember", back_populates="user")
    messages       = relationship("Message", back_populates="user")
    badges         = relationship("Badge", back_populates="user")

class Route(Base):
    __tablename__ = "routes"
    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String, nullable=False)
    slug           = Column(String, unique=True, index=True)
    distance_km    = Column(Float)
    difficulty     = Column(String)  # Easy/Moderate/Hard/Expert
    duration_days  = Column(Integer)
    start_point    = Column(String)
    end_point      = Column(String)
    states         = Column(String)
    best_months    = Column(String)
    description    = Column(Text)
    highlights     = Column(Text)
    warnings       = Column(Text)
    waypoints      = Column(JSON)
    image_url      = Column(String, default="")
    elevation_gain = Column(Integer, default=0)
    checkpoints    = relationship("Checkpoint", back_populates="route")
    batches        = relationship("Batch", back_populates="route")

class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id         = Column(Integer, primary_key=True, index=True)
    route_id   = Column(Integer, ForeignKey("routes.id"))
    name       = Column(String)
    lat        = Column(Float)
    lng        = Column(Float)
    order      = Column(Integer)
    distance_from_start = Column(Float, default=0.0)
    description = Column(Text, default="")
    route      = relationship("Route", back_populates="checkpoints")

class UserProgress(Base):
    __tablename__ = "user_progress"
    id                    = Column(Integer, primary_key=True, index=True)
    user_id               = Column(Integer, ForeignKey("users.id"))
    route_id              = Column(Integer, ForeignKey("routes.id"))
    completed_checkpoints = Column(JSON, default=[])
    status                = Column(String, default="not_started")
    started_at            = Column(DateTime, nullable=True)
    completed_at          = Column(DateTime, nullable=True)
    user                  = relationship("User", back_populates="progress")

class Batch(Base):
    __tablename__ = "batches"
    id           = Column(Integer, primary_key=True, index=True)
    route_id     = Column(Integer, ForeignKey("routes.id"))
    creator_id   = Column(Integer, ForeignKey("users.id"))
    title        = Column(String)
    start_date   = Column(String)
    end_date     = Column(String)
    max_riders   = Column(Integer, default=10)
    description  = Column(Text, default="")
    status       = Column(String, default="open")  # open/full/completed
    created_at   = Column(DateTime, server_default=func.now())
    route        = relationship("Route", back_populates="batches")
    members      = relationship("BatchMember", back_populates="batch")
    messages     = relationship("Message", back_populates="batch")

class BatchMember(Base):
    __tablename__ = "batch_members"
    id        = Column(Integer, primary_key=True, index=True)
    batch_id  = Column(Integer, ForeignKey("batches.id"))
    user_id   = Column(Integer, ForeignKey("users.id"))
    role      = Column(String, default="rider")  # leader/sweep/rider
    joined_at = Column(DateTime, server_default=func.now())
    batch     = relationship("Batch", back_populates="members")
    user      = relationship("User", back_populates="batches")

class Message(Base):
    __tablename__ = "messages"
    id         = Column(Integer, primary_key=True, index=True)
    batch_id   = Column(Integer, ForeignKey("batches.id"))
    user_id    = Column(Integer, ForeignKey("users.id"))
    content    = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    batch      = relationship("Batch", back_populates="messages")
    user       = relationship("User", back_populates="messages")

class Badge(Base):
    __tablename__ = "badges"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    badge_type = Column(String)
    earned_at  = Column(DateTime, server_default=func.now())
    user       = relationship("User", back_populates="badges")