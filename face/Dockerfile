FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# libglib2.0-0 : seule dépendance système requise par opencv-contrib-python-headless sur une image slim
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -u 10001 app && mkdir -p /data && chown 10001 /data
USER 10001
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8600","--no-access-log"]
