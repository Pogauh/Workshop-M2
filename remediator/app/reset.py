"""Reset de laboratoire : docker compose exec remediator python -m app.reset"""
import os, httpx
r = httpx.post("http://localhost:9000/reset", headers={"X-Admin-Token": os.environ["INTERNAL_TOKEN"]}, timeout=60)
print(r.status_code, r.text)
