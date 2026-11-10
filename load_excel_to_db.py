# Lecture du fichier Excel NBA et chargement des données dans SQLite (sportsee.db)
# Schéma : teams, players, reports, stats, matches
# Chaque ligne est validée par Pydantic avant insertion

import os
import sqlite3
import datetime
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from typing import Optional

CHEMIN_EXCEL = "inputs/regular NBA.xlsx"
CHEMIN_DB = "sportsee.db"
SAISON = "2024-25"                 
TYPE_SAISON = "saison régulière"


# MODÈLES PYDANTIC : validation des lignes avant insertion

class LigneEquipe(BaseModel):
    """Valide une ligne de la feuille Equipe."""
    code: str = Field(..., min_length=2, max_length=3)
    nom: str


class LigneJoueur(BaseModel):
    """Valide une ligne de la feuille Données NBA (identité du joueur + statistiques de la saison)."""
    joueur: str
    equipe: Optional[str] = None
    age: Optional[int] = None
    matchs_joues: Optional[int] = None
    victoires: Optional[int] = None
    defaites: Optional[int] = None
    minutes: Optional[float] = None
    pts: Optional[float] = None
    tirs_reussis: Optional[float] = None
    tirs_tentes: Optional[float] = None
    pct_tirs: Optional[float] = None
    tirs3_reussis: Optional[float] = None
    tirs3_tentes: Optional[float] = None
    pct_tirs3: Optional[float] = None
    lf_reussis: Optional[float] = None
    lf_tentes: Optional[float] = None
    pct_lf: Optional[float] = None
    reb_off: Optional[float] = None
    reb_def: Optional[float] = None
    reb_total: Optional[float] = None
    passes: Optional[float] = None
    pertes: Optional[float] = None
    interceptions: Optional[float] = None
    contres: Optional[float] = None
    fautes: Optional[float] = None
    fantasy_pts: Optional[float] = None
    double_double: Optional[float] = None
    triple_double: Optional[float] = None
    plus_minus: Optional[float] = None
    offrtg: Optional[float] = None
    defrtg: Optional[float] = None
    netrtg: Optional[float] = None
    ast_pct: Optional[float] = None
    ast_to: Optional[float] = None
    ast_ratio: Optional[float] = None
    oreb_pct: Optional[float] = None
    dreb_pct: Optional[float] = None
    reb_pct: Optional[float] = None
    to_ratio: Optional[float] = None
    efg_pct: Optional[float] = None
    ts_pct: Optional[float] = None
    usg_pct: Optional[float] = None
    pace: Optional[float] = None
    pie: Optional[float] = None
    poss: Optional[float] = None

    @field_validator("pct_tirs", "pct_tirs3", "pct_lf")
    @classmethod
    def pourcentage_valide(cls, v):
        # Un pourcentage doit être entre 0 et 100
        if v is not None and not (0 <= v <= 100):
            raise ValueError(f"Pourcentage invalide : {v}")
        return v


# Colonnes de la table stats (toutes les statistiques, hors identité du joueur)
COLONNES_STATS = [c for c in LigneJoueur.model_fields if c not in ("joueur", "equipe", "age")]

# Correspondance colonnes Excel -> champs Pydantic
COLONNES_EXCEL = {
    "Player": "joueur", "Team": "equipe", "Age": "age", "GP": "matchs_joues",
    "W": "victoires", "L": "defaites", "Min": "minutes", "PTS": "pts",
    "FGM": "tirs_reussis", "FGA": "tirs_tentes", "FG%": "pct_tirs",
    "3PM": "tirs3_reussis", "3PA": "tirs3_tentes", "3P%": "pct_tirs3",
    "FTM": "lf_reussis", "FTA": "lf_tentes", "FT%": "pct_lf",
    "OREB": "reb_off", "DREB": "reb_def", "REB": "reb_total",
    "AST": "passes", "TOV": "pertes", "STL": "interceptions", "BLK": "contres",
    "PF": "fautes", "FP": "fantasy_pts", "DD2": "double_double", "TD3": "triple_double",
    "+/-": "plus_minus", "OFFRTG": "offrtg", "DEFRTG": "defrtg", "NETRTG": "netrtg",
    "AST%": "ast_pct", "AST/TO": "ast_to", "AST RATIO": "ast_ratio",
    "OREB%": "oreb_pct", "DREB%": "dreb_pct", "REB%": "reb_pct",
    "TO RATIO": "to_ratio", "EFG%": "efg_pct", "TS%": "ts_pct",
    "USG%": "usg_pct", "PACE": "pace", "PIE": "pie", "POSS": "poss",
}


# CRÉATION DE LA BASE ET DU SCHÉMA

# La base est reconstruite entièrement à chaque exécution pour éviter doublons
if os.path.exists(CHEMIN_DB):
    os.remove(CHEMIN_DB)

