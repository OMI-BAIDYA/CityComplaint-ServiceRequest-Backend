from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Categories, Complaints, ServiceRequests, Users
from router.auth import get_current_user


router = APIRouter()


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = ""


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=80,
    )
    description: Optional[str] = None


class ReportCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=5)
    category_id: int
    location: str = Field(min_length=2, max_length=200)
    priority: str = "medium"


class ReportUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=150,
    )
    description: Optional[str] = Field(
        default=None,
        min_length=5,
    )
    category_id: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    admin_note: Optional[str] = None


class UserAdminUpdate(BaseModel):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


def admin_only(user):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")


def serialize(x):
    return {
        "id": x.id,
        "title": x.title,
        "description": x.description,
        "category_id": x.category_id,
        "location": x.location,
        "status": x.status,
        "priority": x.priority,
        "user_id": x.user_id,
        "admin_note": x.admin_note,
        "created_at": x.created_at.isoformat(),
        "updated_at": x.updated_at.isoformat(),
    }


def list_reports(
    db,
    model,
    user,
    search,
    category_id,
    status,
    start_date,
    end_date,
    sort_by,
    sort_order,
    page,
    page_size,
):
    q = db.query(model)

    if user.get("role") != "admin":
        q = q.filter(model.user_id == user["id"])

    if search:
        q = q.filter(
            or_(
                model.title.ilike(f"%{search}%"),
                model.description.ilike(f"%{search}%"),
                model.location.ilike(f"%{search}%"),
            )
        )

    if category_id:
        q = q.filter(model.category_id == category_id)

    if status:
        q = q.filter(model.status == status)

    if start_date:
        q = q.filter(
            model.created_at >= datetime.fromisoformat(start_date)
        )

    if end_date:
        q = q.filter(
            model.created_at <= datetime.fromisoformat(end_date)
        )

    col = getattr(model, sort_by, model.created_at)

    q = q.order_by(
        asc(col) if sort_order == "asc" else desc(col)
    )

    total = q.count()

    items = (
        q.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [serialize(x) for x in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


def create_report(db, model, user, data):
    x = model(
        **data.model_dump(),
        user_id=user["id"],
        status="pending",
        admin_note="",
    )

    db.add(x)
    db.commit()
    db.refresh(x)

    return serialize(x)


def update_report(db, model, user, item_id, data):
    x = db.query(model).filter(model.id == item_id).first()

    if not x:
        raise HTTPException(404, "Record not found")

    if (
        user.get("role") != "admin"
        and x.user_id != user["id"]
    ):
        raise HTTPException(403, "Access denied")

    vals = data.model_dump(exclude_unset=True)

    if user.get("role") != "admin":
        vals.pop("status", None)
        vals.pop("admin_note", None)

    for k, v in vals.items():
        setattr(x, k, v)

    x.updated_at = datetime.utcnow()

    db.commit()

    return serialize(x)


def delete_report(db, model, user, item_id):
    x = db.query(model).filter(model.id == item_id).first()

    if not x:
        raise HTTPException(404, "Record not found")

    if (
        user.get("role") != "admin"
        and x.user_id != user["id"]
    ):
        raise HTTPException(403, "Access denied")

    db.delete(x)
    db.commit()

    return {
        "message": "Record deleted successfully"
    }


@router.get("/categories")
def categories(db: db_dependency):
    return (
        db.query(Categories)
        .order_by(Categories.name.asc())
        .all()
    )


@router.post("/admin/categories")
def create_category(
    user: user_dependency,
    db: db_dependency,
    data: CategoryCreate,
):
    admin_only(user)

    if (
        db.query(Categories)
        .filter(Categories.name == data.name)
        .first()
    ):
        raise HTTPException(
            400,
            "Category already exists",
        )

    x = Categories(**data.model_dump())

    db.add(x)
    db.commit()
    db.refresh(x)

    return x


@router.put("/admin/categories/{category_id}")
def update_category(
    user: user_dependency,
    db: db_dependency,
    category_id: int,
    data: CategoryUpdate,
):
    admin_only(user)

    x = (
        db.query(Categories)
        .filter(Categories.id == category_id)
        .first()
    )

    if not x:
        raise HTTPException(
            404,
            "Category not found",
        )

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(x, k, v)

    db.commit()

    return x


@router.delete("/admin/categories/{category_id}")
def delete_category(
    user: user_dependency,
    db: db_dependency,
    category_id: int,
):
    admin_only(user)

    x = (
        db.query(Categories)
        .filter(Categories.id == category_id)
        .first()
    )

    if not x:
        raise HTTPException(
            404,
            "Category not found",
        )

    db.delete(x)
    db.commit()

    return {
        "message": "Category deleted successfully"
    }


@router.get("/complaints")
def complaints(
    user: user_dependency,
    db: db_dependency,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    return list_reports(
        db,
        Complaints,
        user,
        search,
        category_id,
        status,
        start_date,
        end_date,
        sort_by,
        sort_order,
        page,
        page_size,
    )


@router.post("/complaints")
def create_complaint(
    user: user_dependency,
    db: db_dependency,
    data: ReportCreate,
):
    return create_report(
        db,
        Complaints,
        user,
        data,
    )


@router.get("/complaints/{item_id}")
def complaint_details(
    user: user_dependency,
    db: db_dependency,
    item_id: int,
):
    x = (
        db.query(Complaints)
        .filter(Complaints.id == item_id)
        .first()
    )

    if (
        not x
        or (
            user.get("role") != "admin"
            and x.user_id != user["id"]
        )
    ):
        raise HTTPException(
            404,
            "Complaint not found",
        )

    return serialize(x)


@router.put("/complaints/{item_id}")
def update_complaint(
    user: user_dependency,
    db: db_dependency,
    item_id: int,
    data: ReportUpdate,
):
    return update_report(
        db,
        Complaints,
        user,
        item_id,
        data,
    )


@router.delete("/complaints/{item_id}")
def delete_complaint(
    user: user_dependency,
    db: db_dependency,
    item_id: int,
):
    return delete_report(
        db,
        Complaints,
        user,
        item_id,
    )


@router.get("/service-requests")
def service_requests(
    user: user_dependency,
    db: db_dependency,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    return list_reports(
        db,
        ServiceRequests,
        user,
        search,
        category_id,
        status,
        start_date,
        end_date,
        sort_by,
        sort_order,
        page,
        page_size,
    )


@router.post("/service-requests")
def create_service_request(
    user: user_dependency,
    db: db_dependency,
    data: ReportCreate,
):
    return create_report(
        db,
        ServiceRequests,
        user,
        data,
    )


@router.get("/service-requests/{item_id}")
def service_request_details(
    user: user_dependency,
    db: db_dependency,
    item_id: int,
):
    x = (
        db.query(ServiceRequests)
        .filter(ServiceRequests.id == item_id)
        .first()
    )

    if (
        not x
        or (
            user.get("role") != "admin"
            and x.user_id != user["id"]
        )
    ):
        raise HTTPException(
            404,
            "Service request not found",
        )

    return serialize(x)


@router.put("/service-requests/{item_id}")
def update_service_request(
    user: user_dependency,
    db: db_dependency,
    item_id: int,
    data: ReportUpdate,
):
    return update_report(
        db,
        ServiceRequests,
        user,
        item_id,
        data,
    )


@router.delete("/service-requests/{item_id}")
def delete_service_request(
    user: user_dependency,
    db: db_dependency,
    item_id: int,
):
    return delete_report(
        db,
        ServiceRequests,
        user,
        item_id,
    )


@router.get("/admin/users")
def admin_users(
    user: user_dependency,
    db: db_dependency,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    admin_only(user)

    q = db.query(Users)

    if search:
        q = q.filter(
            or_(
                Users.username.ilike(f"%{search}%"),
                Users.email.ilike(f"%{search}%"),
                Users.firstname.ilike(f"%{search}%"),
                Users.lastname.ilike(f"%{search}%"),
            )
        )

    total = q.count()

    items = (
        q.order_by(Users.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "id": x.id,
                "email": x.email,
                "username": x.username,
                "firstname": x.firstname,
                "lastname": x.lastname,
                "role": x.role,
                "is_active": x.is_active,
                "created_at": x.created_at.isoformat(),
            }
            for x in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.put("/admin/users/{user_id}")
def update_admin_user(
    user: user_dependency,
    db: db_dependency,
    user_id: int,
    data: UserAdminUpdate,
):
    admin_only(user)

    x = (
        db.query(Users)
        .filter(Users.id == user_id)
        .first()
    )

    if not x:
        raise HTTPException(
            404,
            "User not found",
        )

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(x, k, v)

    db.commit()

    return {
        "message": "User updated successfully"
    }


@router.delete("/admin/users/{user_id}")
def delete_admin_user(
    user: user_dependency,
    db: db_dependency,
    user_id: int,
):
    admin_only(user)

    if user_id == user["id"]:
        raise HTTPException(
            400,
            "You cannot delete your own account",
        )

    x = (
        db.query(Users)
        .filter(Users.id == user_id)
        .first()
    )

    if not x:
        raise HTTPException(
            404,
            "User not found",
        )

    db.delete(x)
    db.commit()

    return {
        "message": "User deleted successfully"
    }


@router.get("/admin/dashboard")
def dashboard(
    user: user_dependency,
    db: db_dependency,
):
    admin_only(user)

    return {
        "users": db.query(Users).count(),
        "complaints": db.query(Complaints).count(),
        "requests": db.query(ServiceRequests).count(),
        "pending_complaints": (
            db.query(Complaints)
            .filter(Complaints.status == "pending")
            .count()
        ),
        "pending_requests": (
            db.query(ServiceRequests)
            .filter(ServiceRequests.status == "pending")
            .count()
        ),
        "resolved_complaints": (
            db.query(Complaints)
            .filter(Complaints.status == "resolved")
            .count()
        ),
        "resolved_requests": (
            db.query(ServiceRequests)
            .filter(ServiceRequests.status == "resolved")
            .count()
        ),
    }