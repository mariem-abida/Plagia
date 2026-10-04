# app/api/routes/files.py
from fastapi import APIRouter
from typing import List
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/files", tags=["files"])


# 🔹 Schéma Pydantic de sortie (ce que le front recevra)
class FileItem(BaseModel):
    id: int
    filename: str
    user_email: str
    created_at: datetime
    status: str        # "ACCEPTED" | "REJECTED" | "PENDING"
    similarity: int    # pourcentage
    size_kb: int       # taille du fichier


# 🔹 Endpoint GET /api/files/ (données simulées pour l’instant)
@router.get("/", response_model=List[FileItem])
def list_files():
    return [
        FileItem(
            id=1,
            filename="rapport_stage_erp.pdf",
            user_email="mohamed@example.com",
            created_at=datetime(2025, 12, 8, 20, 0),
            status="ACCEPTED",
            similarity=45,
            size_kb=820
        ),
        FileItem(
            id=2,
            filename="memoire_data_science.pdf",
            user_email="test1@example.com",
            created_at=datetime(2025, 12, 8, 21, 30),
            status="REJECTED",
            similarity=72,
            size_kb=1450
        ),
        FileItem(
            id=3,
            filename="article_ia.docx",
            user_email="prof@example.com",
            created_at=datetime(2025, 12, 8, 22, 10),
            status="PENDING",
            similarity=23,
            size_kb=560
        ),
    ]
