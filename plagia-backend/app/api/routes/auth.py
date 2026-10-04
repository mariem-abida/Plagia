from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database.database import get_db
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    try:
        print(f"📝 Tentative d'inscription pour: {user_data.email}")

        db_user = UserService.get_user_by_email(db, email=user_data.email)
        if db_user:
            raise HTTPException(status_code=400, detail="Email déjà enregistré")

        user = UserService.create_user(db=db, user=user_data)
        print(f"✅ Utilisateur créé avec ID: {user.id}")

        return user

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur lors de l'inscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    try:
        print(f"🔐 Tentative de connexion pour: {form_data.username}")

        user = AuthService.authenticate_user(db, form_data.username, form_data.password)
        if not user:
            print("❌ Échec d'authentification")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou mot de passe incorrect",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # durée de vie token
        access_token_expires = timedelta(minutes=30)

        # rôle en string
        role_str = getattr(user.role, "value", user.role)

        # ✅ IMPORTANT : mettre role dans le token
        access_token = AuthService.create_access_token(
            data={"sub": user.email, "role": role_str},
            expires_delta=access_token_expires
        )

        print(f"✅ Connexion réussie pour: {user.email} | rôle={role_str}")

        # ✅ renvoyer role + email (utile pour le front)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": role_str,
            "email": user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur lors de la connexion: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur serveur")
