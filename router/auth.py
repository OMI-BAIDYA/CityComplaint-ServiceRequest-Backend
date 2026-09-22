from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from database import SessionLocal
from models import (
    PasswordResets,
    RefreshTokens,
    Users,
)


router = APIRouter()

bcrypt_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

oauth2_bearer = OAuth2PasswordBearer(
    tokenUrl="login"
)

SECRET_KEY = "city-service-platform-secret-key-change-in-production"
ALGORITHM = "HS256"


class CreateUser(BaseModel):
    email: EmailStr
    username: str = Field(
        min_length=3,
        max_length=50,
    )
    firstname: str = Field(
        min_length=1,
        max_length=50,
    )
    lastname: str = Field(
        min_length=1,
        max_length=50,
    )
    password: str = Field(min_length=6)
    role: str = "user"


class UpdateUser(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
    )
    firstname: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    lastname: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
    )


class UpdatePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


def create_access_token(user):
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=30
    )

    return jwt.encode(
        {
            "sub": user.username,
            "id": user.id,
            "role": user.role,
            "exp": exp,
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user, db):
    token = secrets.token_urlsafe(48)
    exp = datetime.utcnow() + timedelta(days=7)

    db.add(
        RefreshTokens(
            user_id=user.id,
            token=token,
            expires_at=exp,
        )
    )

    db.commit()

    return token


def get_current_user(
    token: Annotated[str, Depends(oauth2_bearer)]
):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        if (
            payload.get("id") is None
            or payload.get("sub") is None
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
            )

        return {
            "id": payload["id"],
            "username": payload["sub"],
            "role": payload.get("role", "user"),
        }

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token expired or invalid",
        )


user_dependency = Annotated[
    dict,
    Depends(get_current_user),
]


@router.post("/createuser")
def create_user(
    db: db_dependency,
    new_user: CreateUser,
):
    if (
        db.query(Users)
        .filter(Users.username == new_user.username)
        .first()
    ):
        raise HTTPException(
            400,
            "Username already exists",
        )

    if (
        db.query(Users)
        .filter(Users.email == new_user.email)
        .first()
    ):
        raise HTTPException(
            400,
            "Email already exists",
        )

    role = (
        new_user.role
        if new_user.role in ["user", "admin"]
        else "user"
    )

    db.add(
        Users(
            email=new_user.email,
            username=new_user.username,
            firstname=new_user.firstname,
            lastname=new_user.lastname,
            hash_password=bcrypt_context.hash(
                new_user.password
            ),
            role=role,
            is_active=True,
        )
    )

    db.commit()

    return {
        "message": "User created successfully"
    }


@router.post("/login")
def login_user(
    db: db_dependency,
    form_data: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
):
    user = (
        db.query(Users)
        .filter(
            Users.username == form_data.username,
            Users.is_active == True,
        )
        .first()
    )

    if not user or not bcrypt_context.verify(
        form_data.password,
        user.hash_password,
    ):
        raise HTTPException(
            401,
            "Invalid username or password",
        )

    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(
            user,
            db,
        ),
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(
    db: db_dependency,
    request: RefreshRequest,
):
    item = (
        db.query(RefreshTokens)
        .filter(
            RefreshTokens.token == request.refresh_token,
            RefreshTokens.revoked == False,
        )
        .first()
    )

    if (
        not item
        or item.expires_at < datetime.utcnow()
    ):
        raise HTTPException(
            401,
            "Refresh token expired or invalid",
        )

    user = (
        db.query(Users)
        .filter(
            Users.id == item.user_id,
            Users.is_active == True,
        )
        .first()
    )

    if not user:
        raise HTTPException(
            401,
            "User not found",
        )

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    db: db_dependency,
    request: RefreshRequest,
):
    item = (
        db.query(RefreshTokens)
        .filter(
            RefreshTokens.token == request.refresh_token
        )
        .first()
    )

    if item:
        item.revoked = True
        db.commit()

    return {
        "message": "Logged out successfully"
    }


@router.get("/user")
def get_user(
    user: user_dependency,
    db: db_dependency,
):
    x = (
        db.query(Users)
        .filter(Users.id == user["id"])
        .first()
    )

    if not x:
        raise HTTPException(
            404,
            "User not found",
        )

    return {
        "id": x.id,
        "email": x.email,
        "username": x.username,
        "firstname": x.firstname,
        "lastname": x.lastname,
        "role": x.role,
        "is_active": x.is_active,
    }


@router.put("/edituser")
def edit_user(
    user: user_dependency,
    db: db_dependency,
    update: UpdateUser,
):
    x = (
        db.query(Users)
        .filter(Users.id == user["id"])
        .first()
    )

    if not x:
        raise HTTPException(
            404,
            "User not found",
        )

    data = update.model_dump(
        exclude_unset=True
    )

    if (
        "username" in data
        and db.query(Users)
        .filter(
            Users.username == data["username"],
            Users.id != x.id,
        )
        .first()
    ):
        raise HTTPException(
            400,
            "Username already exists",
        )

    if (
        "email" in data
        and db.query(Users)
        .filter(
            Users.email == data["email"],
            Users.id != x.id,
        )
        .first()
    ):
        raise HTTPException(
            400,
            "Email already exists",
        )

    for key, value in data.items():
        setattr(x, key, value)

    db.commit()

    return {
        "message": "Profile updated successfully"
    }


@router.put("/passwordchange")
def password_change(
    user: user_dependency,
    db: db_dependency,
    update: UpdatePassword,
):
    x = (
        db.query(Users)
        .filter(Users.id == user["id"])
        .first()
    )

    if not x or not bcrypt_context.verify(
        update.current_password,
        x.hash_password,
    ):
        raise HTTPException(
            401,
            "Current password is incorrect",
        )

    x.hash_password = bcrypt_context.hash(
        update.new_password
    )

    db.commit()

    return {
        "message": "Password updated successfully"
    }


@router.post("/forgot-password")
def forgot_password(
    db: db_dependency,
    request: ForgotPassword,
):
    x = (
        db.query(Users)
        .filter(Users.email == request.email)
        .first()
    )

    if not x:
        return {
            "message": (
                "If the email exists, "
                "a reset token has been created"
            )
        }

    token = secrets.token_urlsafe(32)

    db.add(
        PasswordResets(
            user_id=x.id,
            token=token,
            expires_at=datetime.utcnow()
            + timedelta(minutes=15),
        )
    )

    db.commit()

    return {
        "message": "Reset token created",
        "reset_token": token,
    }


@router.post("/reset-password")
def reset_password(
    db: db_dependency,
    request: ResetPassword,
):
    x = (
        db.query(PasswordResets)
        .filter(
            PasswordResets.token == request.token,
            PasswordResets.used == False,
        )
        .first()
    )

    if (
        not x
        or x.expires_at < datetime.utcnow()
    ):
        raise HTTPException(
            400,
            "Reset token expired or invalid",
        )

    user = (
        db.query(Users)
        .filter(Users.id == x.user_id)
        .first()
    )

    user.hash_password = bcrypt_context.hash(
        request.new_password
    )

    x.used = True

    db.commit()

    return {
        "message": "Password reset successfully"
    }