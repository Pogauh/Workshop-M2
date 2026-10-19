# Runbook — L'invariant comptable (preuve de guérison, pas juste « ça répond »)

`/api/health/deep` additionne les soldes des 6 comptes de démonstration (`alice`, `bob`, `carol`,
`attacker`, `probe`, `merchant`). La somme doit toujours valoir 600000.00 (6 × 100000.00). C'est le
moyen le plus simple de distinguer :
- un service qui répond mais a des données incohérentes (grave : argent créé ou perdu) ;
- un service réellement rétabli (disponible ET cohérent).

Un service disponible dont les données sont incohérentes n'est pas considéré comme réparé. La sonde
du moteur de remédiation (fonction `probe()`) vérifie les trois éléments à la fois : paiement accepté
(201), relecture du paiement (200), et `consistent: true` sur `/api/health/deep`. Les trois doivent
réussir ensemble, et plusieurs fois de suite, avant que l'état ne passe à RESTORED.
