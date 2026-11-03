# Pipeline d'ingestion : lit fichier Excel et charge les données dans SQLite.
# Validation Pydantic à chaque ligne avant insertion en base.

import sqlite3
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from typing import Optional

CHEMIN_EXCEL = "inputs/regular NBA.xlsx"
CHEMIN_DB = "sportsee.db"

# MODÈLES PYDANTIC — validation des lignes avant insertion

class LigneJoueur(BaseModel):
    """Valide une ligne de stats joueur avant insertion dans la table players."""
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


class LigneEquipe(BaseModel):
    """Valide une ligne de la feuille Equipe."""
    code: str = Field(..., min_length=2, max_length=3)
    nom: str


class LigneStat(BaseModel):
    """Valide une ligne du top 15 joueurs."""
    joueur: str
    pts_total: Optional[float] = None
    pct_tirs: Optional[float] = None
    pct_tirs3: Optional[float] = None
    pct_lf: Optional[float] = None
    reb_off: Optional[float] = None
    impact: Optional[float] = None


class LigneStatEquipe(BaseModel):
    """Valide une ligne de stats d'équipe."""
    code: str
    nom: str
    nb_joueurs: Optional[int] = None
    pts_total: Optional[float] = None


# CONNEXION SQLITE + CRÉATION DES TABLES

conn = sqlite3.connect(CHEMIN_DB)
cur = conn.cursor()

# Table principale : toutes les stats individuelles des joueurs
cur.execute("""
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    joueur TEXT NOT NULL, equipe TEXT, age INTEGER,
    matchs_joues INTEGER, victoires INTEGER, defaites INTEGER,
    minutes REAL, pts REAL, tirs_reussis REAL, tirs_tentes REAL,
    pct_tirs REAL, tirs3_reussis REAL, tirs3_tentes REAL, pct_tirs3 REAL,
    lf_reussis REAL, lf_tentes REAL, pct_lf REAL,
    reb_off REAL, reb_def REAL, reb_total REAL,
    passes REAL, pertes REAL, interceptions REAL, contres REAL,
    fautes REAL, fantasy_pts REAL, double_double REAL, triple_double REAL,
    plus_minus REAL, offrtg REAL, defrtg REAL, netrtg REAL,
    ast_pct REAL, ast_to REAL, ast_ratio REAL,
    oreb_pct REAL, dreb_pct REAL, reb_pct REAL,
    to_ratio REAL, efg_pct REAL, ts_pct REAL,
    usg_pct REAL, pace REAL, pie REAL, poss REAL
)""")

# Table équipes : code et nom complet
cur.execute("""
CREATE TABLE IF NOT EXISTS teams (
    code TEXT PRIMARY KEY,
    nom TEXT NOT NULL
)""")

# Table stats top 15 joueurs 
cur.execute("""
CREATE TABLE IF NOT EXISTS stats_joueurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    joueur TEXT NOT NULL, pts_total REAL,
    pct_tirs REAL, pct_tirs3 REAL, pct_lf REAL,
    reb_off REAL, impact REAL
)""")

# Table stats par équipe
cur.execute("""
CREATE TABLE IF NOT EXISTS stats_equipes (
    code TEXT PRIMARY KEY,
    nom TEXT, nb_joueurs INTEGER, pts_total REAL
)""")

conn.commit()


# INGESTION PLAYERS 

print("Chargement des joueurs...")
# header=1 car la ligne 0 est un titre et la ligne 1 contient les noms de colonnes
df = pd.read_excel(CHEMIN_EXCEL, sheet_name="Données NBA", header=1)

# La colonne 3PM on la renomme manuellement, bon format
cols = list(df.columns)
cols[cols.index(pd.Timestamp('1900-01-01 15:00:00').time()
               if pd.Timestamp('1900-01-01 15:00:00').time() in cols
               else __import__('datetime').time(15, 0))] = '3PM'
df.columns = cols

# On ignore les colonnes vides
df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

