"""Reconnaissance faciale légère (IA « classique », pas de deep learning) : détection par cascade de Haar
+ reconnaissance par LBPH (Local Binary Patterns Histograms), toutes deux fournies par OpenCV. Choisi pour
rester cohérent avec « IA légère » (consigne additionnelle) : CPU uniquement, aucun modèle à télécharger,
entraînement par utilisateur en quelques millisecondes, aucune dépendance lourde (pas de dlib/PyTorch).

Pur (aucune E/S disque ni réseau) : testable avec de simples images de test, voir tests/test_recognizer.py.
Limites documentées dans docs/face-auth.md (§IA) : adapté à un petit groupe en conditions contrôlées, pas
à de la reconnaissance faciale à grande échelle ou en conditions d'éclairage variables."""
import cv2
import numpy as np

FACE_SIZE = (200, 200)
MIN_FACE_PX = (80, 80)
# LBPH : la "confiance" est une DISTANCE (0 = correspondance parfaite). Au-delà de ce seuil, on rejette.
# Valeur de départ usuelle en conditions contrôlées (webcam, visage de face, bon éclairage) ; à RECALIBRER
# empiriquement une fois de vraies photos d'inscription disponibles (voir docs/face-auth.md).
DEFAULT_CONFIDENCE_MAX = 70.0

_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def decode_image(raw: bytes) -> np.ndarray:
    """Décode un JPEG/PNG brut en image BGR OpenCV. Lève ValueError si le flux n'est pas une image valide."""
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("image illisible (format non supporté ou flux corrompu)")
    return img


def extract_face(img: np.ndarray):
    """Retourne le visage détecté, recadré et normalisé (niveaux de gris, 200x200, histogramme égalisé),
    ou None si aucun visage NET et UNIQUE n'est trouvé (0 visage = personne non positionnée ; >1 visage =
    ambigu, on ne devine jamais qui authentifier)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = _detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=MIN_FACE_PX)
    if len(faces) != 1:
        return None
    x, y, w, h = faces[0]
    return cv2.resize(gray[y:y + h, x:x + w], FACE_SIZE)


def train_model(face_images: list[np.ndarray]) -> cv2.face.LBPHFaceRecognizer:
    """Entraîne un modèle LBPH sur plusieurs photos d'UNE SEULE personne (un modèle par utilisateur,
    jamais partagé : voir store.py)."""
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    labels = np.zeros(len(face_images), dtype=np.int32)
    recognizer.train(face_images, labels)
    return recognizer


def verify_face(recognizer: "cv2.face.LBPHFaceRecognizer", face_image: np.ndarray,
                 confidence_max: float = DEFAULT_CONFIDENCE_MAX) -> tuple[bool, float]:
    """(reconnu, confiance LBPH — plus bas = plus proche du modèle entraîné)."""
    _, confidence = recognizer.predict(face_image)
    return confidence <= confidence_max, float(confidence)
