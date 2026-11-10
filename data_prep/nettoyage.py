# Nettoyage des textes OCR (Reddit)

import re

# Lignes à jeter
BRUIT = re.compile(
    r"^("
    r"\d\d/\d\d/\d{4} .*|\d+/\d+|.*http.*|.*reddit\.com.*|.*r(Inba|/nba|lnba)|"             # dates, liens, en-tete de page
    r"R[ée]pondre|Partager|(?:Se )?connecter|(?:Accéder )?au contenu principal|"            # boutons et menus
    r"Rechercher.*|Rejoindre la conversation|Trier par.*|(?:Afficher )?plus de commentaires.*|(?:En )?savoir plus|"
    r"(\d+ )?réponses? supplémentaires?|"
    r"(?:du )?top \d+%?|"                    # "du top 1%" ou "top 1%""
    r"y a \d+ (j|m\.?)|"                      # reste de "il y a 1 m."
    r"[.·]\s*-?\d+\s*(j|m\.?)|"               # ". -1 m." isolé
    r"[\w_]+(l|1)$|"                          # morceau d'URL avec underscore
    r"[\d\s]{1,8}&[\d\s]*|"                   # nombres seuls jusqu'à 4 chiffres + "&" ("4 1 &")
    r".{1,3}|"                                # lignes très courtes (YA, U, ...)
    r"\d{1,3}( \d{1,3})*|"                    # petits nombres groupés à 3 chiffres max = votes (ex: "4 13")
    r")$")

# Début de la liste des autres fils de discussion Reddit (=bruit)
AUTRES_FILS = re.compile(r"^r[/I]\S+ +il ?y? ?a ?\d* ?(j|m\.?|a)?\.?$")

# Restes d'en-têtes de commentaires au milieu d'une ligne (fusionnés par l'OCR avec le texte voisin)
ENTETE_INLINE = re.compile(
    r"(?:\b\d{1,3}(?:\s+\d{1,3})?\s+)?R[ée]pondre\b"                  # bouton "Répondre" (+ votes avant)
    r"|(?:r[ée]ponse\s+)?suppl[ée]mentaire\b"                           # "réponse supplémentaire"
    r"|\bil y a\s*[~\-.]?\s*\d*\s*(?:j|m)\b\.?"                         # "il y a -1 m."
    r"|^a\s+\d+\s*j\b"                                                  # reste de "il y a 10j"
    r"|\S+\s+(?:A[Oo]\s+)?[~\-*.\s]*\d{1,3}\s*(?:j|m)\b\.?"            # pseudo + date ("hqppp AO -10 j")
    r"|(?:Comm[.;,]?|Auteur\S*)\s*du\s*top(?:\s*\d{1,2}\s*%?)?"         # badge "Comm. du top 1%" (et ses variantes OCR)
    r"|^:\s*"                                                           # deux-points isolé en début de ligne
)

def est_entete(l):
    """Vrai si la ligne contient une date ou un badge."""
    return bool(
        re.search(r"[~\-.]?\s*\d{1,3}\s*(j|m\.?)\b", l) or
        re.search(r"[~\-.]?\s*[A-Z]\s*(j|m\.?)\b", l) or   # "-Lm."
        re.search(r"(Comm[.;,]?|Auteur\S*)\s*du\s*top", l) or  # "Comm /Auteur-rice top"
        re.search(r"Modifié il y a", l) or
        re.match(r"^il y a", l)            # "il y a -1 m. Comm.."
    )

def nettoyer(texte):
    lignes = [l.strip() for l in texte.replace("\r", "").split("\n")]
    sortie, pub = [], False                        # sortie = liste qui stocke lignes propres ; pub = on est dans une publicité
    for i, l in enumerate(lignes):
        if AUTRES_FILS.match(l):
            break                                  # fin du contenu utile
        l = re.sub(r"(\s+[\dUu<]{1,3}){0,2}\s+R[ée]pondre$", "", l)  # enlève "répondre" et chiffres associés en fin de ligne
        if "Sponsoris" in l or "Télécharger" in l:
            pub = True                             # début d'une publicité
            continue
        l = re.sub(r"^(du top|Auteur[\w-]*\s*(?:rice\s*)?top)\s*\d*%?\s*", "", l).strip()   # efface les mentions du top/auteur du top
        # Cas 1 : pseudo seul (la ligne suivante est un en-tête)
        suivante = lignes[i + 1] if i + 1 < len(lignes) else ""
        if re.match(r"^\S+$", l) and est_entete(suivante):
            pub = False
            sortie.append("")                      # séparateur de commentaires
            continue                               # on jète le pseudo
        # Cas 2: en-tête normal (pseudo + date/badge sur la même ligne)
        if est_entete(l) and not re.match(r"^il y a", l):
            pub = False
            # On enlève tout jusqu'au texte du commentaire
            l = re.sub(
                r"^\S+(\s+\S+)?\s+"                                    # pseudo (1 ou 2 mots)
                r"'?\s*"                                              
                r"([~\-.]?\s*\d{0,3}\s*(j|m\.?)?\b\.?\s*)?"           
                r"(Modifié il y a\s*[~\-.]?\s*\d*\s*(j|m\.?)?\s*)?"   
                r"((?:m\.)?\s*(?:AO\s*)?(Comm[.;,]?|Auteur\S*)\s*du\s*top\s*\d{0,2}%?\s*)?",  
                "", l).strip()
            sortie.append("")
        # Cas 3: pour les lignes "il y a.." sans pseudo
        elif re.match(r"^il y a", l):
            pub = False
            l = re.sub(r"^il y a\s*[~\-.]?\s*\d*\s*(j|m\.?)?\s*"
               r"(Comm[.;,]?\s*du\s*top\s*\d{0,2}%?)?\s*", "", l).strip()
            sortie.append("")
        # Restes d'en-têtes au milieu d'une ligne : supprimés, le texte du commentaire est conservé
        l = re.sub(r"\s{2,}", " ", ENTETE_INLINE.sub(" ", l)).strip()
        if re.fullmatch(r"[\w\-]+", l):
            l = ""                                 # pseudo isolé restant (un seul mot sans ponctuation)
        if not pub and l and not BRUIT.match(l):
            sortie.append(l)                        # on garde la ligne si pas de pub, pas de bruit
    return "\n".join(sortie)                        # texte propre en sortie