# Évaluation RAGAS du système APRÈS intégration SQL (routeur RAG + SQL)

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
from routeur_rag_sql import repondre_avec_contextes
from logfire_setup import rag_trace

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

CHEMIN_QUESTIONS = "questions_test.json"
CHEMIN_RESULTATS = "resultats_ragas_apres.csv"
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


def source_detectee(outils_appeles: list[str]) -> str:
    """Traduit la liste des outils appelés en source : rag, sql ou mixte."""
    if "outil_rag" in outils_appeles and "outil_sql" in outils_appeles:
        return "mixte"
    if "outil_sql" in outils_appeles:
        return "sql"
    return "rag"


questions = charger_questions(CHEMIN_QUESTIONS)

# 1. GÉNÉRATION DES RÉPONSES AVEC LE ROUTEUR
print(f"\nGénération des réponses ({len(questions)} questions)...")
data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
infos_questions = []      # id, catégorie, routage : pour le tableau final
echecs = []

for qt in questions:
    print(f"  [{qt.id} | {qt.categorie}] {qt.question[:60]}...")
    trace = {}

    def pipeline(question: str):
        """Appelle le routeur ; un échec lève une erreur (tracée dans Logfire) au lieu d'être noté."""
        reponse, contextes, outils = repondre_avec_contextes(question)
        trace["outils"] = outils
        if reponse is None or not contextes:
            raise RuntimeError("pipeline sans réponse exploitable")
        return reponse, contextes

    try:
        # rag_trace : validation Pydantic de l'entrée et de la sortie + traces Logfire
        sortie = rag_trace(qt.question, pipeline, qt.categorie)
    except Exception as e:
        print(f"    -> ÉCHEC écarté du calcul : {e}")
        echecs.append({"id": qt.id, "categorie": qt.categorie, "erreur": str(e)})
        continue

    source = source_detectee(trace["outils"])
    print(f"    -> outils : {trace['outils']} | source attendue : {qt.source_attendue}")
    data["question"].append(qt.question)
    data["answer"].append(sortie.reponse)
    data["contexts"].append([c.text for c in sortie.chunks])
    data["ground_truth"].append(qt.ground_truth)
    infos_questions.append({"id": qt.id, "categorie": qt.categorie,
                            "source_attendue": qt.source_attendue, "source_detectee": source,
                            "routage_ok": source == qt.source_attendue})

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
for cle in ["id", "categorie", "source_attendue", "source_detectee", "routage_ok"]:
    df[cle] = [info[cle] for info in infos_questions]

# 3. AFFICHAGE ET SAUVEGARDE
print("\nScores par question")
print(df[["id", "categorie", "source_detectee", "routage_ok"] + METRIQUES].round(3).to_string())

print("\nMoyenne par catégorie")
print(df.groupby("categorie")[METRIQUES].mean().round(3))

taux_routage = df["routage_ok"].mean() * 100
print(f"\nTaux de bon routage : {taux_routage:.0f} % ({df['routage_ok'].sum()}/{len(df)})")
print(f"Échecs écartés      : {len(echecs)}/{len(questions)}")
for e in echecs:
    print(f"  - {e['id']} ({e['categorie']}) : {e['erreur']}")

df.to_csv(CHEMIN_RESULTATS, index=False)
print(f"\nSauvegardé : {CHEMIN_RESULTATS}")