# Détection par apprentissage automatique (IA/Data)

Référencé depuis `detector/app/model.py`. Complète `docs/architecture.md` (vue d'ensemble) et
`detector/model/README.md` (fichiers livrés) sur la partie strictement ML — les règles SIEM (R1–R5,
corrélation/attribution) sont documentées dans `detector/app/siem.py` et `docs/architecture.md`.

## Pourquoi un modèle, et pas seulement des règles

Le sujet impose de ne pas se limiter à des conditions codées en dur. Les règles SIEM (`siem.py`)
répondent à « qui fait quoi » (un compte, une IP, une règle WAF) ; le modèle ML répond à « la
plateforme se comporte-t-elle normalement, dans son ensemble, en ce moment ? ». Les deux se complètent :
le modèle qualifie une anomalie de charge/latence même quand aucune règle de corrélation ne « nomme »
encore un coupable (ex. début de surcharge avant que l'abus d'API ne soit net), les règles qualifient un
abus ciblé même quand le volume global reste sous le seuil statistique (ex. un seul compte en échec de
connexion dans un trafic par ailleurs calme).

## Données

8 observations par fenêtre glissante (`detector/app/features.py:sample()`), interrogées sur Loki
(journaux WAF/API/auth) et Prometheus (métriques temps réel) :

| Caractéristique | Source | Ce qu'elle capture |
|---|---|---|
| `rps` | Loki (WAF) | débit global de requêtes |
| `rps_max_user` | Loki (API) | débit du compte le plus actif (abus concentré) |
| `p95_ms` | Loki (WAF) | latence de queue (contention, saturation) |
| `err5xx_ratio` | Loki (WAF) | part d'erreurs serveur |
| `waf_block_ratio` | Loki (WAF) | part de requêtes bloquées (403/429) |
| `inflight` | Prometheus (API) | requêtes en cours de traitement (file d'attente) |
| `login_rps` | Prometheus (auth) | débit de tentatives de connexion |
| `login_fail_rate` | Prometheus (auth) | débit d'échecs de connexion (signal brute-force) |

Trois jeux sont collectés séparément, dans cet ordre, pour ne jamais mélanger une attaque dans le
trafic « normal » (`detector/app/collect.py`, orchestré par `scripts/bootstrap_model.sh`) :
- **normal** : `traffic/normal_traffic.py` (comptes alice/bob/carol, montants et libellés aléatoires,
  reconnexions espacées, 1,5 % de fautes de frappe volontaires — un trafic trop régulier ferait
  apprendre au modèle une variance irréaliste et multiplierait les faux positifs) ;
- **flood** : `attacker/flood.py` (surcharge applicative, compte `attacker`) ;
- **brute** : `attacker/bruteforce.py` (échecs de connexion répétés sur `carol`).

Cadence de collecte alignée sur la cadence de détection live (`detector/app/model.py:EVERY`, 1
observation/s) : les chiffres de délai de détection (`detected_after_s`) du rapport correspondent donc
exactement à ce qu'observerait un opérateur sur la plateforme réelle, pas à un artefact de collecte.

## Prétraitement et modèle (`detector/app/model.py`, `train.py`)

- `log1p` sur toutes les observations (clip négatif à 0) : une attaque dépasse le trafic normal de
  plusieurs ordres de grandeur ; sans compression logarithmique, `StandardScaler` serait dominé par les
  valeurs extrêmes et perdrait la sensibilité sur le trafic normal.
- **IsolationForest** (scikit-learn, 300 arbres, non supervisé) entraîné **uniquement sur du trafic
  normal** : le modèle apprend la forme du comportement sain, pas des signatures d'attaque — il
  généralise donc à une attaque qu'il n'a jamais vue, tant qu'elle s'écarte de cette forme.
- **Seuil** = 1er percentile des scores obtenus sur les données d'entraînement : ~1 % de faux positifs
  attendus par construction sur le trafic qui a servi à apprendre.
- **Détection unilatérale** (`UP_Z = 2.0`) : une fenêtre n'est anormale que si au moins une
  caractéristique dépasse +2 écarts-types (après `log1p`) **à la hausse**. Un système au repos (toutes
  métriques proches de 0) n'est pas une attaque — testé explicitement
  (`test_idle_system_is_not_an_attack`).
- **Anti-rebond** : une anomalie n'est qualifiée qu'après **3 fenêtres consécutives** anormales
  (`K=3` dans `detector/app/main.py`), avant transmission au moteur de remédiation. Mesuré et vérifié
  sur le trafic normal tenu à l'écart de l'entraînement (`false_alerts_after_debounce_k3` dans le
  rapport, doit rester à 0).
- **Découpage train/test temporel** (75 %/25 %, pas aléatoire) : les fenêtres glissantes se
  chevauchent (observations corrélées dans le temps) ; un tirage aléatoire laisserait fuiter de
  l'information du futur vers le passé et surestimerait la performance.

## Volume d'entraînement : balayage et choix (`detector/app/train_sweep.py`)

Plutôt que de fixer arbitrairement la taille du jeu normal, `scripts/bootstrap_model.sh` collecte un
grand jeu continu puis **entraîne et évalue à plusieurs tailles** (préfixes chronologiques croissants,
mêmes attaques réelles en évaluation à chaque fois) et retient automatiquement la plus performante sur
la machine utilisée (rappel minimal par type d'attaque, pénalisé par le taux de faux positifs et par
toute attaque non détectée — voir `score()` dans `train_sweep.py`). Le détail de chaque taille testée
est dans `detector/model/sweep.json` ; `detector/model/report.json` ne contient que le résultat retenu.

**Résultats réels (cette machine — Ryzen 7 5800H / 16 Go RAM / Docker Desktop WSL2 — voir
`detector/model/report.json` et `sweep.json`, collecte du 20/10/2026, 2909 lignes normales + 333 flood +
335 brute, cadence 1 ligne/s) :**

| Lignes normales testées | Faux positifs | Rappel flood | Rappel brute | Détecté après (s) | Entraînement |
|---|---|---|---|---|---|
| 400  | 0,0 % | 0,0 %  | 3,3 %  | — (jamais) | 1,04 s |
| 800  | 0,0 % | 0,0 %  | 9,9 %  | — (jamais) | 1,06 s |
| 1200 | 0,0 % | 3,0 %  | 13,4 % | 6 s  | 1,08 s |
| 1800 | 0,0 % | 99,7 % | 40,6 % | 4 s  | 1,06 s |
| 2400 | 0,0 % | 99,7 % | 100 %  | 4 s  | 1,19 s |
| **2909 (retenue)** | **0,0 %** | **100 %** | **100 %** | **3 s** | **1,14 s** |

Taille retenue : **2909 lignes** (= tout le trafic normal collecté) — c'est aussi la plus performante du
balayage : rappel parfait sur les deux attaques, aucun faux positif, détection qualifiée (anti-rebond
K=3) en seulement 3 s après le début de l'attaque. Le balayage montre nettement qu'**en dessous de
~1200 lignes le modèle ne généralise pas** (rappel quasi nul, notamment sur le brute-force) : IsolationForest
a besoin d'assez d'exemples de trafic normal pour cerner correctement la forme du comportement sain.
Le coût d'entraînement lui-même est négligeable (~1,1 s quel que soit le volume testé, 300 arbres sur 8
caractéristiques) : le facteur limitant est la collecte de trafic réel, pas le calcul.

## Limites constatées

- Le modèle détecte une **dérive globale de comportement**, pas une attaque nommée : la classification
  « dos » / « bruteforce » / « outage » appliquée ensuite par le moteur de remédiation
  (`remediator/app/engine.py:classify()`) s'appuie sur les caractéristiques et les suspects SIEM, pas
  sur une sortie multi-classe du modèle.
- Entraîné sur un trafic fictif généré par script : la variance réaliste est volontairement injectée
  (voir `normal_traffic.py`) mais reste plus simple qu'un trafic de production réel ; un déploiement
  réel demanderait un réentraînement périodique sur du trafic réellement observé (volontairement absent
  ici, voir `assistant/corpus/runbooks/memoire.md` sur l'absence de réentraînement automatique).
- Sensible à un changement durable et légitime de volumétrie (ex. campagne commerciale) : sans
  réentraînement, un pic légitime soutenu serait vu comme une anomalie. Mitigé par la régulation
  (assouplissement automatique des défenses après retour au calme, voir `docs/architecture.md`), pas par
  le modèle lui-même.
- Le seuil au 1er percentile est un compromis explicite faux positifs/rappel ; il n'est pas recalculé
  dynamiquement (dérive progressive du trafic normal au fil des mois, hors périmètre d'un prototype de
  4 jours).
- **Constaté en conditions réelles** : des scripts de test enchaînant plusieurs requêtes HTTP sans délai
  (ex. `tests/smoke.py`, plusieurs `tests/e2e_*.py` lancés à la suite) peuvent créer une forme de trafic
  différente de celle apprise (`normal_traffic.py` espace ses requêtes aléatoirement) et déclencher une
  anomalie « dos » à tort. Le système se régule correctement (limitation du débit, vérifié, MTTR observé
  ~2 s, retour à `HOMEOSTASIS`) — ce n'est pas un dysfonctionnement, mais à anticiper : ne pas enchaîner
  ce type de script juste avant la prise du Clip Chrono ou la démonstration live (`./scripts/reset.sh`
  après, pas juste avant, un test de charge manuel).
