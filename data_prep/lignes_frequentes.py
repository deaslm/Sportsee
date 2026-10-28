# repère les lignes qui reviennent le plus (= bruit probable)
from pathlib import Path
from collections import Counter

compteur = Counter()                                  # va compter chaque ligne
for fichier in Path("data_prep/texte_brut").glob("*.txt"):
    for ligne in fichier.read_text(encoding="utf-8").split("\n"):
        ligne = ligne.strip()                         # enlève les espaces autour
        if ligne:                                     # ignore les lignes vides
            compteur[ligne] += 1

# Affiche les 50 lignes les plus fréquentes avec leur nombre d'apparitions
for ligne, n in compteur.most_common(40):
    print(f"{n:4d}  {ligne}")