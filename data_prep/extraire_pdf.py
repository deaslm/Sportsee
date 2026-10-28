# lit les PDF (images) avec l'OCR
import time
from pathlib import Path
import fitz            # pour ouvrir le PDF et transformer une page en image
import easyocr         # OCR : lit le texte contenu dans une image
import numpy as np     # pour convertir l'image en tableau de pixels

PAGES_MAX = None        # lire toutes les pages
SORTIE = Path("data_prep/texte_brut")
SORTIE.mkdir(parents=True, exist_ok=True)   # crée le dossier s'il n'existe pas

reader = easyocr.Reader(["en", "fr"])       # charge le modèle OCR

for pdf in sorted(Path("inputs").glob("*.pdf")):   # pour chaque PDF du dossier inputs
    doc = fitz.open(pdf)
    textes = []
    debut = time.time()
    for i, page in enumerate(doc):
        if PAGES_MAX and i >= PAGES_MAX:
            break                                   # on s'arrête après PAGES_MAX pages
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))   # page -> image (zoom x2)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        blocs = reader.readtext(img, detail=0, paragraph=True)    # liste de blocs de texte
        textes.append("\n".join(blocs))
    (SORTIE / f"{pdf.stem}.txt").write_text("\n\n".join(textes), encoding="utf-8")
    print(f"{pdf.name} : {len(textes)} page(s) en {time.time() - debut:.0f} s")