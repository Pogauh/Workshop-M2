# Runbook — Échelles des actions de remédiation

Principe commun aux trois échelles : toujours essayer l'action la moins destructrice d'abord, et
VÉRIFIER avant de passer à la suivante (sonde de transaction réelle, pas seulement l'état du
conteneur). Si une action suffit à rétablir le service, les suivantes ne sont pas déclenchées.

## Surcharge d'un compte (déni de service applicatif)
1. **throttle** — réduction du débit de paiement autorisé par session (clé = jeton, pas l'IP : voir
   `perimetre.md` sur le NAT de Docker Desktop). 60 → 10 req/s. Réversible, n'affecte aucun
   utilisateur légitime qui respecte un rythme normal.
2. **suspend_user** — suspension des comptes identifiés comme source de la charge anormale (hors
   comptes protégés `probe` et `merchant`). Le compte ne peut plus obtenir de jeton valide.
3. **ban_ip** — bannissement au niveau du WAF des IP sources identifiées. **Désactivé par défaut**
   (`TRUST_SOURCE_IP=false`) car Docker Desktop peut masquer l'IP réelle de l'attaquant derrière une
   adresse de NAT interne ; bannir cette adresse bloquerait tout le monde. À activer seulement après
   vérification manuelle des journaux du WAF (`remote_addr`).
4. **restart_api** — dernier recours. Redémarrage du conteneur API depuis l'image saine, et seulement
   si une sonde fraîche échoue réellement à cet instant (pas de redémarrage réflexe). Limité à 2
   redémarrages par fenêtre de 10 minutes (anti-boucle).

## Brute-force sur la connexion
1. **contain_compromise** — seulement si des échecs en rafale sont suivis d'une connexion réussie sur
   le même compte (compromission probable, pas une simple tentative infructueuse) : révocation de
   toutes les sessions actives (comparaison `iat` du jeton / `revoked_after`), mot de passe à
   réinitialiser forcé, verrouillage prolongé (15 min).
2. **lock_account** — verrouillage temporaire (3 min) du compte ciblé. Le refus est renvoyé AVANT le
   calcul bcrypt : un compte verrouillé ne consomme plus de temps CPU, ce qui limite aussi l'effet
   d'un brute-force distribué sur plusieurs comptes à la fois.
3. **throttle_login** — limitation du débit de connexion par IP (seulement si `TRUST_SOURCE_IP=true`,
   pour la même raison de NAT que `ban_ip` ci-dessus).
4. **restart_auth** — dernier recours, redémarrage du service d'authentification.

## Panne de service
Chien de garde continu (hors anomalie ML) : si la sonde de transaction échoue plusieurs fois de suite
et qu'un service métier (`db`, `auth`, `api`) est signalé arrêté ou défaillant par l'actionneur, le
moteur le redémarre directement, sans attendre une qualification d'anomalie par le détecteur. Vérifie
le rétablissement comme pour les autres échelles.

## Régulation (anti-emballement), commune aux trois échelles
- Maximum 6 actions toutes catégories confondues par fenêtre de 10 minutes.
- Après 2 minutes de calme confirmé (plus d'anomalie détectée), le débit et les bannissements sont
  automatiquement ramenés à leurs valeurs par défaut : le système ne reste pas indéfiniment en mode
  défensif une fois la menace écartée.
