# Plan proposé pour Dossier.pdf (8–12 pages)

1. **Contexte et objectifs** (½ page) — PayAlpha, l'analogie du système immunitaire, le périmètre
   retenu (5 domaines du sujet).
2. **Architecture** (1–1½ page) — schéma des composants et réseaux (`docs/architecture.md`),
   correspondance biologie/technique.
3. **Scénarios d'attaque et remédiation** (2 pages) — les trois scénarios (surcharge, brute-force,
   panne), les échelles d'actions, la preuve de reprise par transaction réelle et invariant comptable.
   Illustrer avec les graphiques « signes vitaux » du dashboard (captures d'écran).
4. **Détection (IA/Data)** (1–1½ page) — caractéristiques utilisées, choix IsolationForest + seuil,
   évaluation réelle (`detector/model/report.json` : taux de faux positifs, rappel par attaque, délai
   de détection). Chiffres réels obligatoires — voir `docs/tests-chaos.md` et `docs/ml.md` (méthode,
   balayage des volumes d'entraînement, limites).
5. **Sécurité et cyber** (1 page) — WAF, SIEM (règles R1–R5), gestion des secrets (`.env` local,
   jamais commité), EBIOS RM (synthèse, renvoi vers `docs/ebios-rm.md`).
6. **Continuité et transformation** (1 page) — PCA/PRA, RTO/RPO mesurés, NIS2/DORA
   (`docs/nis2-dora.md`).
7. **Mesures et résultats** (1–1½ page) — tableaux remplis de `docs/tests-chaos.md` : MTTR par
   scénario, nombre d'essais, taux de détection.
8. **Limites et pistes d'amélioration** (½ page) — risques résiduels assumés (`docs/ebios-rm.md`,
   `docs/pca-pra.md`), ce qui serait fait avec plus de temps.
9. **Répartition du travail** (½ page, si demandé par le barème).

## Ce qui ne peut pas être produit sans la plateforme réellement démarrée
Les chiffres des sections 4 et 7 (taux de détection, MTTR, nombre d'essais) ne sont pas inventés ici :
ce document ne fournit que le squelette et les tableaux vides. Faites tourner
`scripts/bootstrap_model.sh` et le protocole de `docs/tests-chaos.md` sur le PC Hôte pour obtenir les
chiffres réels à reporter.
