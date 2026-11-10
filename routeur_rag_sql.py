# Routeur : le LLM choisit entre RAG (contexte textuel) et SQL (statistiques chiffrées), puis rédige la réponse
# 3 étapes explicites : 1) le LLM décide la source  2) Python appelle l'outil  3) le LLM répond à partir des preuves
import os
import re
from typing import Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from langchain_mistralai import ChatMistralAI
from utils.vector_store import VectorStoreManager
from sql_tool import repondre_sql
import time
import logfire

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

NB_EXTRAITS = 5                       # nombre d'extraits FAISS récupérés

vs = VectorStoreManager()             # index FAISS
llm = ChatMistralAI(model="mistral-large-latest", api_key=KEY, temperature=0)


# MODÈLE PYDANTIC : décision de routage renvoyée par le LLM 
class DecisionRoutage(BaseModel):
    source: Literal["rag", "sql", "mixte"]
    question_rag: Optional[str] = None     # partie contextuelle de la question
    question_sql: Optional[str] = None     # partie chiffrée de la question


# ÉTAPE 1 : LE LLM DÉCIDE QUELLE SOURCE UTILISER
PROMPT_ROUTAGE = """Tu es l'aiguilleur d'un assistant NBA qui dispose de deux sources :
- "rag" : des discussions de fans (Reddit) sur le contexte : règles, play-in, playoffs, Finals, opinions, descriptions de joueurs ou d'équipes.
- "sql" : une base de statistiques chiffrées de la saison régulière : points, pourcentages, rebonds, passes, classements.

Choisis "rag", "sql", ou "mixte" si la question demande les deux.
Pour "mixte", découpe la question en une partie contextuelle (question_rag) et une partie chiffrée (question_sql).
Pour "rag" ou "sql", recopie la question dans le champ correspondant.

Réponds uniquement avec un objet JSON, sans texte autour :
{{"source": "...", "question_rag": "..." ou null, "question_sql": "..." ou null}}

Question : {question}"""


def decider_source(question: str) -> DecisionRoutage:
    """Le LLM classe la question ; en cas de réponse illisible, on interroge les deux sources par sécurité."""
    texte = llm.invoke(PROMPT_ROUTAGE.format(question=question)).content
    json_trouve = re.search(r"\{.*\}", texte, flags=re.DOTALL)      # isole le JSON si le LLM ajoute du texte
    try:
        return DecisionRoutage.model_validate_json(json_trouve.group(0))
    except (AttributeError, ValidationError):
        return DecisionRoutage(source="mixte", question_rag=question, question_sql=question)


# ÉTAPE 2 : LES OUTILS (renvoient des preuves brutes, pas de réponse rédigée)
def outil_rag(question: str) -> list[str]:
    """Renvoie les extraits FAISS les plus proches de la question."""
    return [c["text"] for c in vs.search(question, k=NB_EXTRAITS)]


def outil_sql(question: str) -> str:
    """Renvoie la requête SQL générée et les lignes réellement obtenues."""
    return repondre_sql(question)


# ÉTAPE 3 : LE LLM RÉDIGE LA RÉPONSE À PARTIR DES PREUVES
PROMPT_REPONSE = """Tu es un assistant expert en basketball NBA. Réponds en français à la question,
uniquement à partir des informations ci-dessous : n'invente aucun chiffre ni aucun fait.
Réponds en 3 phrases maximum, sans titres ni listes, en ne gardant que ce qui répond directement à la question.
Les statistiques de la base concernent la saison régulière 2024-25 : c'est elle que désigne « cette saison ».
Si une information manque, dis-le clairement.

Informations disponibles :
{preuves}

Question : {question}
Réponse :"""


def repondre_avec_contextes(question: str, tentatives: int = 4) -> tuple[Optional[str], list[str], list[str]]:
    """Pipeline complet. Renvoie (réponse, contextes réellement utilisés, outils appelés).
    Chaque étape est tracée dans Logfire. En cas d'erreur (ex. limite de requêtes de l'API),
    réessaie après une pause. La réponse vaut None si toutes les tentatives échouent."""
    for essai in range(1, tentatives + 1):
        try:
            with logfire.span("decision_routage"):
                decision = decider_source(question)
                logfire.info("source_choisie", source=decision.source,
                             question_rag=decision.question_rag, question_sql=decision.question_sql)

            contextes, outils_appeles = [], []
            if decision.source in ("rag", "mixte"):
                with logfire.span("recherche_faiss"):
                    extraits = outil_rag(decision.question_rag or question)
                    logfire.info("extraits_recuperes", nb_extraits=len(extraits))
                contextes += extraits                                       # un contexte par extrait
                outils_appeles.append("outil_rag")
            if decision.source in ("sql", "mixte"):
                with logfire.span("outil_sql"):
                    contextes.append(outil_sql(decision.question_sql or question))  # requête + lignes
                outils_appeles.append("outil_sql")

            with logfire.span("redaction_reponse"):
                preuves = "\n\n---\n\n".join(contextes)
                reponse = llm.invoke(PROMPT_REPONSE.format(preuves=preuves, question=question)).content
            return reponse, contextes, outils_appeles
        except Exception as e:
            logfire.warn("echec_pipeline", tentative=essai, erreur=str(e))
            print(f"  Échec du pipeline (tentative {essai}/{tentatives}) : {e}")
            if essai < tentatives:
                time.sleep(20 * essai)         # pause croissante : 20 s, 40 s, puis 60 s
    return None, [], []


def repondre(question: str) -> Optional[str]:
    """Version utilisateur : renvoie uniquement la réponse finale."""
    reponse, _, _ = repondre_avec_contextes(question)
    return reponse


if __name__ == "__main__":
    questions_test = [
        "Qu'est-ce que le play-in tournament NBA ?",                                       # -> rag
        "Combien de points par match marque Shai Gilgeous-Alexander ?",                    # -> sql
        "Qu'est-ce que le play-in et combien de points marque Zach LaVine cette saison ?", # -> mixte
    ]
    for q in questions_test:
        reponse, contextes, outils_appeles = repondre_avec_contextes(q)
        print(f"\nQuestion : {q}")
        print(f"Outils   : {outils_appeles}")
        print(f"Réponse  : {reponse}")