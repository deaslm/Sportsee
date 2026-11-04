# LangChain SQL Tool : génère et exécute des requêtes SQL à partir d'une question en langage naturel sur la base sportsee.db

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv
import os

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

# CONNEXION À LA BASE SQLite
# LangChain lit le schéma automatiquement

db = SQLDatabase.from_uri("sqlite:///sportsee.db", sample_rows_in_table_info=0)       # forcer Mistral d’exécuter la requête SQL

llm = ChatMistralAI(model="mistral-large-latest", api_key=KEY, temperature=0)

# FEW-SHOT : exemples question pour guider le LLM vers les bonnes tables et colonnes

EXEMPLES_SQL = """
Exemples de requêtes sur la base sportsee.db :

Q: Quel joueur a le meilleur pourcentage à 3 points ?
SQL: SELECT joueur, pct_tirs3 FROM stats_joueurs WHERE pct_tirs3 IS NOT NULL ORDER BY pct_tirs3 DESC LIMIT 1;

Q: Quels sont les 5 meilleurs marqueurs de la saison ?
SQL: SELECT joueur, pts FROM players ORDER BY pts DESC LIMIT 5;

Q: Quelle équipe a le plus de points au total ?
SQL: SELECT nom, pts_total FROM stats_equipes ORDER BY pts_total DESC LIMIT 1;

Q: Compare les rebonds offensifs des meilleurs scoreurs.
SQL: SELECT joueur, reb_off, pts_total FROM stats_joueurs ORDER BY pts_total DESC;
"""

# PRÉFIXE : contexte donné au LLM avant génération du SQL
# On lui dit qui il est, quelles tables il a et on lui donne des exemples pour éviter les erreurs de colonnes

PREFIX =f"""Tu es un assistant expert en basketball. 
Tu as accès à une base de données SQLite avec les tables : players, teams, stats_joueurs, stats_equipes.
Utilise uniquement les données de la base.

{EXEMPLES_SQL}
"""

# CRÉATION DE L'AGENT SQL

agent = create_sql_agent(
    llm=llm,
    db=db,
    verbose=True,                                  # affiche le SQL généré et les résultats intermédiaires
    prefix=PREFIX,
    agent_type="zero-shot-react-description",      # compatible avec tous les LLMs
    handle_parsing_errors=True, )


def repondre_sql(question: str) -> str:
    """Pose une question à l'agent SQL et retourne la réponse."""
    try:
        result = agent.invoke({"input": question})
        return result["output"]
    except Exception as e:
        return f"Erreur SQL : {e}"


# TEST

if __name__ == "__main__":
    questions_test = ["Quel joueur a le meilleur pourcentage de réussite à 3 points sur la saison ?"]
    for q in questions_test:
        print(f"\nQuestion : {q}")
        print(f"Réponse  : {repondre_sql(q)}")