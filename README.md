# Assistant RAG avec Mistral

Ce projet implémente un assistant virtuel basé sur le modèle Mistral, utilisant la technique de Retrieval-Augmented Generation (RAG) enrichie d'un outil SQL, pour répondre aux questions sur la NBA à partir de discussions de fans (Reddit) et de statistiques (Excel).

## Architecture du système

Le système repose sur un routeur qui analyse chaque question et la dirige vers le bon outil :

- **Question contextuelle** (règles, événements..) -> `outil_rag` -> recherche sémantique FAISS dans les textes Reddit nettoyés -> 5 extraits les plus proches
- **Question chiffrée** (stats, pourcentages..) -> `outil_sql` -> le LLM écrit une requête SQL -> Python l'exécute sur `sportsee.db` (lecture seule) -> résultats bruts
- **Question mixte** (contexte + chiffres) -> la question est découpée -> les deux outils sont appelés

Le routeur fonctionne en trois étapes : le LLM (Mistral Large) décide de la source (rag, sql ou mixte, puis validée par Pydantic), Python appelle le ou les outils, puis le LLM rédige la réponse uniquement à partir des extraits et résultats obtenus. La question et la réponse sont validées par Pydantic, et chaque étape est tracée dans Logfire.

## Fonctionnalités

- 🔍 **Recherche sémantique** avec FAISS sur les textes Reddit nettoyés
- 🗄️ **Outil SQL** pour les questions chiffrées (statistiques, classements)
- 🔀 **Routeur** qui choisit automatiquement la source (RAG, SQL ou les deux)
- ✅ **Validation Pydantic** des données à chaque étape
- 📈 **Traçage Logfire** pas à pas
- 📊 **Évaluation RAGAS** avant/après l'ajout du SQL

## Prérequis

- Python 3.12
- Clé API Mistral (obtenue sur [console.mistral.ai](https://console.mistral.ai/))
- Token Logfire (obtenu sur [logfire.pydantic.dev](https://logfire.pydantic.dev/))

## Installation

1. **Cloner le dépôt**

```bash
git clone <url-du-repo>
cd <nom-du-repo>
```

2. **Créer un environnement virtuel**

```bash
# Création de l'environnement virtuel
python -m venv .venv

# Activation de l'environnement virtuel
# Sur Windows
.venv\Scripts\activate
# Sur macOS/Linux
source .venv/bin/activate
```

3. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

4. **Configurer les clés API**

Créez un fichier `.env` à la racine du projet (modèle : `.env.example`) :

```
MISTRAL_API_KEY=votre_clé_api_mistral
LOGFIRE_TOKEN=votre_token_logfire
```

## Structure du projet

```
.
├── MistralChat.py              # Application Streamlit principale
├── routeur_rag_sql.py          # Routeur RAG / SQL / mixte
├── sql_tool.py                 # Outil SQL : question -> requête -> résultats
├── load_excel_to_db.py         # Chargement de l'Excel dans la base SQLite
├── sportsee.db                 # Base SQLite (players, teams, reports, stats, matches)
├── indexer.py                  # Script pour indexer les documents
├── models.py                   # Modèles Pydantic (entrées / sorties)
├── logfire_setup.py            # Configuration du traçage Logfire
├── evaluate_ragas.py           # Évaluation RAGAS avant (RAG seul)
├── evaluate_ragas_apres.py     # Évaluation RAGAS après (RAG + SQL)
├── questions_test.json         # Jeu de questions de test
├── resultats_ragas_*.csv       # Résultats des évaluations
├── audit_chunks.py             # Audit du bruit dans les chunks (+ audit_avant.txt)
├── inputs/                     # Documents sources (PDF Reddit + Excel NBA)
├── data_prep/                  # Préparation des textes Reddit
│   ├── extraire_pdf.py         # OCR des PDF
│   ├── lignes_frequentes.py    # Détection des lignes répétées (bruit)
│   ├── nettoyage.py            # Règles de nettoyage
│   ├── nettoyer_textes.py      # Nettoyage + validation Pydantic
│   └── texte_propre/           # Textes nettoyés
├── vector_db/                  # Index FAISS et chunks
└── utils/                      # Modules utilitaires
    ├── config.py               # Configuration de l'application
    ├── data_loader.py          # Chargement des fichiers
    └── vector_store.py         # Gestion de l'index vectoriel
```

## Utilisation

La base SQL (`sportsee.db`) et l'index FAISS (`vector_db/`) sont déjà fournis dans le dépôt : après l'installation, l'application peut être lancée directement (étape 4). Les étapes 1 à 3 ne servent qu'à les reconstruire, par exemple après une mise à jour des fichiers sources.

### 1. Préparer les textes

```bash
python data_prep/extraire_pdf.py
python data_prep/nettoyer_textes.py
```

### 2. Indexer les documents

```bash
python indexer.py
```

Ce script charge les textes nettoyés (`data_prep/texte_propre/`), les découpe en chunks, génère les embeddings avec Mistral et sauvegarde l'index FAISS dans `vector_db/`.

### 3. Créer la base SQL

```bash
python load_excel_to_db.py
```

### 4. Lancer l'application

```bash
streamlit run MistralChat.py
```

L'application sera accessible à l'adresse http://localhost:8501 dans votre navigateur.

### 5. Évaluer le système

```bash
python evaluate_ragas.py          # avant : RAG seul
python evaluate_ragas_apres.py    # après : RAG + SQL
```

Les résultats et leur analyse sont présentés dans le rapport d'évaluation.

## Modules principaux

### `routeur_rag_sql.py`
Le LLM classe la question (rag, sql ou mixte), Python appelle le ou les outils, puis le LLM rédige la réponse à partir des seuls résultats obtenus.

### `sql_tool.py`
Le LLM écrit une requête SQL à partir du schéma, du dictionnaire des données et d'exemples ; Python l'exécute en lecture seule. Les questions hors des données disponibles sont signalées comme non disponibles.

### `utils/vector_store.py`
Gère l'index vectoriel FAISS et la recherche sémantique : découpage des documents, génération et validation des embeddings avec Mistral, création et interrogation de l'index.

### `logfire_setup.py`
Valide la question et la réponse avec Pydantic et trace chaque étape du pipeline dans Logfire.

## Personnalisation

Vous pouvez personnaliser l'application en modifiant les paramètres dans `utils/config.py` :
- Dossier des documents à indexer
- Taille des chunks et chevauchement
- Nombre de documents récupérés
- Modèle d'embeddings
