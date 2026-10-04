from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.routes import files   # ⬅️ ajouter ceci
from app.api.routes import stats
from app.api.routes import student
from app.api.routes import teacher

from app.database.database import get_db, engine, Base
from app.models.user import User
from app.api.routes import auth, users, stats  # <-- ajouter stats
from app.routes.plagiarism import router as plagiarism_router

# Créer les tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Plag'IA Detection API",
    description="API pour la détection de plagiat intelligente",   
    version="1.0.0"

)
app.include_router(plagiarism_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)   

# Inclure les routes
app.include_router(users.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(files.router, prefix="/api")  # ⬅️ nouveau
app.include_router(stats.router, prefix="/api")
app.include_router(student.router, prefix="/api")
app.include_router(teacher.router, prefix="/api")

# Routes de base
@app.get("/")
async def root():
    return {"message": "Bienvenue sur Plag'IA Detection API"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Plag'IA Backend"}

@app.get("/api/test-db")
async def test_database(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT version()"))
        version = result.scalar()
        return {
            "status": "success", 
            "message": "Database connected successfully",
            "database_version": version
        }
    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}

@app.get("/api/check-tables")
async def check_tables(db: Session = Depends(get_db)):
    from app.services.user_service import UserService
    tables_status = UserService.check_tables_exist(db)
    return {
        "status": "success",
        "tables": tables_status
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)