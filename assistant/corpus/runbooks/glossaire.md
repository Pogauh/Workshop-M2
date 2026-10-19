# Glossaire du projet (sigles du sujet)

- **AIOps** : IA appliquee a l'exploitation informatique (ici: le `detector`).
- **RAG** : reponse d'un LLM appuyee sur une recherche documentaire (c'est ce que fait cet assistant).
- **ML** : apprentissage automatique (IsolationForest, non supervise, entraine sur trafic normal).
- **IaC** : infrastructure decrite et deployee par code (`docker-compose.yml`, `ansible/`).
- **WAF** : pare-feu applicatif (le composant `waf`, premiere ligne de defense).
- **SIEM** : centralisation et correlation des journaux (ici, Loki + regles de correlation R1 a R5
  dans `detector/app/siem.py`).
- **EBIOS RM** : methode d'appreciation des risques cyber (voir `docs/ebios-rm.md`).
- **NIS2 / DORA** : reglementations europeennes citees dans `docs/nis2-dora.md`.
- **PCA / PRA** : plans de continuite et de reprise d'activite (voir `docs/pca-pra.md`).
- **Zero-Touch Recovery** : reprise automatisee sans intervention humaine — l'objectif central du
  demonstrateur, mesure par l'axe 1 de la grille du jury.
- **MTTR** : duree entre la detection d'un incident et sa restauration verifiee ; affichee par le
  dashboard (`mttr_s`) a la fin de chaque incident restaure.
