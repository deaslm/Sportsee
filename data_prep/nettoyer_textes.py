# applique le nettoyage aux 4 textes

from pathlib import Path
from nettoyage import nettoyer

ENTREE = Path("data_prep/texte_brut")
SORTIE = Path("data_prep/texte_propre")
SORTIE.mkdir(exist_ok=True)                       # crée le dossier de sortie

# Mêmes mots que dans audit_chunks.py pour comparer bruit avant/après)
BRUIT = ["Répondre", "Comm. du top", "Modifié il y a", "Accéder au contenu principal"]

def nb_bruit(texte):                              # nombre de lignes qui contiennent un mot de bruit
    return sum(any(m in l for m in BRUIT) for l in texte.split("\n"))

for f in sorted(ENTREE.glob("*.txt")):
    brut = f.read_text(encoding="utf-8")
    propre = nettoyer(brut)                       # nettoie le fichier
    (SORTIE / f.name).write_text(propre, encoding="utf-8")      # on enregistre le texte nettoyé dans texte_propre
    print(f"{f.name}: {len(brut)} -> {len(propre)} caractères | "
          f"lignes avec bruit : {nb_bruit(brut)} -> {nb_bruit(propre)}")