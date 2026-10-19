# Préparation de VidChrono.mp4 (≤ 60 s, sans coupure)

## Contrainte
Un seul plan continu, pas de montage/coupure. Préparez donc la séquence pour qu'elle tienne en une
prise, répétée jusqu'à être fluide — `scripts/repeat_demo.sh` sert justement à répéter vite.

## Séquence proposée (à chronométrer et ajuster)
1. **0–5 s** — Montrer le dashboard en `HOMEOSTASIS`, un paiement normal passé depuis l'interface
   PayAlpha (lien visible dans l'en-tête du dashboard).
2. **5–10 s** — Lancer l'attaque choisie (`./scripts/repeat_demo.sh dos` ou le déclencheur du
   brute-force), visible à l'écran (terminal ou second moniteur).
3. **10–20 s** — Le dashboard bascule en `SURVEILLANCE` puis `IMMUNITY` : signes vitaux qui décrochent,
   alerte SIEM qui apparaît, première action listée dans le panneau Incident.
4. **20–45 s** — Actions successives de l'échelle, bande « Transaction témoin » qui repasse au vert,
   état `REGENERATION` puis `RESTORED`. Montrer le MTTR affiché.
5. **45–60 s** — Retour rapide sur l'interface PayAlpha : un nouveau paiement passe normalement,
   preuve que le service est réellement utilisable, pas seulement « up ».

## Checklist avant la prise
- [ ] `./scripts/reset.sh` juste avant (état `HOMEOSTASIS` propre).
- [ ] Modèle ML déjà entraîné (`scripts/bootstrap_model.sh` fait au préalable, pas pendant la vidéo).
- [ ] Fenêtre du dashboard (`localhost:3000`) et de l'interface PayAlpha (`192.168.137.1:8080`) prêtes
      côte à côte ou en bascule rapide.
- [ ] Minuteur affiché à l'écran si l'outil de capture ne l'incruste pas.
- [ ] Volume/micro coupé ou commentaire préparé à l'avance (pas d'improvisation sous 60 s).
