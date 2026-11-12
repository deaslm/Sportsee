# Audit de la qualité des chunks
import pickle
from collections import Counter

# 1. Charger les chunks de l'index
with open("vector_db/document_chunks.pkl", "rb") as f:
    chunks = pickle.load(f)

def famille(c):                          # classe chaque chunk dans une famille
    s = c["metadata"]["source"]
    if s.endswith((".pdf", ".txt")): return "PDF"   
    if "Analyse Vide" in s: return "Feuille vide"
    return "Excel"

pdf = [c for c in chunks if famille(c) == "PDF"]
excel = [c for c in chunks if "Données NBA" in c["metadata"]["source"]]

# 2. Répartition
print("Répartition :", dict(Counter(famille(c) for c in chunks)))

# 3. Bruit d'interface dans les PDF
BRUIT = ["Répondre", "Comm. du top", "Modifié il y a", "Accéder au contenu principal"]
n = sum(any(m in c["text"] for m in BRUIT) for c in pdf)
print(f"Bruit : {n} chunks pollués sur {len(pdf)}")

# 4. Chunks qui commencent en milieu de phrase (1re lettre en minuscule)
coupes = sum(c["text"].lstrip()[:1].islower() for c in pdf)
print(f"Début coupé : {coupes} sur {len(pdf)}")

# 5. OCR : points-virgules vs virgules
print("OCR : ';' =", sum(c["text"].count(";") for c in pdf),
      "| ',' =", sum(c["text"].count(",") for c in pdf))

# 6. Excel : chunks sans noms de colonnes / avec cases vides
print("Excel sans en-tête :", sum("Player" not in c["text"] for c in excel), "sur", len(excel))
print("Excel avec NaN :", sum("NaN" in c["text"] for c in excel), "sur", len(excel))

# 7. Doublons
textes = Counter(c["text"].strip() for c in chunks)
print("Doublons :", sum(v - 1 for v in textes.values() if v > 1))