"""Persistance locale des habilitations faciales : un modèle LBPH par utilisateur, sur son propre volume
(`facedata`), SANS lien avec la base de paiements. Cloisonnement volontaire (voir docs/face-auth.md) :
une compromission de ce service n'expose ni les comptes, ni les soldes, ni les secrets des autres."""
import json, os, shutil, time

import cv2

DATA_DIR = os.getenv("DATA_DIR", "/data")


def _user_dir(username: str) -> str:
    d = os.path.join(DATA_DIR, username)
    os.makedirs(d, exist_ok=True)
    return d


def _model_path(username: str) -> str:
    return os.path.join(_user_dir(username), "model.yml")


def _meta_path(username: str) -> str:
    return os.path.join(_user_dir(username), "meta.json")


def has_enrollment(username: str) -> bool:
    return os.path.exists(_model_path(username))


def save_model(username: str, recognizer, n_images: int):
    recognizer.write(_model_path(username))
    with open(_meta_path(username), "w") as f:
        json.dump({"enrolled_at": time.time(), "n_images": n_images}, f)


def load_model(username: str):
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(_model_path(username))
    return recognizer


def delete_enrollment(username: str):
    d = os.path.join(DATA_DIR, username)
    if os.path.isdir(d):
        shutil.rmtree(d)


def list_enrollments() -> dict:
    out = {}
    if not os.path.isdir(DATA_DIR):
        return out
    for username in sorted(os.listdir(DATA_DIR)):
        mp = os.path.join(DATA_DIR, username, "meta.json")
        if os.path.exists(mp):
            with open(mp) as f:
                out[username] = json.load(f)
    return out
