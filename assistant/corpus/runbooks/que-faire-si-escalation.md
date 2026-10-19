# Runbook — Que faire si l'état devient ESCALATION

ESCALATION signifie que l'échelle complète d'actions a été tentée sans que la sonde de transaction ne
repasse au vert. C'est le seul cas où une intervention humaine est attendue par conception.

## Diagnostic rapide (dans cet ordre)
1. Regarder le journal d'incident sur le dashboard (panneau « Incident » et « Mémoire immunitaire et
   journal du moteur ») : quelle a été la dernière action tentée et quel était le message d'erreur de
   la sonde ?
2. Vérifier `docker compose ps` : un service est-il réellement arrêté (`exited`) plutôt que lent ?
3. Vérifier les journaux de la base (`docker compose logs db`) : la base répond-elle ?
4. Vérifier `/api/health/deep` manuellement : l'invariant comptable (600000) est-il respecté ? Si non,
   ne pas se contenter de relancer le service : il peut s'agir d'une incohérence de données, à
   distinguer d'une simple panne de disponibilité (voir `invariant-comptable.md`).

## En répétition (avant la soutenance)
Si ESCALATION survient pendant vos essais, c'est un signal à corriger, pas à masquer : ajustez les
seuils (`SUSPECT_MIN_RPS`, le nombre K de fenêtres consécutives), le nombre de sondes requises
(`verify_need`), ou le temps de vérification (`verify_timeout`) dans `remediator/app/engine.py`
(`Config`), puis re-testez. L'objectif est que RESTORED soit atteint de manière fiable et
reproductible sur le scénario d'attaque retenu pour la vidéo chronométrée.
