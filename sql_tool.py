# Outil SQL : traduit une question en langage naturel en requête SQL, puis l'exécute sur sportsee.db
# Le LLM écrit uniquement la requête ; c'est Python qui l'exécute : le LLM ne peut donc pas inventer de résultats

import os
import re
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_mistralai import ChatMistralAI
import logfire

load_dotenv()
KEY = os.getenv("MISTRAL_API_KEY")

CHEMIN_DB = "sportsee.db"
CHEMIN_EXCEL = "inputs/regular NBA.xlsx"
NB_LIGNES_MAX = 20                # limite le nombre de lignes renvoyées
INDISPONIBLE = "INDISPONIBLE"     # mot renvoyé par le LLM quand la base ne permet pas de répondre

llm = ChatMistralAI(model="mistral-large-latest", api_key=KEY, temperature=0)

# SCHÉMA DE LA BASE : lu automatiquement (tables, colonnes, clés), injecté dans le prompt
# sample_rows_in_table_info=0 : pas de lignes d'exemple dans le prompt
SCHEMA = SQLDatabase.from_uri(f"sqlite:///{CHEMIN_DB}", sample_rows_in_table_info=0).get_table_info()

# CORRESPONDANCE noms Excel -> noms des colonnes SQL
CORRESPONDANCE = {
    "Player": "joueur", "Team": "team_code", "Age": "age", "GP": "matchs_joues",
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

# Correction : Excel a converti "3PM" en heure "15:00". il s'agit des tirs à 3 points réussis
masque_3pm = df_dico["colonne"].str.startswith("15:00")
df_dico.loc[masque_3pm, "colonne"] = "3PM"
df_dico.loc[masque_3pm, "description"] = "Tirs à 3 points réussis"

def ligne_dictionnaire(nom_excel: str, description: str) -> str:
    """Formate une ligne : nom SQL (nom Excel) : description."""
    cle = nom_excel.replace(" ", "")              # "+ / -" -> "+/-", "AST RATIO" -> "ASTRATIO"
    nom_sql = CORRESPONDANCE.get(cle, nom_excel)
    return f"- {nom_sql} ({nom_excel}) : {description}"

DICTIONNAIRE = "\n".join(ligne_dictionnaire(row["colonne"], row["description"])
                         for _, row in df_dico.iterrows())

# FEW-SHOT : exemples de questions pour guider le LLM vers les bonnes tables, colonnes et jointures
EXEMPLES_SQL = """
Q: Quel joueur a le meilleur pourcentage à 3 points ?
SQL: SELECT p.joueur, s.pct_tirs3, s.tirs3_tentes FROM players p JOIN stats s ON s.player_id = p.player_id WHERE s.tirs3_tentes >= 100 ORDER BY s.pct_tirs3 DESC LIMIT 1

Q: Quels sont les 5 meilleurs marqueurs de la saison ?
SQL: SELECT p.joueur, s.pts FROM players p JOIN stats s ON s.player_id = p.player_id ORDER BY s.pts DESC LIMIT 5

Q: Combien de points par match marque un joueur ?
SQL: SELECT p.joueur, ROUND(s.pts / s.matchs_joues, 1) AS pts_par_match FROM players p JOIN stats s ON s.player_id = p.player_id WHERE p.joueur = 'Nom du joueur'

Q: Quelle équipe a le plus de points au total ?
SQL: SELECT t.nom, SUM(s.pts) AS pts_total FROM players p JOIN stats s ON s.player_id = p.player_id JOIN teams t ON t.code = p.team_code GROUP BY t.code ORDER BY pts_total DESC LIMIT 1

Q: Quels joueurs jouent aux Boston Celtics ?
SQL: SELECT p.joueur FROM players p JOIN teams t ON t.code = p.team_code WHERE t.nom = 'Boston Celtics'

Q: Combien de points les Lakers marquent-ils à domicile ?
SQL: INDISPONIBLE
"""

# PROMPT
PROMPT_SQL = """Tu es un expert SQL et basketball. Écris UNE requête SQLite SELECT qui répond à la question.
Renvoie uniquement la requête SQL, sans explication ni balises Markdown.

Schéma de la base :
{schema}

Organisation : players = identité des joueurs (nom, équipe, âge) ; stats = leurs statistiques sur la saison
(jointure sur player_id) ; teams = code et nom complet des équipes (jointure players.team_code = teams.code) ;
reports = saison et source des données.

Dictionnaire des colonnes (nom SQL (nom Excel) : description) :
{dictionnaire}

Attention : malgré le dictionnaire, minutes est une moyenne par match, mais les colonnes de comptage
(pts, tirs_reussis, reb_total, passes, etc.) sont des TOTAUX sur la saison. Pour une moyenne par match, divise par matchs_joues.
Les colonnes en % sont déjà des pourcentages (44.6 = 44,6 %).
Conventions : « meilleurs marqueurs » = classement par total de points (pts) ; une statistique sans précision s'entend sur toute la saison (total), sauf si la question dit « par match » ; 
un classement au pourcentage à 3 points ne retient que les joueurs ayant tenté au moins 100 tirs à 3 points.
Sélectionne toujours le nom du joueur ou de l'équipe avec la statistique demandée.

La table matches est vide : la base ne contient que des totaux de saison. Si la question porte sur des matchs
précis (derniers matchs, un match donné, domicile/extérieur), renvoie uniquement le mot INDISPONIBLE.

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
    """Étape 1 : le LLM traduit la question en requête SQL"""
    prompt = PROMPT_SQL.format(schema=SCHEMA, dictionnaire=DICTIONNAIRE,
                               exemples=EXEMPLES_SQL, question=question)
    reponse = llm.invoke(prompt)
    return nettoyer_sql(reponse.content)


def executer_sql(requete: str) -> tuple[list[str], list[tuple]]:
    """Étape 2 : Python exécute la requête en lecture seule et renvoie (colonnes, lignes)."""
    # Sécurité : seules les requêtes de lecture sont autorisées
    if not re.match(r"^(SELECT|WITH)\b", requete, flags=re.IGNORECASE):
        raise ValueError("Seules les requêtes SELECT sont autorisées.")
    # mode=ro : la base est ouverte en lecture seule, aucune modification possible
    with sqlite3.connect(f"file:{CHEMIN_DB}?mode=ro", uri=True) as conn:
        curseur = conn.execute(requete)
        colonnes = [c[0] for c in curseur.description]
        lignes = curseur.fetchmany(NB_LIGNES_MAX)
    return colonnes, lignes


def repondre_sql(question: str) -> str:
    """Génère la requête, l'exécute et renvoie la requête + les résultats bruts (contexte pour le routeur et RAGAS).
    La génération et l'exécution sont tracées dans Logfire."""
    # Précise la saison et l'unité des données, pour que le LLM puisse répondre à « cette saison »
    source = "Source : base de statistiques NBA, saison régulière 2024-25 (colonnes de comptage = totaux sur la saison)"
    try:
        with logfire.span("generation_sql"):
            requete = generer_sql(question)
            logfire.info("requete_generee", requete=requete)
        if requete.upper().startswith(INDISPONIBLE):
            logfire.info("question_indisponible")
            return (f"{source}\nInformation non disponible : la base ne contient que des totaux de saison, "
                    "sans données match par match (derniers matchs, domicile/extérieur).")
        with logfire.span("execution_sql"):
            colonnes, lignes = executer_sql(requete)
            logfire.info("resultat_sql", nb_lignes=len(lignes))
        if not lignes:
            return f"{source}\nRequête SQL : {requete}\nRésultat : aucune ligne trouvée dans la base."
        resultat = "\n".join(str(ligne) for ligne in lignes)
        return f"{source}\nRequête SQL : {requete}\nColonnes : {', '.join(colonnes)}\nRésultat :\n{resultat}"
    except Exception as e:
        logfire.error("erreur_sql", erreur=str(e))
        return f"Erreur SQL : {e}"


# TEST
if __name__ == "__main__":
    questions_test = [
        "Parmi les 15 meilleurs marqueurs de la saison, quel joueur a le meilleur pourcentage de réussite à 3 points ?",
        "Combien de points par match marque Shai Gilgeous-Alexander ?",
        "Quelle équipe a marqué le plus de points ?",
        "Quel joueur a le meilleur pourcentage à 3 points sur les 5 derniers matchs ?",
    ]
    for q in questions_test:
        print(f"\nQuestion : {q}")
        print(repondre_sql(q))