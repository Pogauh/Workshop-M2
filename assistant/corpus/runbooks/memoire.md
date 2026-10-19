# Runbook — La memoire de l'assistant (ce qu'elle est, ce qu'elle n'est pas)

L'assistant s'appuie sur un corpus documentaire fixe (ce dossier + `docs/`), indexe une fois au
demarrage (ou via `POST /reindex` apres une modification des fichiers). Ce n'est pas un
re-entrainement automatique sur les incidents reels : le modele de langage et le modele de detection
d'anomalies restent figes pendant la demonstration, et ne s'ajustent jamais automatiquement a partir
d'evenements non verifies survenus en direct.

Apres un incident, le `remediator` ecrit un rapport dans `incidents.jsonl` (memoire immunitaire au
sens biologique : trace de ce qui s'est passe). C'est un journal, pas un jeu d'entrainement. Si
l'equipe souhaite enrichir les runbooks avec les enseignements d'un incident, elle le fait
manuellement : elle relit `incidents.jsonl`, redige une note dans `assistant/corpus/runbooks/`, et
relance `POST /reindex`. Ce choix garde un humain dans la boucle d'apprentissage.
