# app/services/auth_service.py

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
import hashlib

from dotenv import load_dotenv
from app.models.user import User  # ✅ on utilise directement le modèle

load_dotenv()

# Configuration de sécurité
SECRET_KEY = os.getenv("SECRET_KEY", "votre-secret-key-de-developpement-changez-en-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

print("🔑 AuthService chargé avec SHA256 (sans bcrypt)")

class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie le mot de passe avec SHA256"""
        return AuthService.get_password_hash(plain_password) == hashed_password

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash le mot de passe avec SHA256 - pour développement seulement"""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str):
        """Authentifie un utilisateur via son email et mot de passe"""
        print(f"🔐 Authentification pour: {email}")
        
        # ⬇️ on ne passe plus par UserService
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print("❌ Utilisateur non trouvé")
            return False
        
        print(f"🔑 Vérification mot de passe: {password[:2]}...")
        print(f"🔑 Hash stocké: {user.password_hash[:20]}...")
        
        if not AuthService.verify_password(password, user.password_hash):
            print("❌ Mot de passe incorrect")
            return False
        
        print("✅ Authentification réussie")
        return user

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta = None):
        """Crée un token JWT"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str):
        """Vérifie un token JWT et retourne l'email (sub)"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None
            return email
        except JWTError as e:
            print(f"❌ Erreur JWT: {e}")
            return None

    @staticmethod
    def get_current_user(db: Session, token: str):
        """Récupère l'utilisateur courant à partir du token"""
        email = AuthService.verify_token(token)
        if email is None:
            return None
        
        try:
            # on récupère directement l'utilisateur par email
            return db.query(User).filter(User.email == email).first()
        except Exception as e:
            print(f"❌ Erreur récupération utilisateur: {e}")
            return None
