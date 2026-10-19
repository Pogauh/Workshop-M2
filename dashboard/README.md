# Console de supervision (signes vitaux)

Lecture seule de l'état du moteur de remédiation (`GET /state`, interrogé chaque seconde), pour le jury : état du système,
graphique en 3 pistes (débit, latence de la transaction témoin, score d'anomalie) avec les phases avant/pendant/après,
incident en cours avec ses actions numérotées, alertes SIEM, état des services, défenses actives, mémoire des derniers
incidents. Aucune action n'est disponible ici : seul l'actionneur peut agir, et uniquement depuis le moteur.

Développement : `npm install && npm run dev` (publier le port du moteur : voir `docker-compose.yml`, service `remediator`).
Tests de la logique de présentation : `npm test`.