conn = sqlite3.connect(CHEMIN_DB)
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys = ON")      # active le contrôle des clés étrangères

# Équipes : code et nom complet (feuille Equipe)
cur.execute("""
CREATE TABLE teams (
    code TEXT PRIMARY KEY,
    nom  TEXT NOT NULL
)""")

# Joueurs : identité reliée à son équipe
cur.execute("""
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    joueur    TEXT NOT NULL UNIQUE,
    team_code TEXT REFERENCES teams(code),
    age       INTEGER
)""")

# Rapports : source des statistiques (saison, type, fichier, date d'import)
cur.execute("""
CREATE TABLE reports (
    report_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    saison         TEXT NOT NULL,
    type_saison    TEXT NOT NULL,
    fichier_source TEXT,
    date_import    TEXT,
    UNIQUE (saison, type_saison)
)""")

# Statistiques : une ligne par joueur et par rapport (saison)
colonnes_sql = ",\n    ".join(f"{c} REAL" for c in COLONNES_STATS)
cur.execute(f"""
CREATE TABLE stats (
    stat_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    report_id INTEGER NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    {colonnes_sql},
    UNIQUE (player_id, report_id)
)""")

# Matchs : structure prévue, mais vide (l'Excel ne contient aucune donnée match par match)
cur.execute("""
CREATE TABLE matches (
    match_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id        INTEGER REFERENCES reports(report_id) ON DELETE CASCADE,
    date_match       TEXT,
    equipe_domicile  TEXT REFERENCES teams(code),
    equipe_exterieur TEXT REFERENCES teams(code),
    score_domicile   INTEGER,
    score_exterieur  INTEGER,
    CHECK (equipe_domicile <> equipe_exterieur)
)""")

# Index sur les colonnes de jointure : accélèrent les requêtes avec JOIN
cur.execute("CREATE INDEX idx_players_team ON players(team_code)")
cur.execute("CREATE INDEX idx_stats_player ON stats(player_id)")
cur.execute("CREATE INDEX idx_stats_report ON stats(report_id)")
conn.commit()


# INGESTION TEAMS

print("Chargement des équipes...")
df_eq = pd.read_excel(CHEMIN_EXCEL, sheet_name="Equipe")
ok, err = 0, 0
for _, row in df_eq.iterrows():
    try:
        t = LigneEquipe(code=row["Code"], nom=row["Nom complet de l'équipe"])
        cur.execute("INSERT INTO teams VALUES (?, ?)", (t.code, t.nom))
        ok += 1
    except Exception as e:
        err += 1
        print(f"  Erreur équipe : {e}")
print(f"  -> {ok} équipes insérées, {err} erreurs")


# INGESTION REPORTS

cur.execute("INSERT INTO reports (saison, type_saison, fichier_source, date_import) VALUES (?, ?, ?, ?)",
            (SAISON, TYPE_SAISON, CHEMIN_EXCEL, datetime.datetime.now().isoformat(timespec="seconds")))
report_id = cur.lastrowid


# INGESTION PLAYERS + STATS

print("Chargement des joueurs et de leurs statistiques...")
# header=1 : la ligne 0 est un titre, la ligne 1 contient les noms de colonnes
df = pd.read_excel(CHEMIN_EXCEL, sheet_name="Données NBA", header=1)
# Excel a converti l'en-tête "3PM" en heure (15:00) : on le renomme
df.columns = ["3PM" if isinstance(c, datetime.time) else c for c in df.columns]
df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

placeholders = ", ".join("?" for _ in COLONNES_STATS)
ok, err = 0, 0
for _, row in df.iterrows():
    try:
        j = LigneJoueur(**{champ: row.get(col) for col, champ in COLONNES_EXCEL.items()})
        # 1. Le joueur (identité)
        cur.execute("INSERT INTO players (joueur, team_code, age) VALUES (?, ?, ?)",
                    (j.joueur, j.equipe, j.age))
        player_id = cur.lastrowid
        # 2. Ses statistiques, reliées au joueur et au rapport
        cur.execute(f"INSERT INTO stats (player_id, report_id, {', '.join(COLONNES_STATS)}) "
                    f"VALUES (?, ?, {placeholders})",
                    (player_id, report_id, *[getattr(j, c) for c in COLONNES_STATS]))
        ok += 1
    except Exception as e:
        err += 1
        print(f"  Erreur joueur : {e}")
print(f"  -> {ok} joueurs insérés, {err} erreurs")

conn.commit()

# RÉCAPITULATIF
print("\nBase SQLite créée : sportsee.db")
for table in ["teams", "players", "reports", "stats", "matches"]:
    print(f"  {table:8} : {cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]} lignes")
conn.close()