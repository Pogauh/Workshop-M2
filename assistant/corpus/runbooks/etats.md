# Runbook — Comprendre les états du système

Le moteur de remédiation (`remediator`) fait vivre le système dans l'un de ces états. Le dashboard et
cet assistant les lisent en direct sur `/state`.

## HOMEOSTASIS
État normal. Les paiements fonctionnent, le score ML est stable, aucune action défensive active.
C'est l'état de départ et l'état cible après toute reprise.

## SURVEILLANCE
Le détecteur a vu une fenêtre suspecte (score anormal isolé). Aucune action n'est encore prise : il
faut 3 fenêtres anormales consécutives pour qualifier un incident. Cette règle d'anti-rebond évite de
réagir au moindre pic de trafic légitime et d'interrompre des paiements qui n'ont rien d'anormal.

## IMMUNITY
Incident qualifié (3 scores anormaux d'affilée, ou règle SIEM déclenchée). Le moteur choisit l'action
la moins invasive disponible dans l'échelle correspondant au type d'attaque identifié (surcharge,
brute-force ou panne). Voir `echelle-actions.md`.

## REGENERATION
Une action vient d'être appliquée. Le système sonde une transaction réelle (paiement, relecture,
vérification de l'invariant comptable) toutes les secondes, pendant jusqu'à 25 ou 40 secondes selon
l'action, avant de conclure.

## RESTORED
Au moins 3 sondes de transaction réussies d'affilée, latence correcte. Le service est réputé rétabli.
L'état reste RESTORED un court palier (HOLD, 30 s) avant de redescendre en HOMEOSTASIS (ou CONTAINED
si la source de l'incident persiste sans plus toucher le service), pour éviter les oscillations
d'état à l'affichage.

## CONTAINED
La menace détectée persiste (par exemple des tentatives de connexion continuent d'échouer) mais elle
n'a plus d'effet sur le service, déjà protégé par les actions précédentes. Un nouvel incident n'est
ouvert que si une cible ou un compte réellement nouveau apparaît : l'anomalie qui continue à l'identique
ne redéclenche pas inutilement toute l'échelle.

## ESCALATION
Toutes les actions de l'échelle ont été tentées et la vérification continue d'échouer. C'est le seul
état où une intervention humaine est attendue. Si cela arrive pendant la démonstration devant le jury,
l'axe « remédiation autonome » de la grille est affecté : c'est pourquoi ce scénario doit être répété
et testé intensivement avant la soutenance (voir `que-faire-si-escalation.md`).
