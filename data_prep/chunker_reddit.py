# Découpage des textes Reddit nettoyés en chunks par commentaire

from pathlib import Path

ENTREE = Path("data_prep/texte_propre")
SORTIE = Path("data_prep/chunks_reddit")
SORTIE.mkdir(exist_ok=True)

MAX_CHARS = 1500  # taille max d'un chunk

def chunker(texte, source):
    """Découpe par commentaire (séparateur = ligne vide). """
    chunks = []
    commentaire = []

    for ligne in texte.split("\n"):
        if ligne.strip() == "":          # ligne vide = fin d'un commentaire
            bloc = "\n".join(commentaire).strip()
            if len(bloc) > 30:           # on ignore les blocs trop courts (mots isolés par ex inutiles)
                # Si le commentaire est trop long, on le coupe
                while len(bloc) > MAX_CHARS:
                    chunks.append({"text": bloc[:MAX_CHARS], "metadata": {"source": source}})
                    bloc = bloc[MAX_CHARS:]
                if bloc:
                    chunks.append({"text": bloc, "metadata": {"source": source}})
            commentaire = []
        else:
            commentaire.append(ligne)

    return chunks

tous_chunks = []
for f in sorted(ENTREE.glob("*.txt")):
    texte = f.read_text(encoding="utf-8")
    chunks = chunker(texte, f.name)
    tous_chunks.extend(chunks)
    print(f"{f.name} : {len(chunks)} chunks")

print(f"Total : {len(tous_chunks)} chunks Reddit")