# afficher quelques chunks 
import pickle 

# Ouvre le fichier des chunks 
with open("vector_db/document_chunks.pkl", "rb") as f:
    chunks = pickle.load(f)         

print("Nombre de chunks :", len(chunks))

numero = 50
c = chunks[numero]
print("Source :", c["metadata"]["source"])   # d'où vient ce chunk
print("Texte :")
print(c["text"])                              # ce que le LLM verra