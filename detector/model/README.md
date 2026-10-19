# Modèle livré avec le dépôt

Après l'entraînement (`scripts/bootstrap_model.sh`), exportez le modèle ici avec `scripts/export_model.sh` :

- `model.joblib` : scaler + IsolationForest + seuil (utilisé par le détecteur si `/data/model.joblib` est absent) ;
- `report.json`  : résultats réels (taux de faux positifs, rappel par type d'attaque, délai de détection)
  à reporter dans la section IA/Data du dossier.

Ces fichiers contiennent uniquement des statistiques de trafic fictif : ils peuvent être versionnés.
