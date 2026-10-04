from fastapi import FastAPI, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import hashlib
import datetime
from typing import Optional

# Essayer d'importer JWT (différents noms possibles)
try:
    import jwt
except ImportError:
    try:
        from jose import jwt
    except ImportError:
        raise ImportError("Install either 'pyjwt' or 'python-jose' package")

app = FastAPI(title="Plagia API", version="1.0.0")

# CORS pour Angular
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"

# Base de données SQLite
def get_db():
    conn = sqlite3.connect('plagia.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect('plagia.db')
    cursor = conn.cursor()
    
    # Table users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table pour les détections de plagiat
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plagiarism_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            document_name TEXT,
            document_text TEXT,
            ai_probability REAL,
            result_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Créer un admin par défaut
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO users (email, password_hash, full_name, role) 
        VALUES (?, ?, ?, ?)
    ''', ("admin@plagia.com", admin_hash, "Administrator", "admin"))
    
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()
    print("✅ Database initialized successfully")

# Routes d'authentification
@app.post("/auth/register")
def register_user(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role: str = Form("student"),
    db: sqlite3.Connection = Depends(get_db)
):
    # Vérifier si l'email existe déjà
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    # Hasher le mot de passe
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Insérer l'utilisateur
    cursor = db.execute(
        "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
        (email, password_hash, full_name, role)
    )
    db.commit()
    
    user_id = cursor.lastrowid
    
    return {
        "message": "Utilisateur créé avec succès",
        "user_id": user_id,
        "user": {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role": role
        }
    }

@app.post("/auth/login")
def login_user(
    email: str = Form(...),
    password: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    user = db.execute(
        "SELECT * FROM users WHERE email = ? AND password_hash = ? AND is_active = 1",
        (email, password_hash)
    ).fetchone()
    
    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    
    # Créer un token JWT
    token_data = {
        "sub": user["email"],
        "user_id": user["id"],
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    
    token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"]
        }
    }

# Routes utilisateurs
@app.get("/users/me")
def get_current_user(token: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        
        user = db.execute(
            "SELECT id, email, full_name, role, created_at FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Utilisateur non trouvé")
        
        return dict(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")

@app.get("/users")
def get_all_users(token: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        
        users = db.execute(
            "SELECT id, email, full_name, role, is_active, created_at FROM users"
        ).fetchall()
        
        return {"users": [dict(user) for user in users]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")

# Routes pour la détection de plagiat
@app.post("/plagiarism/check")
def check_plagiarism(
    token: str = Form(...),
    document_name: str = Form(...),
    document_text: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        
        # Simulation de détection d'IA (à remplacer par votre algorithme)
        ai_probability = len(document_text) % 100  # Simulation
        
        # Enregistrer le résultat
        cursor = db.execute(
            "INSERT INTO plagiarism_checks (user_id, document_name, document_text, ai_probability, result_data) VALUES (?, ?, ?, ?, ?)",
            (user_id, document_name, document_text, ai_probability, f"{{'ai_probability': {ai_probability}}}")
        )
        db.commit()
        
        check_id = cursor.lastrowid
        
        return {
            "check_id": check_id,
            "ai_probability": ai_probability,
            "is_likely_ai": ai_probability > 50,
            "message": f"Probabilité IA: {ai_probability}%"
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")

@app.get("/plagiarism/history")
def get_plagiarism_history(
    token: str,
    user_id: Optional[int] = None,  # Pour l'admin seulement
    db: sqlite3.Connection = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        current_user_id = payload.get("user_id")
        current_user_role = payload.get("role")
        
        # L'admin peut voir tout l'historique, les autres seulement le leur
        if current_user_role == "admin" and user_id:
            checks = db.execute(
                "SELECT * FROM plagiarism_checks WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
        else:
            checks = db.execute(
                "SELECT * FROM plagiarism_checks WHERE user_id = ? ORDER BY created_at DESC",
                (current_user_id,)
            ).fetchall()
        
        return {"checks": [dict(check) for check in checks]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")

# Routes générales
@app.get("/")
def read_root():
    return {"message": "Plagia Detection API", "status": "active"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)