# Évaluation RAGAS du système avant intégration SQL : RAG seul (recherche FAISS + génération)
# Même questions, même modèle que evaluate_ragas_apres.py
# Différence : l'ajout du routeur et de l'outil SQL
import os
import sys
import json
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from routeur_rag_sql import outil_rag, PROMPT_REPONSE, llm as llm_generation
from logfire_setup import rag_trace
import logfire

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

CHEMIN_QUESTIONS = "questions_test.json"
CHEMIN_RESULTATS = "resultats_ragas_avant.csv"
METRIQUES = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


# N'additionne que les compteurs de tokens numériques (sinon answer_relevancy = NaN)
class ChatMistralAIRagas(ChatMistralAI):
    def _combine_llm_outputs(self, llm_outputs):
        usage = {}
        for sortie in llm_outputs:
            for cle, valeur in ((sortie or {}).get("token_usage") or {}).items():
                if isinstance(valeur, (int, float)):
                    usage[cle] = usage.get(cle, 0) + valeur
        return {"token_usage": usage, "model_name": self.model}


# LLM juge de RAGAS et embeddings
llm = ChatMistralAIRagas(model="mistral-small-latest", api_key=KEY)
embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=KEY)


# MODÈLE PYDANTIC : structure attendue de chaque question du fichier JSON
class QuestionTest(BaseModel):
    id: str
    categorie: Literal["simple", "complexe", "bruité", "mixte"]
    source_attendue: Literal["rag", "sql", "mixte"]
    question: str
    ground_truth: str


def charger_questions(chemin: str) -> list[QuestionTest]:
    """Lit le fichier JSON et valide chaque question (erreur explicite si une entrée est mal formée)."""
    with open(chemin, encoding="utf-8") as f:
        return [QuestionTest.model_validate(q) for q in json.load(f)]


def rag_repondre(question: str):
    """RAG seul : recherche FAISS puis génération, sans routage ni SQL (étapes tracées dans Logfire)."""
    with logfire.span("recherche_faiss"):
        contextes = outil_rag(question)
        logfire.info("extraits_recuperes", nb_extraits=len(contextes))
    if not contextes:
        raise RuntimeError("aucun extrait trouvé")
    with logfire.span("redaction_reponse"):
        preuves = "\n\n---\n\n".join(contextes)
        reponse = llm_generation.invoke(PROMPT_REPONSE.format(preuves=preuves, question=question)).content
    return reponse, contextes


# Jeu de test sans "mixte"
questions = [q for q in charger_questions(CHEMIN_QUESTIONS) if q.categorie != "mixte"]

# 1. GÉNÉRATION DES RÉPONSES AVEC LE RAG SEUL
print(f"\nGénération des réponses ({len(questions)} questions)...")
data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
infos_questions = []
echecs = []

for qt in questions:
    print(f"  [{qt.id} | {qt.categorie}] {qt.question[:60]}...")
    try:
        # rag_trace : validation Pydantic de l'entrée et de la sortie + traces Logfire
        sortie = rag_trace(qt.question, rag_repondre, qt.categorie)
    except Exception as e:
        print(f"Échec écarté du calcul : {e}")
        echecs.append({"id": qt.id, "categorie": qt.categorie, "erreur": str(e)})
        continue

    data["question"].append(qt.question)
    data["answer"].append(sortie.reponse)
    data["contexts"].append([c.text for c in sortie.chunks])
    data["ground_truth"].append(qt.ground_truth)
    infos_questions.append({"id": qt.id, "categorie": qt.categorie})

if not data["question"]:
    sys.exit("Aucune réponse exploitable : évaluation impossible.")

# 2. ÉVALUATION RAGAS (uniquement sur les réponses réussies)
print("\nÉvaluation RAGAS en cours...")
resultats = evaluate(
    Dataset.from_dict(data),
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=llm, embeddings=embeddings,
)

df = resultats.to_pandas()
for cle in ["id", "categorie"]:
    df[cle] = [info[cle] for info in infos_questions]

# 3. AFFICHAGE ET SAUVEGARDE
print("\nScores par question")
print(df[["id", "categorie"] + METRIQUES].round(3).to_string())

print("\nMoyenne par catégorie")
print(df.groupby("categorie")[METRIQUES].mean().round(3))

print(f"\nÉchecs écartés : {len(echecs)}/{len(questions)}")
for e in echecs:
    print(f"  - {e['id']} ({e['categorie']}) : {e['erreur']}")

df.to_csv(CHEMIN_RESULTATS, index=False)
print(f"\nSauvegardé : {CHEMIN_RESULTATS}")