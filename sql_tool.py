# Outil SQL : traduit une question en langage naturel en requête SQL, puis l'exécute sur sportsee.db
# Le LLM écrit uniquement la requête ; c'est Python qui l'exécute pour empecher le llm d'nventer de résultats

import os
import re
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_mistralai import ChatMistralAI

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

CHEMIN_DB = "sportsee.db"
CHEMIN_EXCEL = "inputs/regular NBA.xlsx"
NB_LIGNES_MAX = 20          # limite le nombre de lignes renvoyées

llm = ChatMistralAI(model="mistral-large-latest", api_key=KEY, temperature=0)

# SCHÉMA DE LA BASE : lu automatiquement (tables / colonnes)
# sample_rows_in_table_info=0 : aucune ligne d'exemple, pour que le LLM ne devine pas les réponses
SCHEMA = SQLDatabase.from_uri(f"sqlite:///{CHEMIN_DB}", sample_rows_in_table_info=0).get_table_info()

# Correspondance noms Excel et noms colonnes SQL (identique à charger_excel_db.py)
CORRESPONDANCE = {
    "Player": "joueur", "Team": "equipe", "Age": "age", "GP": "matchs_joues",
    "W": "victoires", "L": "defaites", "Min": "minutes", "PTS": "pts",
    "FGM": "tirs_reussis", "FGA": "tirs_tentes", "FG%": "pct_tirs",
    "3PM": "tirs3_reussis", "3PA": "tirs3_tentes", "3P%": "pct_tirs3",
    "FTM": "lf_reussis", "FTA": "lf_tentes", "FT%": "pct_lf",
    "OREB": "reb_off", "DREB": "reb_def", "REB": "reb_total",
    "AST": "passes", "TOV": "pertes", "STL": "interceptions", "BLK": "contres",
    "PF": "fautes", "FP": "fantasy_pts", "DD2": "double_double", "TD3": "triple_double",
    "+/-": "plus_minus", "OFFRTG": "offrtg", "DEFRTG": "defrtg", "NETRTG": "netrtg",
    "AST%": "ast_pct", "AST/TO": "ast_to", "ASTRATIO": "ast_ratio",
    "OREB%": "oreb_pct", "DREB%": "dreb_pct", "REB%": "reb_pct",
    "TORATIO": "to_ratio", "EFG%": "efg_pct", "TS%": "ts_pct",
    "USG%": "usg_pct", "PACE": "pace", "PIE": "pie", "POSS": "poss",
}

# CHARGEMENT AUTOMATIQUE DU DICTIONNAIRE DES DONNÉES
df_dico = pd.read_excel(CHEMIN_EXCEL, sheet_name="Dictionnaire des données", header=0)
df_dico.columns = ["colonne", "description"]
df_dico = df_dico.dropna(subset=["colonne"])
df_dico["colonne"] = df_dico["colonne"].astype(str)

# Correction erreur: Excel a converti "3PM" en heure "15:00" or il s'agit des tirs à 3 points réussis
masque_3pm = df_dico["colonne"].str.startswith("15:00")
df_dico.loc[masque_3pm, "colonne"] = "3PM"
df_dico.loc[masque_3pm, "description"] = "Tirs à 3 points réussis"

def ligne_dictionnaire(nom_excel: str, description: str) -> str:      # transforme les lignes excel en ligne comprehensible par le llm via correspondance
    """Formate une ligne : nom SQL (nom Excel) : description."""
    cle = nom_excel.replace(" ", "")              # "+ / -" -> "+/-", "AST RATIO" -> "ASTRATIO"
    nom_sql = CORRESPONDANCE.get(cle, nom_excel)
    return f"- {nom_sql} ({nom_excel}) : {description}"

DICTIONNAIRE = "\n".join(ligne_dictionnaire(row["colonne"], row["description"])
                         for _, row in df_dico.iterrows())

