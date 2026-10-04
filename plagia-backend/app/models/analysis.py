from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)

    # infos fichier
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    # résultats IA
    plagiarism_percent = Column(Float, nullable=False)
    ai_percent = Column(Float, nullable=True)
    decision = Column(String, nullable=False)

    # métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)

    # utilisateur (étudiant)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", backref="analyses")
