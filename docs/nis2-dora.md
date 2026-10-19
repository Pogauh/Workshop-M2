# NIS2 / DORA — ce que le prototype démontre, ce qu'il ne démontre pas

Ce document relie les exigences générales de ces deux réglementations européennes aux éléments
concrets du démonstrateur, pour la partie « transformation » du dossier. Il ne constitue pas une
analyse de conformité juridique — un prototype de workshop sur quelques jours ne peut pas en tenir
lieu — mais une mise en correspondance pédagogique.

## NIS2 (directive sur la cybersécurité des réseaux et systèmes d'information)

| Exigence générale NIS2 | Démontré par le prototype |
|---|---|
| Gestion des risques (analyse, mesures proportionnées) | `docs/ebios-rm.md` (5 ateliers) |
| Gestion des incidents (détection, traitement, retour d'expérience) | Détecteur ML + règles SIEM, moteur de remédiation, journal `incidents.jsonl`, dashboard |
| Continuité d'activité et gestion de crise | `docs/pca-pra.md`, sauvegarde/restauration (`ansible/backup.yml`, `restore_db.yml`), chaos engineering (`ansible/chaos.yml`) |
| Sécurité de la chaîne d'approvisionnement | Hors périmètre d'un prototype sans fournisseurs réels |
| Politiques de contrôle d'accès et gestion des actifs | Rôles SQL au moindre privilège, jetons à durée de vie courte, secrets jamais commités (`.env` local) |
| Chiffrement | TLS hors périmètre du laboratoire (réseau pédagogique isolé) ; secrets en clair mais jamais commités ni transmis, limite assumée (voir `docs/secrets.md`) |
| Notification des incidents aux autorités dans les délais légaux | **Non démontrable** par un prototype : aucune autorité réelle, aucun délai réglementaire à respecter ici |

## DORA (règlement sur la résilience opérationnelle numérique, secteur financier)

| Exigence générale DORA | Démontré par le prototype |
|---|---|
| Cadre de gestion du risque lié aux TIC | `docs/ebios-rm.md`, architecture en profondeur (`docs/architecture.md`) |
| Gestion, classification et notification des incidents liés aux TIC | Journal d'incidents horodaté, alertes SIEM classées par sévérité, dashboard |
| Tests de résilience opérationnelle numérique | `ansible/chaos.yml` (panne franche), scénarios d'attaque répétables (`scripts/repeat_demo.sh`), `tests/e2e_demo.py` |
| Gestion du risque lié aux prestataires tiers de TIC | Hors périmètre (pas de prestataire réel) |
| Partage d'informations sur les menaces | Hors périmètre d'un prototype isolé |
| Gouvernance formelle (comité des risques, responsabilités à l'échelle de l'organisation) | **Non démontrable** par un prototype : pas d'organisation réelle derrière le projet |

## Limite générale assumée
Un système qui se répare seul en quelques dizaines de secondes dans un laboratoire isolé illustre des
capacités techniques (détection, réponse automatisée, preuve de reprise, traçabilité) qui sont des
briques nécessaires à la conformité NIS2/DORA, mais la conformité elle-même suppose en plus une
gouvernance, des processus organisationnels et des obligations contractuelles qui dépassent le cadre
d'un atelier de quelques jours.
