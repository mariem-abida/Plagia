# app/routes/analysis.py
from fastapi import APIRouter, Depends
from app.services.analysis_service import AnalysisService
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/student", tags=["Student"])

@router.get("/analyses")
def get_student_analyses(current_user=Depends(get_current_user)):
    """
    Retourne les analyses du student connecté
    """
    return AnalysisService.get_analyses_by_user_id(current_user["id"])
