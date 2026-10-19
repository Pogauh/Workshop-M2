# PCA / PRA — synthèse

## Périmètre couvert par le démonstrateur
- Service de paiement (API + base) et authentification.
- Scénarios couverts par la reprise automatique : surcharge applicative, brute-force sur la
  connexion, panne franche d'un service (chien de garde).
- Scénario couvert par une procédure manuelle (non automatisée) : perte ou corruption de la base de
  données — voir sauvegarde/restauration ci-dessous.

## Objectifs mesurés (RTO / RPO)
À compléter avec les chiffres réellement observés lors des essais (section mesures du Dossier.pdf) :
- **RTO observé** = MTTR affiché par le dashboard (`mttr_s`) et par `remediator_last_mttr_seconds`
  (Prometheus), sur plusieurs essais répétés avec `scripts/repeat_demo.sh`.
- **RPO applicatif** = 0 (aucune perte de transaction en cas de redémarrage : écritures
  transactionnelles, clé d'idempotence côté client, invariant comptable vérifié à `/api/health/deep`
  après chaque reprise).
- **RPO en cas de perte de la base** = âge de la dernière sauvegarde `ansible/backup.yml` (à planifier
  en tâche périodique hors workshop ; exécutée manuellement ici).

## Sauvegarde et restauration de la base
- `ansible-playbook ansible/backup.yml` : `pg_dump` au format personnalisé dans `backups/` (hors
  dépôt versionné), conserve les 10 sauvegardes les plus récentes.
- `ansible-playbook ansible/restore_db.yml -e backup_file=backups/payments-XXXX.dump` : arrête les
  services qui écrivent dans la base, réinitialise le schéma, restaure, relance les services.
- `ansible-playbook ansible/chaos.yml` : tue brutalement un service (`api`, `auth` ou `db` au hasard,
  ou `-e chaos_service=db`) pour vérifier que la reprise reste automatique (chien de garde du moteur
  de remédiation) — utilisé pour mesurer le RTO en conditions de panne franche, indépendamment d'une
  attaque applicative.

## Responsabilités pendant un incident
| Rôle | Responsabilité |
|---|---|
| Moteur de remédiation | Détection → décision → action → vérification, sans intervention humaine |
| Opérateur (observateur) | Supervise via le dashboard, n'intervient qu'en cas d'`ESCALATION` |
| Assistant IA local | Aide à la compréhension de l'incident (lecture seule, aucune action) |

## Choix de restauration
Trois échelles graduées selon le type d'attaque (surcharge, brute-force, panne) — détail dans
`assistant/corpus/runbooks/echelle-actions.md`. Le redémarrage d'un service n'est tenté qu'en dernier
recours, et seulement si une sonde fraîche échoue réellement à cet instant ; sa preuve de succès est
une transaction réelle vérifiée (création, relecture, invariant comptable), jamais seulement l'état
« running » du conteneur.

## Risques qui subsistent après la reprise
- Un attaquant distribué sur de nombreuses adresses contournerait un bannissement IP unitaire ; mesure
  recommandée en contexte industriel : CDN ou protection anti-DDoS en amont.
- Le modèle ML peut générer des faux positifs sur un pic de trafic légitime ; la régulation
  (relâchement automatique après retour au calme, anti-rebond à 3 fenêtres consécutives) limite
  l'impact sans l'annuler complètement.
- La restauration de base (`restore_db.yml`) n'automatise pas la détection de corruption : elle
  suppose qu'un opérateur a identifié le besoin de restaurer et choisi la sauvegarde à utiliser.

## NIS2 / DORA — voir `docs/nis2-dora.md` pour le détail de ce que le prototype démontre et ne
démontre pas vis-à-vis de ces deux réglementations.
