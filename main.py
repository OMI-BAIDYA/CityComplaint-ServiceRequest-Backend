from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

from database import SessionLocal, engine
from models import Categories, Users
from router import admin, auth

import models


app = FastAPI(
    title="City Complaint & Service Request Platform"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


models.Base.metadata.create_all(bind=engine)


def seed_data():
    db = SessionLocal()

    try:
        if db.query(Users).count() == 0:
            c = CryptContext(
                schemes=["bcrypt"],
                deprecated="auto",
            )

            db.add(
                Users(
                    email="admin@cityservice.com",
                    username="admin",
                    firstname="City",
                    lastname="Admin",
                    hash_password=c.hash("admin123"),
                    role="admin",
                    is_active=True,
                )
            )

            db.add(
                Users(
                    email="user@cityservice.com",
                    username="user",
                    firstname="Normal",
                    lastname="User",
                    hash_password=c.hash("user123"),
                    role="user",
                    is_active=True,
                )
            )

        if db.query(Categories).count() == 0:
            categories = [
                (
                    "Road & Traffic",
                    "Road, traffic and street problems",
                ),
                (
                    "Waste Management",
                    "Garbage and waste collection",
                ),
                (
                    "Water & Drainage",
                    "Water supply and drainage",
                ),
                (
                    "Electricity",
                    "Street and public electricity issues",
                ),
                (
                    "Public Safety",
                    "Safety and public area concerns",
                ),
                (
                    "Other",
                    "Other city services",
                ),
            ]

            for name, description in categories:
                db.add(
                    Categories(
                        name=name,
                        description=description,
                    )
                )

        db.commit()

    finally:
        db.close()


seed_data()


app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {
        "message": "City Complaint & Service Request Platform API"
    }