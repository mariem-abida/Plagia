from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.analysis import Analysis

from app.services.plagiarism_service import (
    save_upload_file,
    detect_plagiarism,
    build_corpus_index
)

router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])


@router.post("/index-corpus")
def index_corpus():
    return build_corpus_index()


@router.post("/detect")
async def detect(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # 1️⃣ Sauvegarder le fichier
        path = save_upload_file(file)

        # 2️⃣ Lancer la détection IA
        result = detect_plagiarism(path, top_k=5)

        # 3️⃣ Sauvegarder en base
        analysis = Analysis(
            filename=file.filename,
            file_path=path,
            plagiarism_percent=result.get("plagiarism_percent", 0),
            ai_percent=result.get("ai_percent"),
            decision=result.get("decision", "A_VERIFIER")
        )

        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        # 4️⃣ Retourner le résultat au frontend
        return {
            "id": analysis.id,
            "filename": analysis.filename,
            "plagiarism_percent": analysis.plagiarism_percent,
            "ai_percent": analysis.ai_percent,
            "decision": analysis.decision,
            "created_at": analysis.created_at
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
