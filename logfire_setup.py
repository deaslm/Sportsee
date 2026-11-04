# Pydantic Logfire pour tracer la chaîne RAG pas à pas.
# Chaque appel RAG (recherche FAISS + génération LLM) sera visible en temps réel dans le dashboard Logfire.

import os
import logfire
from dotenv import load_dotenv
from models import QuestionEntree, ReponsRAG, ChunkRecupere

load_dotenv()

# Initialisation de Logfire avec le token depuis .env
logfire.configure(
    token=os.getenv("LOGFIRE_TOKEN"),
    service_name="sportsee-rag"
)


def rag_trace(question: str, rag_fn, categorie: str = "non_classée") -> ReponsRAG:
    """
    Enveloppe la fonction RAG avec des traces Logfire.
    - Valide la question avec Pydantic avant d'appeler le RAG
    - Trace la recherche FAISS et la génération LLM
    - Valide la sortie avec Pydantic avant de retourner
    """

    # Validation de l'entrée via Pydantic
    entree = QuestionEntree(question=question)

    # Trace tout l'appel RAG
    with logfire.span("rag_pipeline", question=entree.question, categorie=categorie):

        # Trace la génération de la réponse
        with logfire.span("llm_generation"):
            reponse_texte, chunks_bruts = rag_fn(entree.question)
            logfire.info("reponse_generee", reponse=reponse_texte)

        # Trace la validation de la sortie
        with logfire.span("validation_sortie"):
            chunks_valides = [ChunkRecupere(text=c) for c in chunks_bruts]
            sortie = ReponsRAG(
                question=entree.question,
                reponse=reponse_texte,
                chunks=chunks_valides, )

    return sortie