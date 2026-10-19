FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Tourne en root dans le conteneur car il doit lire le socket Docker ; compensé dans docker-compose
# (read_only, cap_drop ALL, no-new-privileges, réseau interne dédié, jeton d'accès).
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","9200","--no-access-log"]