ok, err = 0, 0
for _, row in df.iterrows():
    try:
        j = LigneJoueur(
            joueur=row["Player"], equipe=row.get("Team"),
            age=row.get("Age"), matchs_joues=row.get("GP"),
            victoires=row.get("W"), defaites=row.get("L"),
            minutes=row.get("Min"), pts=row.get("PTS"),
            tirs_reussis=row.get("FGM"), tirs_tentes=row.get("FGA"),
            pct_tirs=row.get("FG%"), tirs3_reussis=row.get("3PM"),
            tirs3_tentes=row.get("3PA"), pct_tirs3=row.get("3P%"),
            lf_reussis=row.get("FTM"), lf_tentes=row.get("FTA"),
            pct_lf=row.get("FT%"), reb_off=row.get("OREB"),
            reb_def=row.get("DREB"), reb_total=row.get("REB"),
            passes=row.get("AST"), pertes=row.get("TOV"),
            interceptions=row.get("STL"), contres=row.get("BLK"),
            fautes=row.get("PF"), fantasy_pts=row.get("FP"),
            double_double=row.get("DD2"), triple_double=row.get("TD3"),
            plus_minus=row.get("+/-"), offrtg=row.get("OFFRTG"),
            defrtg=row.get("DEFRTG"), netrtg=row.get("NETRTG"),
            ast_pct=row.get("AST%"), ast_to=row.get("AST/TO"),
            ast_ratio=row.get("AST RATIO"), oreb_pct=row.get("OREB%"),
            dreb_pct=row.get("DREB%"), reb_pct=row.get("REB%"),
            to_ratio=row.get("TO RATIO"), efg_pct=row.get("EFG%"),
            ts_pct=row.get("TS%"), usg_pct=row.get("USG%"),
            pace=row.get("PACE"), pie=row.get("PIE"),
            poss=row.get("POSS")
        )
        cur.execute("""
            INSERT INTO players VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (j.joueur, j.equipe, j.age, j.matchs_joues, j.victoires, j.defaites,
              j.minutes, j.pts, j.tirs_reussis, j.tirs_tentes, j.pct_tirs,
              j.tirs3_reussis, j.tirs3_tentes, j.pct_tirs3, j.lf_reussis,
              j.lf_tentes, j.pct_lf, j.reb_off, j.reb_def, j.reb_total,
              j.passes, j.pertes, j.interceptions, j.contres, j.fautes,
              j.fantasy_pts, j.double_double, j.triple_double, j.plus_minus,
              j.offrtg, j.defrtg, j.netrtg, j.ast_pct, j.ast_to, j.ast_ratio,
              j.oreb_pct, j.dreb_pct, j.reb_pct, j.to_ratio, j.efg_pct,
              j.ts_pct, j.usg_pct, j.pace, j.pie, j.poss))
        ok += 1
    except Exception as e:
        err += 1
        print(f"  Erreur : {e}")

print(f"  -> {ok} joueurs insérés, {err} erreurs")

# INGESTION TEAMS

print("Chargement des équipes...")
df_eq = pd.read_excel(CHEMIN_EXCEL, sheet_name="Equipe")
df_eq = df_eq.rename(columns={"Code": "code", "Nom complet de l'équipe": "nom"})

ok, err = 0, 0
for _, row in df_eq.iterrows():
    try:
        t = LigneEquipe(code=row["code"], nom=row["nom"])
        cur.execute("INSERT OR IGNORE INTO teams VALUES (?, ?)", (t.code, t.nom))
        ok += 1
    except Exception as e:
        err += 1
print(f"  -> {ok} équipes insérées, {err} erreurs")

# INGESTION STATS EQUIPES

print("Chargement des stats équipes...")
# Le header de la feuille Analyse est à la ligne 5 (index 5)
df_an = pd.read_excel(CHEMIN_EXCEL, sheet_name="Analyse", header=5)
# Liste des 30 codes NBA valides pour filtrer seulement les lignes équipes
CODES_NBA = {"ATL","BKN","BOS","CHA","CHI","CLE","DAL","DEN","DET","GSW",
             "HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK",
             "OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"}

df_eq_stats = df_an[["Code", "Nom complet de l'équipe",
                      "Nombre de joueur par équipe",
                      "Nombre de point total par équipe"]].dropna(subset=["Code"])
# On garde uniquement les lignes dont le code est un vrai code NBA
df_eq_stats = df_eq_stats[df_eq_stats["Code"].isin(CODES_NBA)]

ok, err = 0, 0
for _, row in df_eq_stats.iterrows():
    try:
        s = LigneStatEquipe(
            code=row["Code"], nom=row["Nom complet de l'équipe"],
            nb_joueurs=row.get("Nombre de joueur par équipe"),
            pts_total=row.get("Nombre de point total par équipe")
        )
        cur.execute("INSERT OR IGNORE INTO stats_equipes VALUES (?,?,?,?)",
                    (s.code, s.nom, s.nb_joueurs, s.pts_total))
        ok += 1
    except Exception as e:
        err += 1
        print(f"  Erreur : {e}")
print(f"  -> {ok} stats équipes insérées, {err} erreurs")

# INGESTION STATS JOUEURS (top 15 meilleurs)

print("Chargement du top 15...")
df_raw = pd.read_excel(CHEMIN_EXCEL, sheet_name="Analyse", header=None)
idx = df_raw[df_raw[0] == "Players"].index[0]
df_top = pd.read_excel(CHEMIN_EXCEL, sheet_name="Analyse", header=idx)
df_top = df_top.dropna(subset=["Players"]).head(15)

ok, err = 0, 0
for _, row in df_top.iterrows():
    try:
        s = LigneStat(
            joueur=row["Players"],
            pts_total=row.get("Nombre de point total"),
            pct_tirs=row.get("Pourcentage de tirs réussis"),
            pct_tirs3=row.get("Pourcentage de réussite aux tirs à 3 points"),
            pct_lf=row.get("Pourcentage de réussite aux lancers francs"),
            reb_off=row.get("Rebonds offensifs"),
            impact=row.get("Estimation de l'impact du joueur")
        )
        cur.execute("INSERT INTO stats_joueurs VALUES (NULL,?,?,?,?,?,?,?)",
                    (s.joueur, s.pts_total, s.pct_tirs, s.pct_tirs3,
                     s.pct_lf, s.reb_off, s.impact))
        ok += 1
    except Exception as e:
        err += 1
        print(f"  Erreur : {e}")
print(f"  -> {ok} stats joueurs insérées, {err} erreurs")

conn.commit()
conn.close()
print("Base SQLite créée : sportsee.db")
print("  Tables : players, teams, stats_joueurs, stats_equipes")