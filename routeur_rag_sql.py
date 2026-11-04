# Agent qui route automatiquement entre RAG (contexte) et SQL (chiffres)
import os
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub
from langchain_mistralai import ChatMistralAI
from utils.vector_store import VectorStoreManager
from mistralai.client import MistralClient
from sql_tool import repondre_sql

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

# Initialisation RAG
vs = VectorStoreManager()
client = MistralClient(api_key=KEY)

def repondre_rag(question: str) -> str:
    """Répond aux questions contextuelles via FAISS + Mistral."""
    chunks = vs.search(question, k=5)
    contexte = "\n\n".join(c["text"] for c in chunks)
    rep = client.chat(
        model="mistral-large-latest",
        messages=[{"role": "user", "content":
                   f"Tu es un assistant expert en basketball. Réponds uniquement à partir du contexte.\n\n"
                   f"Contexte:\n{contexte}\n\nQuestion: {question}\nRéponse:"}]
    )
    return rep.choices[0].message.content

# Définition des outils
outils = [
    Tool(
        name="outil_rag",
        func=repondre_rag,
        description=(
            "Utilise cet outil pour les questions sur le contexte en basketball : "
            "règles, événements, play-in, playoffs, descriptions générales. "
            "Exemple : 'Qu'est-ce que le play-in ?' ou 'Quelle équipe a atteint les Finals ?'"
        ),
    ),
    Tool(
        name="outil_sql",
        func=repondre_sql,
        description=(
            "Utilise cet outil pour les questions avec des statistiques chiffrées : "
            "pourcentages, points, rebonds, classements numériques. "
            "Exemple : 'Quel joueur a le meilleur pourcentage à 3 points ?' ou 'Quels sont les 5 meilleurs joueurs ?'"
        ),
    ),
]

# Création de l'agent 
llm = ChatMistralAI(model="mistral-large-latest", api_key=KEY, temperature=0)
prompt = hub.pull("hwchase17/react")                # prompt ReAct (Reasoning/Acting), définit le format que l’agent doit suivre

agent = create_react_agent(llm=llm, tools=outils, prompt=prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=outils,
    verbose=True,
    handle_parsing_errors=True,
)

def repondre(question: str) -> str:
    """Route la question vers RAG ou SQL selon son type."""
    result = agent_executor.invoke({"input": question})
    return result["output"]

if __name__ == "__main__":
    questions_test = [
        "Qu'est-ce que le play-in tournament NBA ?",           # → RAG
        "Quel joueur a le meilleur pourcentage à 3 points ?",  # → SQL
    ]
    for q in questions_test:
        print(f"\nQuestion : {q}")
        print(f"Réponse  : {repondre(q)}")