# Modèle livré avec le dépôt

Après l'entraînement (`scripts/bootstrap_model.sh`, qui balaie plusieurs volumes de lignes via
`app.train_sweep` et retient le plus performant), exportez le modèle ici avec `scripts/export_model.sh` :

- `model.joblib` : scaler + IsolationForest + seuil du **meilleur** volume testé (utilisé par le détecteur
  si `/data/model.joblib` est absent) ;
- `report.json`  : résultats réels du modèle retenu (taille d'entraînement, taux de faux positifs, rappel
  et délai de détection par type d'attaque) — à reporter dans la section IA/Data du dossier ;
- `sweep.json`   : comparatif de TOUTES les tailles testées (400 à 3000+ lignes normales) — justifie le
  choix du volume retenu (voir aussi `scripts/export_model.sh`, à adapter pour copier ce fichier).

Ces fichiers contiennent uniquement des statistiques de trafic fictif : ils peuvent être versionnés.