# FEW-SHOT : exemples de questions pour guider le LLM vers les bonnes tables et colonnes
EXEMPLES_SQL = """
Q: Quel joueur a le meilleur pourcentage à 3 points (avec un volume de tirs significatif) ?
SQL: SELECT joueur, pct_tirs3, tirs3_tentes FROM players WHERE tirs3_tentes >= 100 ORDER BY pct_tirs3 DESC LIMIT 1

Q: Quels sont les 5 meilleurs marqueurs de la saison ?
SQL: SELECT joueur, pts FROM players ORDER BY pts DESC LIMIT 5

Q: Combien de points par match marque un joueur ?
SQL: SELECT joueur, ROUND(pts / matchs_joues, 1) AS pts_par_match FROM players WHERE joueur = 'Nom du joueur'

Q: Quelle équipe a le plus de points au total ?
SQL: SELECT nom, pts_total FROM stats_equipes ORDER BY pts_total DESC LIMIT 1

Q: Combien de possessions totales a joué un joueur ?
SQL: SELECT joueur, poss FROM players WHERE joueur = 'Nom du joueur'
"""

# Prompt
PROMPT_SQL = """Tu es un expert SQL et basketball. Écris UNE requête SQLite SELECT qui répond à la question.
Renvoie uniquement la requête SQL, sans explication ni balises Markdown.

Schéma de la base :
{schema}

Dictionnaire des colonnes de la table players (nom SQL (nom Excel) : description) :
{dictionnaire}

Attention : malgré le dictionnaire, minutes est une moyenne par match, mais les colonnes de comptage
(pts, tirs_reussis, passes, etc.) sont des TOTAUX sur la saison.
Pour une moyenne par match, divise par matchs_joues.
Les colonnes en % sont déjà des pourcentages (44.6 = 44,6 %).
Sélectionne toujours le nom du joueur ou de l'équipe avec la statistique demandée.

Exemples :
{exemples}

Q: {question}
SQL:"""


def nettoyer_sql(texte: str) -> str:
    """Retire les éventuelles balises ```sql``` et le point-virgule final ajoutés par le LLM."""
    texte = texte.strip()
    texte = re.sub(r"^```(?:sql)?\s*|\s*```$", "", texte, flags=re.IGNORECASE)
    return texte.strip().rstrip(";").strip()


def generer_sql(question: str) -> str:
    """Étape 1 : le LLM traduit la question en requête SQL."""
    prompt = PROMPT_SQL.format(schema=SCHEMA, dictionnaire=DICTIONNAIRE,
                               exemples=EXEMPLES_SQL, question=question)
    reponse = llm.invoke(prompt)
    return nettoyer_sql(reponse.content)


def executer_sql(requete: str) -> tuple[list[str], list[tuple]]:
    """Étape 2 : Python exécute la requête en lecture seule et renvoie (colonnes, lignes)."""
    # seules les requêtes de lecture autorisées
    if not re.match(r"^(SELECT|WITH)\b", requete, flags=re.IGNORECASE):
        raise ValueError("Seules les requêtes SELECT sont autorisées.")
    # mode=ro : la base est ouverte en lecture seule, pas de modification possible
    with sqlite3.connect(f"file:{CHEMIN_DB}?mode=ro", uri=True) as conn:
        curseur = conn.execute(requete)
        colonnes = [c[0] for c in curseur.description]
        lignes = curseur.fetchmany(NB_LIGNES_MAX)
    return colonnes, lignes


def repondre_sql(question: str) -> str:
    """Génère la requête, l'exécute et renvoie la requête et les résultats bruts (contexte pour le routeur et RAGAS)."""
    try:
        requete = generer_sql(question)
        colonnes, lignes = executer_sql(requete)
        if not lignes:
            return f"Requête SQL : {requete}\nRésultat : aucune ligne trouvée dans la base."
        resultat = "\n".join(str(ligne) for ligne in lignes)
        return f"Requête SQL : {requete}\nColonnes : {', '.join(colonnes)}\nRésultat :\n{resultat}"
    except Exception as e:
        return f"Erreur SQL : {e}"


# TEST
if __name__ == "__main__":
    questions_test = [
        "Parmi les 15 meilleurs marqueurs de la saison, quel joueur a le meilleur pourcentage de réussite à 3 points ?",
        "Combien de points par match marque Shai Gilgeous-Alexander ?",
    ]
    for q in questions_test:
        print(f"\nQuestion : {q}")
        print(repondre_sql(q))