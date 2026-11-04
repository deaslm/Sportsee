# Assistant RAG avec Mistral

Ce projet implémente un assistant virtuel basé sur le modèle Mistral, utilisant la technique (RAG) enrichie d'un agent SQL pour fournir des réponses précises sur les données NBA (contextuelles et chiffrées).

## Architecture du système

Le système repose sur un routeur intelligent qui analyse chaque question et la dirige vers le bon outil :

- **Question contextuelle** (règles, événements..) -> `outil_rag` → recherche sémantique FAISS dans les chunks Reddit -> génération Mistral Large
- **Question chiffrée** (stats, pourcentages..) -> `outil_sql` -> LangChain SQL Agent -> requête SQLite sur `sportsee.db` -> réponse structurée
- **Question mixte** (contexte + chiffres) -> les deux outils sont appelés -> réponse synthétisée

Le routeur est un agent ReAct (Reasoning + Acting) : il raisonne sur la question, choisit l'outil adapté, exécute, observe le résultat, puis formule la réponse finale.

## Fonctionnalités

- 🔍 **Recherche sémantique** avec FAISS pour les questions contextuelles
- 🤖 **Génération de réponses** avec Mistral Large
- 🗄️ **Agent SQL** pour les questions chiffrées 
- 🔀 **Routeur rag/sql** qui détecte le type de question
- 📊 **Évaluation RAGAS** avec Pydantic et traçage Logfire
- ⚙️ **Paramètres personnalisables** (modèle, nombre de documents, score minimum)

## Prérequis

- Python 3.9+
- Clé API Mistral (obtenue sur [console.mistral.ai](https://console.mistral.ai/))
- Token Logfire (traçage)

## Installation

1. **Cloner le dépôt**

```bash
git clone <url-du-repo>
cd <nom-du-repo>
```

2. **Créer un environnement virtuel**

```bash
python -m venv .venv

# Activation
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

3. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

4. **Configurer les clés API**

Créez un fichier `.env` à la racine :

```
MISTRAL_API_KEY=votre_clé_api_mistral
LOGFIRE_TOKEN=votre_token_logfire
```

## Structure du projet

```
.
├── inputs/                     # Documents sources (PDF Reddit + NBA.xlsx)
├── data_prep/                  # Scripts de préparation des données
│   ├── extraire_pdf.py         # Extraction texte brut des PDF
│   ├── nettoyage.py            # Nettoyage OCR
│   ├── nettoyer_textes.py      # Nettoyage complet
│   ├── lignes_frequentes.py    # Détection lignes répétitives
│   └── chunker_reddit.py       # Découpage en chunks
├── utils/                      # Modules utilitaires
│   ├── config.py               # Configuration globale
│   ├── data_loader.py          # Chargement des données
│   └── vector_store.py         # Gestion index FAISS
├── vector_db/                  # Index FAISS et chunks
│   ├── faiss_index.idx
│   └── document_chunks.pkl
├── indexer.py                  # Indexation des documents
├── charger_excel_db.py         # Chargement Excel en SQLite
├── sportsee.db                 # Base SQLite (générée par charger_excel_db.py)
├── sql_tool.py                 # Agent SQL LangChain
├── routeur_rag_sql.py          # Routeur RAG + SQL
├── evaluate_ragas.py           # Évaluation RAGAS avant intégration SQL
├── evaluate_ragas_après.py     # Évaluation RAGAS après intégration SQL
├── logfire_setup.py            # Configuration traçage Logfire
├── MistralChat.py              # Interface Streamlit
├── resultats_ragas_avant.csv   # Scores RAGAS avant
├── resultats_ragas_apres.csv   # Scores RAGAS après
└── .env.example                # Exemple de configuration
```

## Utilisation

### 1. Préparer les données textuelles

```bash
# Extraire le texte des PDFs
python data_prep/extraire_pdf.py

# Nettoyer les textes extraits
python data_prep/nettoyer_textes.py
```

### 2. Indexer les documents

```bash
python indexer.py
```

Génère l'index FAISS dans `vector_db/`.

### 3. Charger les données Excel en base SQL

```bash
python charger_excel_db.py
```

Génère `sportsee.db` avec les tables `players`, `teams`, `stats_joueurs`, `stats_equipes`.

### 4. Lancer le routeur

```python
from routeur_rag_sql import repondre

# Question contextuelle -> outil_rag
repondre("Qu'est-ce que le play-in tournament NBA ?")

# Question chiffrée -> outil_sql
repondre("Quel joueur a le meilleur pourcentage à 3 points ?")
```

### 5. Lancer l'interface Streamlit

```bash
streamlit run MistralChat.py
```

### 6. Évaluer les performances

```bash
# Évaluation avant intégration SQL
python evaluate_ragas.py

# Évaluation après intégration SQL
python evaluate_ragas_apres.py
```

## Évaluation RAGAS — Résultats comparatifs

Catégorie | faithfulness avant | faithfulness après | Évolution 
----------|--------------------|--------------------|-----------
bruité    | 0.881              | **0.950**          | +0.069 
simple    | 0.639              | **0.650**          | +0.011 
complexe  | 0.750              | 0.000              | - 
mixte     | -                  | 0.240              | nouveau 


## Modules principaux

### `MistralChat.py`
Application Streamlit principale : interface de chat, appel au pipeline RAG, affichage des réponses.

### `utils/vector_store.py`
Gère l'index vectoriel FAISS et la recherche sémantique : chargement et découpage des documents, génération des embeddings avec Mistral, création et interrogation de l'index FAISS.

### `utils/query_classifier.py`
Détermine si une requête nécessite une recherche RAG : analyse des mots-clés, classification avec le modèle Mistral, détection des questions spécifiques vs générales.

### `utils/database.py`
Gère la base de données SQLite pour les interactions : enregistrement des questions et réponses, stockage des feedbacks utilisateurs, récupération des statistiques.

### `charger_excel_db.py`
Charge le fichier `regular NBA.xlsx` dans une base SQLite (`sportsee.db`) avec 4 tables : `players`, `teams`, `stats_joueurs`, `stats_equipes`.

### `routeur_rag_sql.py`
Agent ReAct (LangChain) qui route automatiquement les questions vers `outil_rag` (FAISS + Mistral) ou `outil_sql` (LangChain SQL Agent) selon leur nature. Utilise `mistral-large-latest` pour garantir le respect du format ReAct.

### `sql_tool.py`
Agent SQL LangChain connecté à `sportsee.db`. Utilise `sample_rows_in_table_info=0` pour forcer l'exécution des requêtes SQL plutôt que de déduire les réponses depuis les exemples de lignes affichés dans le schéma.

### `evaluate_ragas.py` / `evaluate_ragas_apres.py`
Scripts d'évaluation automatique avec RAGAS (faithfulness, context_precision, context_recall). Utilisent Pydantic pour valider les entrées/sorties.

### `logfire_setup.py`
Traçage structuré du pipeline RAG avec Logfire pour monitorer les étapes clés, les erreurs et les performances du pipeline.

## Personnalisation

Vous pouvez personnaliser l'application en modifiant les paramètres dans `utils/config.py` :
- Modèles Mistral utilisés
- Taille des chunks et chevauchement
- Nombre de documents par défaut
- Nom de la commune ou organisation
