#!/bin/sh
# À lancer une fois, après "docker compose --profile ai up -d", pour préparer l'assistant local.
set -eu
cd "$(dirname "$0")/.."
DC="docker compose --profile ai"
echo "Téléchargement des modèles Ollama (peut prendre plusieurs minutes la première fois)..."
$DC exec ollama ollama pull nomic-embed-text
$DC exec ollama ollama pull "${ASSISTANT_CHAT_MODEL:-qwen2.5:3b-instruct}"
echo "Construction de l'index documentaire (RAG)..."
$DC exec assistant python -m app.ingest
echo "Assistant prêt : http://localhost:3002"
