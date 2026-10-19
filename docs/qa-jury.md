# Questions probables du jury — réponses préparées

**« Comment savez-vous que le service est vraiment rétabli, pas juste que le conteneur tourne ? »**
La sonde du moteur de remédiation exécute une vraie transaction (connexion, paiement, relecture) et
vérifie l'invariant comptable (`/api/health/deep`, somme des soldes = 600 000). Un conteneur
« running » seul ne suffit jamais — voir `assistant/corpus/runbooks/invariant-comptable.md`.

**« Pourquoi ne bannissez-vous pas l'IP de l'attaquant directement ? »**
Sous Docker Desktop, le trafic traverse un NAT : l'IP vue par le WAF n'est pas fiable. Bannir à
l'aveugle risquerait de bloquer tout le monde. Le débit est donc limité par jeton de session, et le
bannissement IP reste désactivé par défaut (`TRUST_SOURCE_IP=false`), activable après vérification
manuelle — voir `docs/architecture.md`.

**« Que se passe-t-il si le modèle se trompe (faux positif) sur un pic de trafic légitime ? »**
L'anti-rebond exige 3 fenêtres anormales consécutives avant de qualifier un incident. Si une action
est tout de même déclenchée à tort, elle reste la moins invasive possible (limitation de débit avant
suspension), et un relâchement automatique intervient après 2 minutes de calme confirmé.

**« L'IA peut-elle agir sur le système, ou seulement le décrire ? »**
Deux IA séparées, deux rôles : le détecteur (ML) alimente le moteur de remédiation en évènements, mais
ne décide ni n'agit lui-même ; l'assistant conversationnel (RAG) est strictement en lecture seule, sans
jeton d'action, isolé sur son propre réseau Docker (`assist`) sans route vers l'actionneur ni vers la
base — voir `assistant/corpus/runbooks/perimetre.md`.

**« Comment le modèle a-t-il été entraîné et évalué ? »**
Entraînement non supervisé (IsolationForest) sur du trafic normal réel généré par
`traffic/normal_traffic.py`, évalué sur de vraies données d'attaque (flood, brute-force) collectées
avec le même protocole. Chiffres réels dans `detector/model/report.json`.

**« Que se passe-t-il en cas de compromission réelle d'un compte (pas juste une tentative) ? »**
Le système distingue l'échec répété (verrouillage temporaire) d'une connexion réussie après une série
d'échecs (compromission probable) : dans ce second cas, toutes les sessions du compte sont révoquées,
un changement de mot de passe est forcé, et le compte reste verrouillé plus longtemps — règle SIEM R3.

**« Que couvre réellement le PCA/PRA, et que ne couvre-t-il pas ? »**
Voir `docs/pca-pra.md` : couvert par la reprise automatique (surcharge, brute-force, panne de
service) ; couvert par une procédure manuelle documentée (sauvegarde/restauration de base) ; non
couvert (haute disponibilité multi-site, réplication en continu).

**« Pourquoi un `.env` local plutôt que SOPS/Vault ? »**
Par souci de fiabilité du démarrage pendant le temps contraint du workshop : un fichier généré
localement et jamais commité (`.gitignore` + `scripts/check_secrets.sh` avant toute livraison) est
plus simple à faire fonctionner à coup sûr sur la machine de démonstration qu'un chiffrement au
repos. Le compromis est assumé et documenté (`docs/secrets.md`, risque résiduel dans
`docs/ebios-rm.md`) : une vraie gestion de secrets serait la suite logique hors contrainte de temps.
