# Pydantic pour valider les entrées/sorties du pipeline RAG (garantit que les données sont bien formées à chaque étape)

from pydantic import BaseModel, Field, field_validator
from typing import List


class QuestionEntree(BaseModel):
    """Valide qu'une question est bien formée avant d'interroger le RAG."""

    # La question doit faire au moins 5 caractères
    question: str = Field(..., min_length=5, description="Question posée au RAG")

    @field_validator("question")
    @classmethod
    def question_non_vide(cls, v):
        # Rejette les questions vides ou composées uniquement d'espaces
        if not v.strip():
            raise ValueError("La question ne peut pas être vide.")
        return v.strip()


class ChunkRecupere(BaseModel):
    """Représente un chunk de texte retourné par la recherche vectorielle FAISS."""

    # Le texte du chunk doit exister (non vide)
    text: str = Field(..., min_length=1, description="Contenu du chunk récupéré")


class ReponsRAG(BaseModel):
    """Valide la sortie complète du pipeline RAG avant affichage ou évaluation."""

    question: str
    # La réponse générée par le LLM doit exister
    reponse: str = Field(..., min_length=1, description="Réponse générée par le LLM")
    # Au moins un chunk doit avoir été utilisé pour construire la réponse
    chunks: List[ChunkRecupere] = Field(..., min_length=1, description="Chunks utilisés")