"""Construit (ou reconstruit) l'index vectoriel a partir du corpus en lecture seule.
Corpus = docs/ (architecture, EBIOS, PCA/PRA) + runbooks d'incident + description des APIs.
Rien dans ce dossier n'est ecrit par le reste du systeme : c'est une base documentaire statique,
versionnee avec le code, pas une memoire qui s'auto-modifie a partir d'evenements non verifies."""
import glob, hashlib, os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import MarkdownTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
PERSIST_DIR = os.getenv("CHROMA_DIR", "/data/chroma")
CORPUS_DIRS = ["/app/corpus/runbooks", "/app/corpus/docs"]


def load_docs():
    paths = []
    for d in CORPUS_DIRS:
        paths += glob.glob(os.path.join(d, "**/*.md"), recursive=True)
    docs = []
    for p in paths:
        for d in TextLoader(p, encoding="utf-8").load():
            d.metadata["source"] = os.path.relpath(p, "/app/corpus")
            docs.append(d)
    return docs


def build():
    docs = load_docs()
    if not docs:
        raise RuntimeError("corpus vide: verifier /app/corpus")
    chunks = MarkdownTextSplitter(chunk_size=800, chunk_overlap=120).split_documents(docs)
    emb = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
    store = Chroma(collection_name="immune_corpus", embedding_function=emb, persist_directory=PERSIST_DIR)
    # reindexation complete simple: coherent avec un petit corpus qui change peu
    try:
        ids = store.get()["ids"]
        if ids: store.delete(ids=ids)
    except Exception:
        pass
    store.add_documents(chunks)
    return len(docs), len(chunks)


if __name__ == "__main__":
    n_docs, n_chunks = build()
    print(f"index construit: {n_docs} documents, {n_chunks} fragments")
