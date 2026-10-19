"""Assistant local (systeme nerveux 'conscient'): aide les operateurs a comprendre un incident.
LECTURE SEULE par construction: aucun client vers l'actuator, aucun jeton d'action.
Le seul acces externe est un GET vers /state du remediator (etat courant, pour repondre avec le
contexte reel), jamais un POST vers une route qui agit sur le systeme."""
import os, re, time, json
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:3b-instruct")   # <= 8B, voir README pour alternatives
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
PERSIST_DIR = os.getenv("CHROMA_DIR", "/data/chroma")
REMEDIATOR_STATE_URL = os.getenv("REMEDIATOR_STATE_URL", "http://remediator:9000/state")
TOP_K = int(os.getenv("TOP_K", "4"))

SYSTEM_PROMPT = """Tu es l'assistant local de PROJECT RESILIENCE-ALPHA, une plateforme de paiement \
fictive avec reprise automatique inspiree du systeme immunitaire. Tu aides un operateur humain ou le \
jury a COMPRENDRE ce qui se passe. Regles strictes :
- Tu n'executes AUCUNE action. Tu n'as acces a aucune commande de redemarrage, de bannissement ou de \
suspension. Si on te demande d'agir, explique que seul le moteur de remediation automatique ou un \
operateur humain avec acces direct peut le faire, et oriente vers le runbook pertinent.
- Appuie-toi UNIQUEMENT sur le contexte documentaire fourni ci-dessous et sur l'etat live du systeme \
s'il est fourni. Si l'information n'y est pas, dis-le clairement plutot que d'inventer.
- Reponds en francais, de maniere concise et operationnelle (un operateur lit vite pendant un incident).
- Cite le document source entre parentheses, ex: (etats.md)."""

app = FastAPI(title="Assistant local (RAG)")
_store = None
_llm = None


def store():
    global _store
    if _store is None:
        emb = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
        _store = Chroma(collection_name="immune_corpus", embedding_function=emb, persist_directory=PERSIST_DIR)
    return _store


def llm():
    global _llm
    if _llm is None:
        _llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_URL, temperature=0.1, num_predict=500)
    return _llm


def live_state_snippet() -> str:
    """Lecture seule: un GET, rien d'autre. Resume court pour ne pas noyer le contexte RAG."""
    try:
        r = httpx.get(REMEDIATOR_STATE_URL, timeout=3)
        r.raise_for_status(); s = r.json()
    except Exception:
        return "(etat live indisponible pour le moment)"
    inc = s.get("incident") or {}
    return (f"Etat actuel: {s.get('state')}. Debit paiement autorise: {s.get('rules', {}).get('pay_rate')} req/s. "
            f"Comptes suspendus: {s.get('rules', {}).get('suspended_users') or 'aucun'}. "
            f"Comptes verrouilles: {list((s.get('rules', {}).get('locked_users') or {}).keys()) or 'aucun'}. "
            f"IP bannies: {s.get('rules', {}).get('banned_ips') or 'aucune'}. "
            f"Score detecteur: {s.get('detector', {}).get('score')}. "
            f"Incident en cours: {inc.get('id', 'aucun')} "
            + (f"(actions tentees: {[a['name'] for a in inc.get('actions', [])]})" if inc else ""))


class Ask(BaseModel):
    question: str
    include_live_state: bool = True


def retrieve(question: str):
    docs = store().similarity_search(question, k=TOP_K)
    ctx = "\n\n".join(f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs)
    sources = sorted({d.metadata.get("source", "?") for d in docs})
    return ctx, sources


@app.post("/ask")
def ask(a: Ask):
    if not a.question.strip():
        raise HTTPException(400, "question vide")
    ctx, sources = retrieve(a.question)
    live = live_state_snippet() if a.include_live_state else ""
    prompt = (f"{SYSTEM_PROMPT}\n\n--- Contexte documentaire ---\n{ctx}\n\n"
              f"--- Etat live (lecture seule) ---\n{live}\n\n--- Question ---\n{a.question}")
    t0 = time.perf_counter()
    try:
        resp = llm().invoke(prompt)
    except Exception as e:
        raise HTTPException(503, f"modele local indisponible: {e}")
    return {"answer": resp.content, "sources": sources, "latency_ms": round((time.perf_counter() - t0) * 1000)}


@app.get("/health")
def health():
    try:
        n = store()._collection.count()
    except Exception:
        n = 0
    return {"status": "ok", "indexed_chunks": n, "model": CHAT_MODEL}


@app.post("/reindex")
def reindex():
    """Reconstruit l'index depuis le corpus versionne (pas depuis les incidents live: voir memoire.md)."""
    from .ingest import build
    n_docs, n_chunks = build()
    global _store; _store = None
    return {"documents": n_docs, "chunks": n_chunks}
