"""Service de reconnaissance faciale (IA légère, OpenCV/LBPH, CPU) — consigne additionnelle 1 :
confirme l'identifiant saisi par une capture caméra AVANT d'autoriser la saisie du mot de passe.
Isolé : aucun accès à la base de paiements ni à l'actuator ; émet un billet signé (ticket.py) que seul
`auth` sait vérifier (FACE_TICKET_KEY partagé, aucun appel réseau entre les deux services).

Flux (voir docs/face-auth.md pour le détail complet) :
  1. POST /face/verify   {username, image}     -> reconnu ? billet signé + LED verte clignotante
                                                    non reconnu ? LED rouge fixe 30s, compte les échecs
  2. (côté navigateur) saisie du mot de passe, POST /auth/login avec le billet
  3. Gestion des habilitations (back-office, JWT requis) : /face/enroll, /face/enrollments, /face/enroll/{username}

Routes préfixées par /face (même convention que /api/ dans api/app/main.py) : le WAF (waf/nginx.conf,
`location /face/`) transmet le chemin SANS le réécrire, contrairement à un reverse-proxy qui le retirerait."""
import base64, os, time

import jwt
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import esp_led, lockout, recognizer, store, ticket

JWT_SECRET = os.environ["JWT_SECRET"]            # même secret que auth/api : un jeton de session valide suffit
MAX_IMAGE_B64 = 600_000                           # ~450 Ko décodés : large marge pour un JPEG webcam, borné contre l'abus
MIN_ENROLL_IMAGES = 3

app = FastAPI(title="Face Recognition")


# ---------- auth des routes de gestion (back-office uniquement) ----------
def _bearer_claims(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    try:
        return jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid token")


def _require_self_or_backoffice(authorization: str | None, target_username: str) -> dict:
    claims = _bearer_claims(authorization)
    if claims["sub"] != target_username and claims.get("role") != "backoffice":
        raise HTTPException(403, "réservé au titulaire du compte ou à un opérateur back-office")
    return claims


def _require_backoffice(authorization: str | None) -> dict:
    claims = _bearer_claims(authorization)
    if claims.get("role") != "backoffice":
        raise HTTPException(403, "réservé à un opérateur back-office")
    return claims


def _decode_b64_image(b64: str) -> bytes:
    if len(b64) > MAX_IMAGE_B64:
        raise HTTPException(413, "image trop volumineuse")
    try:
        return base64.b64decode(b64, validate=True)
    except Exception:
        raise HTTPException(400, "image: base64 invalide")


# ---------- vérification (pré-authentification, appelée depuis le navigateur) ----------
class VerifyIn(BaseModel):
    username: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    image: str = Field(min_length=1)   # JPEG/PNG encodé en base64


@app.post("/face/verify")
def verify(body: VerifyIn):
    # Réponse 200 avec `recognized:false` même en cas de verrou : le corps JSON porte toute l'information
    # (locked_until, retry_after_s) sans la nicher sous un `detail` d'erreur que le client ne lirait pas
    # uniformément (voir web/src/lib/api.js : seul un `detail` CHAÎNE est propagé sur une erreur HTTP).
    locked_until = lockout.is_locked(body.username)
    if locked_until:
        esp_led.set_led("off")
        return {"recognized": False, "locked": True, "locked_until": locked_until,
                "retry_after_s": round(locked_until - time.time())}

    raw = _decode_b64_image(body.image)
    try:
        img = recognizer.decode_image(raw)
    except ValueError:
        raise HTTPException(400, "image illisible")

    # Aucune inscription pour ce compte : amorçage — on laisse passer au mot de passe seul, l'opérateur
    # enregistrera son visage ensuite depuis le back-office (voir docs/face-auth.md, §amorçage).
    if not store.has_enrollment(body.username):
        t = ticket.issue(body.username)
        esp_led.set_led("green_blink")
        return {"recognized": True, "bootstrap": True, "ticket": t, "expires_in": ticket.TTL_S}

    face = recognizer.extract_face(img)
    if face is not None:
        model = store.load_model(body.username)
        ok, confidence = recognizer.verify_face(model, face)
    else:
        ok, confidence = False, None

    if ok:
        lockout.record_success(body.username)
        t = ticket.issue(body.username)
        esp_led.set_led("green_blink")
        return {"recognized": True, "bootstrap": False, "ticket": t, "expires_in": ticket.TTL_S, "confidence": confidence}

    just_locked = lockout.record_failure(body.username)
    esp_led.set_led("red_solid_30")
    return {"recognized": False, "confidence": confidence, "locked_until": just_locked,
            "retry_after_s": (round(just_locked - time.time()) if just_locked else None)}


# ---------- gestion des habilitations (back-office) ----------
class EnrollIn(BaseModel):
    username: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    images: list[str] = Field(min_length=MIN_ENROLL_IMAGES, max_length=20)


@app.post("/face/enroll")
def enroll(body: EnrollIn, authorization: str | None = Header(None)):
    _require_self_or_backoffice(authorization, body.username)
    faces = []
    for b64 in body.images:
        raw = _decode_b64_image(b64)
        try:
            img = recognizer.decode_image(raw)
        except ValueError:
            continue
        f = recognizer.extract_face(img)
        if f is not None:
            faces.append(f)
    if len(faces) < MIN_ENROLL_IMAGES:
        raise HTTPException(422, f"visage net détecté sur seulement {len(faces)} photo(s) (minimum {MIN_ENROLL_IMAGES}) : "
                                  "reprenez des photos mieux cadrées, un seul visage par photo, bon éclairage")
    model = recognizer.train_model(faces)
    store.save_model(body.username, model, len(faces))
    lockout.reset(body.username)
    return {"ok": True, "username": body.username, "n_images": len(faces)}


@app.get("/face/enrollments")
def enrollments(authorization: str | None = Header(None)):
    _require_backoffice(authorization)
    return store.list_enrollments()


@app.get("/face/enroll/status")
def enroll_status(username: str, authorization: str | None = Header(None)):
    _require_self_or_backoffice(authorization, username)
    return {"username": username, "enrolled": store.has_enrollment(username)}


@app.delete("/face/enroll/{username}")
def unenroll(username: str, authorization: str | None = Header(None)):
    _require_self_or_backoffice(authorization, username)
    store.delete_enrollment(username)
    lockout.reset(username)
    return {"ok": True, "username": username}


@app.post("/face/reset")
def reset_lockout(username: str, authorization: str | None = Header(None)):
    """Remise à zéro de laboratoire (voir scripts/reset.sh) : lève un blocage de reconnaissance en cours."""
    _require_backoffice(authorization)
    lockout.reset(username)
    return {"ok": True}


@app.get("/face/health")
def health():
    return {"status": "ok"}
