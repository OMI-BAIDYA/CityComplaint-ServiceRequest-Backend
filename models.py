from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from database import Base


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    firstname = Column(String)
    lastname = Column(String)
    hash_password = Column(String)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class Categories(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, default="")
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class Complaints(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
    )
    location = Column(String)
    status = Column(
        String,
        default="pending",
        index=True,
    )
    priority = Column(
        String,
        default="medium",
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
    )
    admin_note = Column(
        Text,
        default="",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class ServiceRequests(Base):
    __tablename__ = "service_requests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
    )
    location = Column(String)
    status = Column(
        String,
        default="pending",
        index=True,
    )
    priority = Column(
        String,
        default="medium",
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
    )
    admin_note = Column(
        Text,
        default="",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class RefreshTokens(Base):
    __tablename__ = "refresh_tokens"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
    )
    token = Column(
        String,
        unique=True,
        index=True,
    )
    expires_at = Column(DateTime)
    revoked = Column(
        Boolean,
        default=False,
    )


class PasswordResets(Base):
    __tablename__ = "password_resets"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
    )
    token = Column(
        String,
        unique=True,
        index=True,
    )
    expires_at = Column(DateTime)
    used = Column(
        Boolean,
        default=False,
    )