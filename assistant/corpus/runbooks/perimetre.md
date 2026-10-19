# Runbook — Périmètre de l'assistant (ce qu'il peut et ne peut pas faire)

Cet assistant répond à des questions. Il n'a AUCUN moyen technique d'agir sur le système :
- Pas de jeton d'`actuator`, pas de client vers l'`actuator`.
- Pas de jeton `INTERNAL_TOKEN` (suspension, verrouillage ou réinitialisation de comptes).
- Le seul appel réseau sortant qu'il effectue vers le reste du système est un GET en lecture seule
  vers `/state` du moteur de remédiation, pour contextualiser ses réponses avec l'état réel. Son
  réseau Docker (`assist`) n'a d'ailleurs aucune route vers l'actionneur ni vers la base de données.

Si un opérateur demande « redémarre l'API » ou « bannis cette IP », l'assistant doit refuser d'agir,
expliquer que seule la chaîne automatique (ou un accès direct à l'`actuator`, hors de l'assistant)
peut le faire, et au besoin renvoyer vers `echelle-actions.md`.

Cette séparation stricte (recherche documentaire d'un côté, action sur le système de l'autre) est ce
qui permet de montrer au jury un assistant utile sans qu'il ne devienne un second chemin, non
contrôlé, vers les mêmes privilèges que l'actionneur.

## Note sur le réglage NAT du laboratoire
Sous Docker Desktop, le trafic venant du PC Attaquant traverse un NAT avant d'atteindre le conteneur
WAF : l'adresse IP source vue par nginx n'est donc pas toujours fiable. C'est pourquoi la limitation
de débit de paiement est indexée sur le jeton de session (`$rl_key`, voir `waf/nginx.conf`) plutôt que
sur l'IP, et pourquoi les actions par IP (`ban_ip`, `throttle_login`) restent désactivées par défaut
(`TRUST_SOURCE_IP=false`) tant qu'une vérification manuelle des journaux du WAF n'a pas confirmé que
l'adresse source observée correspond bien au poste attaquant.
