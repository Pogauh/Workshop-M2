# EBIOS Risk Manager (synthèse — à détailler dans le Dossier.pdf)

## Atelier 1 — Cadrage et socle de sécurité
**Valeurs métier** : disponibilité du service de paiement, intégrité des soldes et des transactions,
disponibilité et intégrité de l'authentification.
**Événements redoutés** : paiement indisponible (perte de confiance), solde incohérent (perte
financière, trahit la confidentialité/intégrité des données), compte compromis par brute-force
(fraude, usurpation).
**Socle de sécurité retenu** : WAF en frontal unique, authentification par jeton à durée de vie
courte, moindre privilège par service (rôles SQL distincts, droits au niveau colonne), secrets
jamais commités (`.env` local, voir `docs/secrets.md`), observabilité complète (métriques, journaux
structurés, alertes SIEM), moteur de remédiation à liste blanche d'actions et preuve de reprise par
transaction réelle.

## Atelier 2 — Sources de risque
| Source de risque | Objectif visé | Pertinence pour le démonstrateur |
|---|---|---|
| Cybercriminel opportuniste | Indisponibilité, extorsion | Retenue (scénario de surcharge applicative) |
| Script kiddie / outil automatisé | Scan, injection, brute-force de mots de passe faibles | Retenue (scénarios injection bloquée et brute-force) |
| Initié malveillant | Fraude interne | Hors périmètre (pas de couche IAM avancée dans un prototype de workshop) |
| État / APT | Espionnage, sabotage ciblé | Hors périmètre (disproportionné pour le contexte fictif) |

## Atelier 3 — Scénarios stratégiques
Chemin d'attaque retenu : réseau pédagogique du hotspot → PC Attaquant → WAF → API de paiement /
service d'authentification. Parties prenantes : WAF (barrière), API et authentification (cibles),
détecteur (vigie), moteur de remédiation (réponse).

## Atelier 4 — Scénarios opérationnels
1. **Surcharge applicative (DoS)** : un compte valide envoie un flot de paiements à `/api/payments`,
   saturant le débit autorisé puis le pool de connexions à la base. Vraisemblance : forte (outil
   simple, un seul poste). Gravité : forte (fonction cœur de métier).
2. **Brute-force sur la connexion** : essais répétés de mots de passe sur un compte faible
   (`carol`), jusqu'à verrouillage ou, si le mot de passe est deviné, compromission du compte.
   Vraisemblance : forte (mot de passe volontairement faible pour la démonstration). Gravité : forte
   si elle réussissait sans réponse (fraude sur le compte compromis) — d'où la distinction entre
   simple contention de la disponibilité et confinement d'une compromission probable (révocation des
   sessions, réinitialisation forcée).
3. **Injection applicative** (bonus) : charges utiles SQLi/XSS/traversal sur les paramètres de
   requête — doit être arrêtée au WAF, jamais atteindre l'API. Vraisemblance : moyenne. Gravité :
   forte si elle passait (intégrité des données).

## Atelier 5 — Traitement du risque
| Risque | Mesure | Statut démontrable en atelier |
|---|---|---|
| Surcharge applicative | Limitation de débit par jeton + détection ML + suspension/bannissement/redémarrage automatiques | Oui — démonstration en direct |
| Brute-force / compromission de compte | Verrouillage avant calcul du mot de passe, règles SIEM R2/R3, révocation de session + réinitialisation forcée | Oui — démonstration en direct |
| Injection | Signatures WAF (SQLi, XSS, traversal, injection de commande), validation stricte des entrées (schémas) | Oui — scénario bonus |
| Exfiltration de données | Rôles SQL en lecture minimale (l'API ne lit jamais `pw_hash`) | Partiel (mesure en place, non démontrée par un vol réel) |
| Sur-réaction du système (faux positifs bloquant des paiements légitimes) | Anti-rebond (3 fenêtres consécutives), échelle graduée, anti-boucle, relâchement automatique | Oui — à illustrer explicitement pendant la démonstration |

**Risques résiduels assumés** : pas de haute disponibilité multi-nœuds, pas de WAF industriel complet
(signatures maison plutôt que ModSecurity/CRS), modèle ML entraîné sur un volume de données limité au
temps du workshop, bannissement par IP non activé par défaut (fiabilité de la source sous NAT Docker
Desktop — voir `docs/architecture.md`), secrets en `.env` local non chiffré au repos (choix de
fiabilité de démarrage pendant le workshop plutôt qu'un chiffrement SOPS/age — voir
`docs/secrets.md` ; le fichier ne quitte jamais la machine de démonstration).
