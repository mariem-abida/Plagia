from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.database import get_db
from app.schemas.user import UserResponse, UserCreate, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


# 🔹 READ – liste de tous les utilisateurs
@router.get("/", response_model=List[UserResponse])
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = UserService.get_users(db, skip=skip, limit=limit)
    return users


# 🔹 READ – un utilisateur par ID
@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = UserService.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# 🔹 CREATE – créer un utilisateur (version admin)
# (Tu peux garder /api/auth/register pour l'inscription classique)
@router.post("/", response_model=UserResponse)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    user = UserService.create_user(db, user=user_data)
    return user


# 🔹 UPDATE – modifier un utilisateur
@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, update_data: UserUpdate, db: Session = Depends(get_db)):
    user = UserService.update_user(db, user_id=user_id, update_data=update_data)
    return user


# 🔹 DELETE – supprimer un utilisateur
@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    result = UserService.delete_user(db, user_id=user_id)
    return result
