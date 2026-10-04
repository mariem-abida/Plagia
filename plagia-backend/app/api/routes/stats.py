from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Pour l’instant : valeurs MOCK.
    Plus tard, on ira chercher dans la base (users, analyses, fichiers…)
    """
    return {
        "total_users": 12,
        "total_files": 34,
        "total_analyses": 28,
        "avg_similarity": 37,
    }
