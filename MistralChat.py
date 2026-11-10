# MistralChat.py (version RAG + SQL)
# Interface Streamlit de l'assistant NBA : chaque question passe par le routeur RAG/SQL,
# avec validation Pydantic des entrées/sorties et traces Logfire pas à pas

import streamlit as st
import logging
from pydantic import ValidationError

# --- Importations depuis vos modules ---
try:
    from utils.config import APP_TITLE, NAME
    from routeur_rag_sql import repondre_avec_contextes, vs
    from logfire_setup import rag_trace          
except ImportError as e:
    st.error(f"Erreur d'importation: {e}. Vérifiez la structure de vos dossiers et les fichiers du projet.")
    st.stop()


# --- Configuration du Logging (msg dans le terminal) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# --- Vérification de l'index documentaire (chargé par le routeur) ---
if vs.index is None or not vs.document_chunks:
    st.warning("L'index documentaire n'est pas chargé. Exécutez 'python indexer.py' pour le construire.")
    logging.error("Index Faiss ou chunks non chargés.")


# --- Initialisation de l'historique de conversation ---
if "messages" not in st.session_state:
    # Message d'accueil initial
    st.session_state.messages = [{"role": "assistant", "content": f"Bonjour ! Je suis votre analyste IA pour la {NAME}. Posez-moi vos questions sur les équipes, les joueurs ou les statistiques, et je vous répondrai en me basant sur nos données."}]


# --- Fonctions ---

def pipeline_chat(question: str):
    """Appelle le routeur RAG/SQL et renvoie (réponse, contextes) au format attendu par rag_trace."""
    reponse, contextes, outils = repondre_avec_contextes(question)
    if reponse is None:
        raise RuntimeError("le service est momentanément indisponible")
    logging.info(f"Outils utilisés : {outils}")
    return reponse, contextes


# --- Interface Utilisateur Streamlit ---
st.title(APP_TITLE)
st.caption(f"Assistant virtuel pour {NAME} | Recherche documentaire + base de statistiques")

# Affichage des messages de l'historique
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Zone de saisie utilisateur
if prompt := st.chat_input(f"Posez votre question sur la {NAME}..."):
    # 1. Ajouter et afficher le message de l'utilisateur
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # 2. Générer la réponse via le routeur (RAG, SQL ou les deux selon la question)
    with st.chat_message("assistant"):
        with st.spinner("Recherche en cours..."):
            try:
                # rag_trace : validation Pydantic de la question et de la réponse + traces Logfire
                response_content = rag_trace(prompt, pipeline_chat, categorie="chat").reponse
            except ValidationError:
                # Question vide ou trop courte, ou réponse générée invalide
                logging.warning(f"Validation Pydantic échouée pour la question : {prompt!r}")
                response_content = "Je n'ai pas pu traiter cette question. Pouvez-vous la reformuler en quelques mots ?"
            except Exception:
                logging.exception("Erreur pendant le traitement de la question")
                response_content = ("Je suis désolé, une erreur technique m'empêche de répondre. "
                                    "Veuillez réessayer dans quelques instants.")

        # 3. Afficher la réponse
        st.write(response_content)

    # 4. Ajouter la réponse de l'assistant à l'historique 
    st.session_state.messages.append({"role": "assistant", "content": response_content})

# Petit pied de page optionnel
st.markdown("---")
st.caption("Powered by Mistral AI, Faiss & SQLite | Data-driven NBA Insights")