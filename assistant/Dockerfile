FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir -U pip
COPY assistant/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY assistant/app ./app
COPY assistant/corpus/runbooks ./corpus/runbooks
COPY docs ./corpus/docs
RUN useradd -u 10001 app && mkdir -p /data && chown 10001 /data
USER 10001
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8500","--no-access-log"]
