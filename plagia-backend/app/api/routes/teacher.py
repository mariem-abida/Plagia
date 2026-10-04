from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.analysis import Analysis

router = APIRouter(prefix="/teacher", tags=["Teacher"])


@router.get("/checks")
def get_teacher_checks(db: Session = Depends(get_db)):
    analyses = db.query(Analysis).order_by(Analysis.created_at.desc()).all()

    return [
        {
            "id": a.id,
            "filename": a.filename,
            "plagiarism_percent": a.plagiarism_percent,
            "ai_percent": a.ai_percent,
            "decision": a.decision,
            "created_at": a.created_at
        }
        for a in analyses
    ]
