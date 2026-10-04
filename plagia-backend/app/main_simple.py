from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Plag'IA Detection API",
    description="API pour la détection de plagiat intelligente",   
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@app.get("/")
async def root():
    return {"message": "Bienvenue sur Plag'IA Detection API"}
@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Plag'IA Backend"}

@app.get("/api/test")
async def test_backend():
    return {"message": "Backend FastAPI is working perfectly!", "status": "success"}

@app.get("/api/test-db")
async def test_database():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()
        cur.close()
        conn.close()
        return {
            "status": "success", 
            "message": "Database connected successfully",
            "database_version": version[0]
        }
    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}

# Vérifier si les tables existent
@app.get("/api/check-tables")
async def check_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier la table users
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            );
        """)
        users_exists = cur.fetchone()[0]
        
        # Vérifier la table documents
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'documents'
            );
        """)
        documents_exists = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "tables": {
                "users": users_exists,
                "documents": documents_exists
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Error checking tables: {str(e)}"}

# GET pour récupérer les utilisateurs
@app.get("/api/users")
async def get_users():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, email, full_name, created_at FROM users")
        users = cur.fetchall()
        
        # Convertir en format JSON
        users_list = []
        for user in users:
            users_list.append({
                "id": user[0],
                "email": user[1],
                "full_name": user[2],
                "created_at": user[3].isoformat() if user[3] else None
            })
            
        cur.close()
        conn.close()
        
        return {"status": "success", "users": users_list}
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch users: {str(e)}"}

# POST pour l'inscription
@app.post("/api/register")
async def register_user(
    email: str = Form(...),
    password: str = Form(...), 
    full_name: str = Form(...)
):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier si l'email existe déjà
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return {"status": "error", "message": "Email already exists"}
        
        # En production, hasher le mot de passe avec bcrypt!
        cur.execute(
            "INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, %s) RETURNING id",
            (email, password, full_name)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "success", "user_id": user_id, "message": "User registered successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Registration failed: {str(e)}"}

# Endpoint pour l'upload de fichiers
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    return {
        "filename": file.filename,
        "message": "File upload endpoint ready for plagiarism detection"
    }
# Endpoint GET pour tester l'inscription rapidement
@app.get("/api/register-test")
async def register_test():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        email = "test@example.com"
        password = "123456"
        full_name = "Test User"
        
        # Vérifier si l'email existe déjà
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return {"status": "error", "message": "Email already exists"}
        
        cur.execute(
            "INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, %s) RETURNING id",
            (email, password, full_name)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "success", "user_id": user_id, "message": "Test user registered successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Registration failed: {str(e)}"}