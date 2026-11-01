# Évalue le prototype avant améliorations

import os
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from mistralai.client import MistralClient
from utils.vector_store import VectorStoreManager
from logfire_setup import rag_trace

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

# LLM et embeddings utilisés par RAGAS pour juger les réponses
llm = ChatMistralAI(model="mistral-small-latest", api_key=KEY)
embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=KEY)

# Chargement de l'index FAISS (vector_db/)
vs = VectorStoreManager()

# Client Mistral pour générer les réponses RAG
client = MistralClient(api_key=KEY)

# Jeu de test catégorisé
# Un tuple = question, ground_truth (réponse correcte attendue), catégorie

# Questions simples : formulation claire, réponse directe
questions_simples = [
    ("Qu'est-ce que le play-in tournament NBA ?",
     "Le play-in permet aux équipes classées 7 à 10 de se qualifier pour les playoffs NBA.",
     "simple"),
    ("Quelle équipe a atteint les Finals NBA 2023 sans avoir l'avantage du terrain ?",
     "Le Miami Heat, tête de série 8, a atteint les Finals 2023 sans avantage du terrain.",
     "simple"),]

# Questions complexes : nécessitent de croiser plusieurs infos / synthétiser
questions_complexes = [
    ("Quel joueur a le meilleur pourcentage de réussite à 3 points sur la saison ?",
    "Zach LaVine affiche le meilleur pourcentage à 3 points parmi les joueurs à haut volume, avec 44,6%.",
    "complexe"),
    ("Compare les statistiques de rebonds offensifs des meilleurs scoreurs de la saison.",
    "Parmi les 15 meilleurs scoreurs, Karl-Anthony Towns domine les rebonds offensifs "
    "avec 209 prises, suivi de Nikola Jokić (203) et Giannis Antetokounmpo "
    "(147). À l'opposé, Zach LaVine (22) et Tyler Herro (39) captent très peu "
    "de rebonds offensifs.",
    "complexe"),]

# Questions bruitées : mal formulées (fautes, abréviations..)
questions_bruitees = [
    ("heat finals 2023 homecourt oui ou non ?",
     "Non, le Heat n'avait pas l'avantage du terrain en 2023, ils étaient la tête de série 8.",
     "bruité"),
    ("play in nba utile ou pas arguments ??",
     "Le play-in est jugé utile car il maintient l'intérêt en fin de saison"
     "mais critiqué car il peut avantager des équipes inférieures.",
     "bruité"),]

# Fusion de toutes les questions
TESTS = questions_simples + questions_complexes + questions_bruitees


def rag_repondre(question):
    """Cherche les 5 chunks les plus pertinents et génère une réponse via Mistral."""
    chunks = vs.search(question, k=5)
    contexte = "\n\n".join(c["text"] for c in chunks)
    rep = client.chat(
        model="mistral-small-latest",
        messages=[{"role": "user", "content":
                   f"Tu es un assistant NBA. Réponds uniquement à partir du contexte.\n\n"
                   f"Contexte:\n{contexte}\n\nQuestion: {question}\nRéponse:"}]
    )
    return rep.choices[0].message.content, [c["text"] for c in chunks]


# Construction du dataset RAGAS
print("Génération des réponses RAG...")
data = {"question": [], "answer": [], "contexts": [], "ground_truth": [], "category": []}

for q, gt, cat in TESTS:
    print(f"  [{cat}] {q[:55]}...")
    # rag_trace valide via Pydantic et envoie les traces à Logfire
    sortie = rag_trace(q, rag_repondre, categorie=cat)
    data["question"].append(q)
    data["answer"].append(sortie.reponse)
    data["contexts"].append([c.text for c in sortie.chunks])
    data["ground_truth"].append(gt)
    data["category"].append(cat)

# Évaluation RAGAS (RAGAS utilise le LLM pour juger : fidélité, pertinence, précision, rappel)
print("\nÉvaluation RAGAS en cours...")
results = evaluate(
    Dataset.from_dict(data),
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=llm,
    embeddings=embeddings,
)

# Affichage des résultats
df = results.to_pandas()
df["category"] = data["category"]

print("Scores par question")
print(df[["category", "faithfulness", "answer_relevancy",
          "context_precision", "context_recall"]].to_string())

print("Moyenne par catégorie")
print(df.groupby("category")[
    ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
].mean().round(3))

# Sauvegarde pour comparaison plus tard
df.to_csv("resultats_ragas_avant.csv", index=False)
print("Sauvegardé : resultats_ragas_avant.csv")