"""Tests du cœur de reconnaissance (recognizer.py). Pur : aucune caméra, aucun réseau, données synthétiques.

LIMITE ASSUMÉE : la cascade de Haar (détection) est entraînée sur de vrais visages photographiés — elle
ne peut pas être testée positivement avec des images générées ici (aucun visage réel disponible dans cet
environnement). On teste donc : (a) la détection NÉGATIVE (rien à détecter sur une image unie — fiable,
ne dépend pas d'un visage réel), et (b) l'entraînement/la comparaison LBPH directement sur des motifs
200x200 synthétiques, en contournant la détection — ce qui exerce réellement la logique de reconnaissance
(train_model/verify_face), juste pas le cadrage caméra. Validation de bout en bout avec de vrais visages :
voir la procédure manuelle dans docs/face-auth.md (§vérification).

SEUIL PAR DÉFAUT NON VALIDÉ ICI : ces motifs synthétiques (texture générée, pas de vrai visage) sont
nettement moins discriminants que de vraies photos sous LBPH — un premier jeu de tests a montré qu'une
identité synthétique différente peut passer sous DEFAULT_CONFIDENCE_MAX=70.0, alors que la DIRECTION de
la discrimination (même identité < identité différente) est, elle, bien vérifiée et fiable. Conclusion
assumée : le seuil livré est un point de départ, pas une valeur calibrée — voir docs/face-auth.md.

Lancer : cd face && python3 -I -m unittest discover -s tests -t . -v"""
import os
os.environ.setdefault("FACE_TICKET_KEY", "test-key-not-a-real-secret")
os.environ.setdefault("JWT_SECRET", "test-key-not-a-real-secret")

import unittest

import cv2
import numpy as np

from app import recognizer


def synth_face(seed: int, n=1, noise=4.0):
    """Motif 200x200 reproductible, avec une texture HAUTE FRÉQUENCE propre à `seed` (reproductible pour
    un même seed, décorrélée d'un seed à l'autre — comme la texture de peau d'un visage réel), plus un peu
    de bruit pour simuler plusieurs photos de la « même personne ». Sert à exercer LBPH (qui compare des
    motifs de texture LOCAUX), pas la détection de visage (voir note de module : un dégradé + des formes
    pleines, trop lisses, ne suffit pas à discriminer sous LBPH — testé puis corrigé après un premier
    échec de ce fichier)."""
    identity = np.random.default_rng(seed).integers(0, 255, (200, 200)).astype(np.float64)
    identity = cv2.GaussianBlur(identity, (0, 0), sigmaX=1.2)   # cohérence spatiale locale (pas du bruit blanc pur)
    noise_rng = np.random.default_rng(seed * 7919 + 1)          # flux de bruit indépendant mais reproductible
    return [np.clip(identity + noise_rng.normal(0, noise, identity.shape), 0, 255).astype(np.uint8) for _ in range(n)]


class DecodeImage(unittest.TestCase):
    def test_decodes_a_valid_jpeg(self):
        arr = np.full((64, 64, 3), 127, dtype=np.uint8)
        ok, buf = cv2.imencode(".jpg", arr)
        self.assertTrue(ok)
        img = recognizer.decode_image(buf.tobytes())
        self.assertEqual(img.shape[:2], (64, 64))

    def test_rejects_garbage_bytes(self):
        with self.assertRaises(ValueError):
            recognizer.decode_image(b"ceci n'est pas une image")


class ExtractFace(unittest.TestCase):
    def test_blank_image_has_no_detectable_face(self):
        blank = np.full((300, 300, 3), 128, dtype=np.uint8)
        self.assertIsNone(recognizer.extract_face(blank))


class TrainAndVerify(unittest.TestCase):
    def test_matches_a_face_close_to_the_enrolled_pattern(self):
        enrolled = synth_face(seed=1, n=5, noise=4.0)
        model = recognizer.train_model(enrolled)
        probe = synth_face(seed=1, n=1, noise=4.0)[0]      # même « personne » (même graine), bruit différent
        ok, confidence = recognizer.verify_face(model, probe, confidence_max=70.0)
        self.assertTrue(ok, f"confiance={confidence}")

    def test_same_identity_scores_lower_than_a_different_one(self):
        """Propriété réellement garantie par ces fixtures synthétiques (contrairement à un seuil absolu,
        voir note de module) : une correspondance authentique obtient TOUJOURS une distance LBPH plus
        faible qu'une identité différente. Observé ici : avec confidence_max=70.0 (valeur par défaut
        livrée), une identité synthétique différente peut tout de même passer sous ce seuil (~30 dans un
        run type) — preuve empirique que ce seuil DOIT être recalibré sur de vraies photos avant mise en
        service (voir docs/face-auth.md, §IA) : ces motifs synthétiques, pauvres en texture réelle de
        peau/visage, sous-estiment la séparation qu'obtiendrait LBPH sur de vrais visages."""
        enrolled = synth_face(seed=3, n=5, noise=3.0)
        model = recognizer.train_model(enrolled)
        same, different = synth_face(seed=3, n=1, noise=3.0)[0], synth_face(seed=4, n=1, noise=3.0)[0]
        _, conf_same = recognizer.verify_face(model, same, confidence_max=0)
        _, conf_different = recognizer.verify_face(model, different, confidence_max=0)
        self.assertLess(conf_same, conf_different)


if __name__ == "__main__":
    unittest.main()
