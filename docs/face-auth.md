# Authentification renforcée du back-office — consigne additionnelle 1

Caméra USB + reconnaissance faciale (IA légère) + badge lumineux ESP8266, intercalés entre l'identifiant
et le mot de passe sur la connexion du compte `manager` (back-office). Complète `docs/architecture.md`
(vue d'ensemble de la plateforme) et `docs/esp8266-wiring.md` (câblage détaillé du badge).

## Pourquoi un compte dédié (`manager`), et pas tous les comptes existants

La consigne demande de « renforcer l'authentification du back-office ». Les comptes de démonstration
existants (`alice`, `bob`, `carol`, `merchant`, `attacker`, `probe`) portent chacun un rôle précis et déjà
validé dans le sujet initial : `carol` doit rester brute-forçable par mot de passe seul (c'est tout
l'intérêt du scénario), `attacker` est utilisé par des scripts automatisés (`attacker/flood.py`),
`probe` est la sonde de santé interne du moteur de remédiation — aucun de ces trois ne peut raisonnablement
exiger une caméra sans casser une démonstration déjà construite et mesurée (MTTR, rappel ML...).

Plutôt que de complexifier ces comptes avec des exceptions, un compte **`manager`** (rôle `backoffice`)
porte intégralement la nouvelle exigence : c'est lui, et lui seul, qui a `face_required=true` en base
(`db/init.sh`, `auth/app/main.py:SEED`). Compte à solde nul (`0`, voir `db/init.sh`) : ne modifie pas
l'invariant comptable de 600 000 € déjà vérifié par `/api/health/deep`.

## Flux complet

```
1. Identifiant saisi (web/src/components/Login.jsx, étape "username")
        │
        ▼
2. Caméra activée dans le NAVIGATEUR (getUserMedia — PAS dans un conteneur : Docker Desktop sous
   Windows n'expose pas les périphériques USB aux conteneurs Linux, voir §Pourquoi le navigateur)
        │  POST /face/verify {username, image}
        ▼
3. Service « face » (OpenCV, voir §IA) :
     - Aucun visage enregistré pour ce compte -> amorçage, succès automatique (voir §Amorçage)
     - Visage reconnu   -> billet signé (ticket.py) + LED verte clignotante (green_blink)
     - Visage refusé    -> LED rouge fixe 30 s (red_solid_30) ; 1 nouvel essai, puis blocage 5 min
        │ (si reconnu)
        ▼
4. Mot de passe saisi -> POST /auth/login {username, password, face_ticket}
        │
        ▼
5. Service « auth » :
     - Billet absent/invalide/périmé pour un compte face_required -> refusé (401), LED rouge x10 (red_blink10)
     - Mot de passe incorrect                                      -> refusé (401), LED rouge x10, et toute
                                                                        la phase d'identification recommence
                                                                        (identifiant + caméra, pas juste le mot de passe)
     - Les deux valides -> jeton de session, LED verte fixe 30 s (green_solid_30) puis back-office disponible
```

## Pourquoi la capture caméra vit dans le navigateur, pas dans un conteneur

Docker Desktop sous Windows (backend WSL2, imposé par le sujet) **ne permet pas** le passage d'un
périphérique USB (webcam) à un conteneur Linux — contrairement à `--device /dev/video0` sur un hôte Linux
natif. Plutôt que de contourner cette limite (ce que le sujet interdit explicitement en matière de
réseau — « contourner une politique de sécurité n'est jamais une solution admise » — et que nous
appliquons par analogie ici), la capture se fait avec l'API standard du navigateur
(`navigator.mediaDevices.getUserMedia`, dans `web/src/components/FaceCapture.jsx`), qui a un accès natif
à la caméra du PC Hôte. Seule l'image déjà capturée (JPEG) est envoyée par HTTP au service `face` : celui-ci
n'a besoin d'aucun accès matériel, seulement de traiter des octets — cohérent avec le reste de
l'architecture (conteneurs sans privilèges, `read_only: true`, voir `docker-compose.yml`).

## IA de reconnaissance faciale (« légère », voir consigne)

OpenCV (`opencv-contrib-python-headless`) : cascade de Haar pour la **détection** du visage dans l'image,
LBPH (Local Binary Patterns Histograms) pour la **reconnaissance** — CPU uniquement, aucun modèle à
télécharger, entraînement par compte en quelques millisecondes. Détail méthodologique et limites :
`face/app/recognizer.py` (docstring) et `face/tests/test_recognizer.py` (résultats empiriques, y compris
l'échec initial d'un seuil non calibré — conservé volontairement dans l'historique des tests comme preuve
de démarche). **Le seuil livré (`DEFAULT_CONFIDENCE_MAX=70.0`) n'est PAS calibré sur de vrais visages** :
aucune photo réelle n'était disponible pour ce développement. Avant la démonstration, enregistrez
plusieurs photos réelles de l'opérateur (back-office, §Gestion des habilitations) et ajustez au besoin
cette constante selon le taux de faux rejets/acceptations observé.

## Amorçage (bootstrap) : premier accès sans visage encore enregistré

Au tout premier démarrage, aucun visage n'est enregistré pour `manager` — un blocage total serait
impossible à lever. `POST /face/verify` détecte l'absence d'inscription (`store.has_enrollment()`) et
répond `recognized:true, bootstrap:true` sans aucune comparaison, avec un billet valide : la connexion se
termine au mot de passe seul, avec un message explicite dans l'interface. L'opérateur peut ensuite
enregistrer son visage depuis le back-office (§Gestion des habilitations) pour que les connexions
suivantes exigent une vraie reconnaissance.

## Gestion des habilitations (back-office)

Une fois connecté, `manager` voit une console dédiée (`web/src/components/BackOffice.jsx`, remplace le
tableau de bord de paiement pour ce rôle) :
- **Inscrire un visage** : saisie d'un identifiant de compte, capture de 5 photos via la caméra (variation
  d'angle recommandée), entraînement du modèle LBPH, stockage isolé (`face/app/store.py`, volume
  `facedata`, **aucun lien avec la base de paiements**).
- **Lister / révoquer** : tous les comptes avec un visage enregistré, avec révocation en un clic (confirmation
  en deux temps, pas de `window.confirm` — indisponible dans certains contextes de rendu).

Autorisation : `face/app/main.py` exige un jeton de session valide (même secret `JWT_SECRET` que
`api`/`auth`) — un compte peut gérer son propre visage, et tout compte de rôle `backoffice` peut gérer
celui de n'importe quel autre compte (`_require_self_or_backoffice`).

## Sécurité : le billet signé (`face_ticket`)

`face` émet, `auth` vérifie — **aucun appel réseau entre les deux services** : même secret partagé
(`FACE_TICKET_KEY`), HMAC-SHA256, même principe que la signature des évènements détecteur -> remédiateur
déjà en place (`detector/app/main.py`). Le billet est lié au nom d'utilisateur, expire après 120 secondes
(le temps de taper un mot de passe, pas de le rejouer plus tard), et sa signature est vérifiée en temps
constant (`hmac.compare_digest`). Un compte sans `face_required` (tous sauf `manager`) ignore
entièrement ce mécanisme : **aucun changement de comportement** pour les scénarios déjà validés
(brute-force sur `carol`, surcharge via `attacker`, sondes `probe`, tous les scripts `tests/e2e_*.py` et
`scripts/bootstrap_model.sh`).

## Cloisonnement (cohérent avec le reste de l'architecture)

`face` ne touche ni la base de paiements, ni l'actuator, ni les secrets des autres services — ses seules
données (modèles LBPH) vivent sur son propre volume (`facedata`). Réseaux (voir `docker-compose.yml`) :
`internal` (joignable par le WAF, comme `api`/`auth`/`web`) + `edge` (seul moyen d'atteindre le badge
ESP8266 sur le réseau du hotspot, en dehors des réseaux Docker internes — même raison que `ollama-pull`
pour les modèles IA). `auth` rejoint aussi `edge` pour le même motif (LED du badge pilotée aux deux
étapes, reconnaissance ET mot de passe).

## Badge ESP8266 : indicateur, pas verrou de sécurité

Les deux services (`face`, `auth`) envoient leurs ordres LED en **best-effort**
(`esp_led.py` dans chacun) : un badge éteint, pas encore flashé ou hors de portée WiFi est journalisé
mais **ne bloque jamais l'authentification**. La LED est un retour visuel pour la démonstration, la
sécurité réelle repose sur le billet signé et le mot de passe — jamais sur l'état d'un périphérique
physique optionnel. Détail du firmware et séquencement exact des couleurs : `esp8266/README.md`.

## Limites assumées
- Seuil de reconnaissance non calibré sur de vrais visages (voir §IA) — à ajuster avant la démonstration.
- Verrouillage de la phase faciale (`face/app/lockout.py`) en mémoire : un redémarrage du service lève
  les blocages en cours. Acceptable pour un prototype de workshop, à journaliser en base pour un usage
  réel.
- Un seul visage par compte (pas de gestion multi-visages/éclairages pour une même personne) : plusieurs
  photos à l'inscription améliorent la robustesse (5 angles), mais restent un seul modèle entraîné.
- Pas de détection de usurpation (photo imprimée, vidéo rejouée) : hors périmètre d'un prototype de
  4 jours, à mentionner explicitement devant le jury comme limite connue (liveness detection écartée).
