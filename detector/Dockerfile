FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Modèle livré avec le dépôt (voir scripts/export_model.sh) : utilisé si /data/model.joblib n'existe pas encore
COPY model ./model
RUN useradd -u 10001 app && mkdir -p /data && chown 10001 /data
USER 10001
CMD ["python","-m","app.main"]
