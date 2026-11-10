# Applique le nettoyage aux 4 textes et valide chaque texte propre avec Pydantic avant de l'enregistrer

from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from nettoyage import nettoyer

ENTREE = Path("data_prep/texte_brut")
SORTIE = Path("data_prep/texte_propre")
SORTIE.mkdir(exist_ok=True)                       # crée le dossier de sortie

# Mêmes mots que dans audit_chunks.py pour comparer bruit avant/après
BRUIT = ["Répondre", "Comm. du top", "Modifié il y a", "Accéder au contenu principal"]

def nb_bruit(texte):                              # nombre de lignes qui contiennent un mot de bruit
    return sum(any(m in l for m in BRUIT) for l in texte.split("\n"))


class TexteNettoye(BaseModel):
    """Valide un texte nettoyé avant de l'enregistrer : assez long et sans bruit d'interface Reddit."""
    source: str
    texte: str = Field(min_length=500)           # un texte quasi vide signalerait un nettoyage qui a tout supprimé

    @field_validator("texte")
    @classmethod
    def sans_bruit(cls, v):
        restant = nb_bruit(v)
        if restant > 0:
            raise ValueError(f"{restant} lignes contiennent encore du bruit d'interface Reddit")
        return v


for f in sorted(ENTREE.glob("*.txt")):
    brut = f.read_text(encoding="utf-8")
    propre = nettoyer(brut)                       # nettoie le fichier
    valide = TexteNettoye(source=f.name, texte=propre)          # validation Pydantic : erreur si texte vide ou bruité
    (SORTIE / f.name).write_text(valide.texte, encoding="utf-8")  # on enregistre le texte nettoyé et validé
    print(f"{f.name}: {len(brut)} -> {len(propre)} caractères | "
          f"lignes avec bruit : {nb_bruit(brut)} -> {nb_bruit(propre)}")