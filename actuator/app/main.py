"""Actionneur : SEUL composant qui touche au socket Docker (voir logic.py pour la liste blanche)."""
import os

import docker
from fastapi import FastAPI, Header, HTTPException

from .logic import Actuator, Denied

core = Actuator(docker.from_env(), os.environ["ACTUATOR_TOKEN"])
app = FastAPI(title="Actuator", docs_url=None, redoc_url=None, openapi_url=None)


def call(fn, *a):
    try:
        return fn(*a)
    except Denied as e:
        raise HTTPException(e.code, e.msg)


@app.post("/restart/{svc}")
def restart(svc: str, x_actuator_token: str | None = Header(None)):
    return call(core.restart, x_actuator_token, svc)


@app.post("/waf/reload")
def reload_waf(x_actuator_token: str | None = Header(None)):
    return call(core.reload_waf, x_actuator_token)


@app.get("/status")
def status(x_actuator_token: str | None = Header(None)):
    return call(core.status, x_actuator_token)


@app.get("/health")
def health():
    return {"ok": True}
