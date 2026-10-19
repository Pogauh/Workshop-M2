# PC Attaquant en conteneur (profil « lab », réseau interne uniquement) : exécute les scripts fournis dans ce dossier.
# docker compose --profile lab run --rm attacker python flood.py --password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)" --target http://waf:8080
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -u 10001 app
USER 10001
CMD ["python", "flood.py"]
