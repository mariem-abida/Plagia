from sqlalchemy.orm import Session
from sqlalchemy import inspect
from fastapi import HTTPException, status
from datetime import datetime

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.auth_service import AuthService


# ---------- Fonctions "simples" ----------

def check_tables_exist(db: Session):
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    return {"users": "users" in tables}


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()


def get_user_by_id(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return user


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user: UserCreate):
    existing = get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà utilisé",
        )

    hashed_pwd = AuthService.get_password_hash(user.password)

    role = user.role or UserRole.STUDENT

    new_user = User(
        email=user.email,
        full_name=user.full_name,
        password_hash=hashed_pwd,
        role=role,
        is_verified=False,
        is_active=True,
        last_login=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse.model_validate(new_user, from_attributes=True)

def update_user(db: Session, user_id: int, update_data: UserUpdate):
    user = get_user_by_id(db, user_id)

    if update_data.full_name is not None:
        user.full_name = update_data.full_name
    if update_data.is_active is not None:
        user.is_active = update_data.is_active

    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)
    db.delete(user)
    db.commit()
    return {"message": "Utilisateur supprimé avec succès"}


# ---------- Classe "façade" pour garder le même usage ----------

class UserService:
    check_tables_exist = staticmethod(check_tables_exist)
    get_users = staticmethod(get_users)
    get_user_by_id = staticmethod(get_user_by_id)
    get_user_by_email = staticmethod(get_user_by_email)
    create_user = staticmethod(create_user)
    update_user = staticmethod(update_user)
    delete_user = staticmethod(delete_user)
