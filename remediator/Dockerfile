FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -u 10001 app && mkdir -p /data && chown 10001 /data
USER 10001
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","9000","--no-access-log"]
