# Évalue le prototype après intégration SQL (routeur RAG + SQL)
import os
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from utils.vector_store import VectorStoreManager
from routeur_rag_sql import repondre, agent_executor
from logfire_setup import rag_trace

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

llm = ChatMistralAI(model="mistral-small-latest", api_key=KEY)
embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=KEY)
vs = VectorStoreManager()

# On va comparer sur les memes questions qu'avant
questions_simples = [
    ("Qu'est-ce que le play-in tournament NBA ?",
     "Le play-in permet aux équipes classées 7 à 10 de se qualifier pour les playoffs NBA.", "simple"),
    ("Quelle équipe a atteint les Finals NBA 2023 sans avoir l'avantage du terrain ?",
     "Le Miami Heat, tête de série 8, a atteint les Finals 2023 sans avantage du terrain.", "simple"), ]
questions_complexes = [
    ("Quel joueur a le meilleur pourcentage de réussite à 3 points sur la saison ?",
     "Zach LaVine affiche le meilleur pourcentage à 3 points parmi les meilleurs scoreurs, avec 44,6%.", "complexe"),
    ("Compare les statistiques de rebonds offensifs des meilleurs scoreurs de la saison.",
     "Parmi les 15 meilleurs scoreurs, Karl-Anthony Towns domine les rebonds offensifs "
     "avec 209 prises, suivi de Nikola Jokić (203) et Giannis Antetokounmpo (147).", "complexe"),]
questions_bruitees = [
    ("heat finals 2023 homecourt oui ou non ?",
     "Non, le Heat n'avait pas l'avantage du terrain en 2023, ils étaient la tête de série 8.", "bruité"),
    ("play in nba utile ou pas arguments ??",
     "Le play-in est jugé utile car il maintient l'intérêt en fin de saison "
     "mais critiqué car il peut avantager des équipes inférieures.", "bruité"),]

#Questions mixtes (contexte narratif + chiffres)
questions_mixtes = [ 
    ("Qui est Nikola Jokić et quel est son pourcentage de tirs cette saison ?",
     "Nikola Jokić est le pivot des Denver Nuggets, MVP des Finals 2023. Il affiche 57,6% de réussite aux tirs cette saison.", "mixte"),
    ("Qu'est-ce que le play-in et combien de points marque Zach LaVine cette saison ?",
     "Le play-in est un mini-tournoi pour les équipes classées 7 à 10. Zach LaVine totalise 1724 points cette saison.", "mixte"),]

TESTS = questions_simples + questions_complexes + questions_bruitees + questions_mixtes

def rag_repondre(question):
    """Pour l'évaluation : retourne (réponse, contexte adapté selon la source)."""
    # Appelle le routeur et récupère la réponse + les étapes intermédiaires
    result = agent_executor.invoke({"input": question})
    reponse_texte = result["output"]
    
    # Détecte quel outil a été utilisé par l'agent
    outils = str(result.get("intermediate_steps", []))
    if "outil_sql" in outils and "outil_rag" in outils:
        source = "mixte"
    elif "outil_sql" in outils:
        source = "sql"
    else:
        source = "rag"
    print(f"  → source détectée : {source}")

    # Adapte le contexte selon la source
    if source == "mixte":
        chunks = vs.search(question, k=3)
        contexte = [c["text"] for c in chunks] + [reponse_texte]
    elif source == "sql":
        contexte = [reponse_texte]
    else:
        chunks = vs.search(question, k=5)
        contexte = [c["text"] for c in chunks]
    
    return reponse_texte, contexte

print("Génération des réponses avec le routeur...")
data = {"question": [], "answer": [], "contexts": [], "ground_truth": [], "category": []}

for q, gt, cat in TESTS:
    print(f"  [{cat}] {q[:55]}...")
    reponse_texte, chunks_bruts = rag_repondre(q)
    data["question"].append(q)
    data["answer"].append(reponse_texte)
    data["contexts"].append(chunks_bruts)
    data["ground_truth"].append(gt)
    data["category"].append(cat)

print("Évaluation RAGAS en cours...")
results = evaluate(
    Dataset.from_dict(data),
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=llm, embeddings=embeddings,)

df = results.to_pandas()
df["category"] = data["category"]
print("Scores par question:")
print(df[["category", "faithfulness", "answer_relevancy", "context_precision", "context_recall"]].to_string())
print("Moyenne par catégorie:")
print(df.groupby("category")[["faithfulness", "answer_relevancy", "context_precision", "context_recall"]].mean().round(3))
df.to_csv("resultats_ragas_apres.csv", index=False)
print("Sauvegardé : resultats_ragas_apres.csv")