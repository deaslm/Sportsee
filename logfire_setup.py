# Pydantic Logfire pour tracer la chaîne RAG/LLM pas à pas.
# Chaque question est visible en temps réel dans le dashboard Logfire : décision de routage,
# recherche FAISS, génération et exécution SQL, rédaction de la réponse, validation Pydantic.

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
    Enveloppe la chaîne RAG/SQL avec des traces Logfire.
    - Valide la question avec Pydantic avant d'appeler la chaîne
    - Trace chaque étape de la chaîne (routage, recherche, SQL, rédaction)
    - Valide la sortie avec Pydantic avant de la retourner
    """

    # Trace tout l'appel
    with logfire.span("rag_pipeline", question=question, categorie=categorie):

        # Trace la validation de l'entrée
        with logfire.span("validation_entree"):
            entree = QuestionEntree(question=question)

        # Trace l'exécution de toute la chaîne (routage, recherche, SQL, rédaction)
        with logfire.span("execution_chaine"):
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