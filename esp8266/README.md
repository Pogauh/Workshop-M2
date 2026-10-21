# Badge lumineux ESP8266 — PROJECT RESILIENCE-ALPHA

LED bicolore (rouge/vert) qui matérialise l'état de l'authentification renforcée du back-office
(caméra + IA de reconnaissance faciale + mot de passe). Détail du comportement et du câblage :
`docs/esp8266-wiring.md` (racine du dépôt) — ce fichier couvre la prise en main logicielle.

## Matériel
- 1x carte ESP8266 (NodeMCU v2/v3 ou Wemos D1 Mini — même brochage "Dx")
- 1x LED bicolore rouge/vert, 3 broches, cathode commune
- 2x résistance 220 Ω (1/4 W)
- Câbles Dupont + breadboard
- Câblage complet, schéma et justification des valeurs : **`docs/esp8266-wiring.md`**

## IDE imposé : JetBrains CLion + PlatformIO
1. Installer le plugin **PlatformIO for CLion** (Settings → Plugins → rechercher "PlatformIO").
2. `File → Open...` → sélectionner le dossier `esp8266/` (celui qui contient `platformio.ini`).
   CLion détecte automatiquement le projet PlatformIO et propose de l'importer.
3. Adapter dans `platformio.ini` (section `build_flags`) avant le premier flash :
   - `WIFI_SSID` : nom exact du hotspot Windows du PC Hôte (`RESILIENCE-G<n>`)
   - `WIFI_PASSWORD` : mot de passe de ce hotspot
   - `STATIC_IP` : IP fixe souhaitée pour le badge (défaut `192.168.137.50`, hors plage DHCP — voir
     `docs/windows-setup.md` pour la plage DHCP réelle de votre hotspot et ajuster si collision)
   - Si carte Wemos D1 Mini : changer `board = nodemcuv2` en `board = d1_mini` (même brochage "Dx",
     aucun autre changement nécessaire)
4. Brancher l'ESP8266 en USB, puis dans CLion : barre d'outils PlatformIO → **Upload** (ou `pio run -t upload`
   en ligne de commande depuis ce dossier). Le port série est détecté automatiquement.
5. Ouvrir le **Moniteur série** (115200 bauds) pour vérifier la connexion WiFi et relever l'IP obtenue —
   doit correspondre à `STATIC_IP`.

## Vérifier que le badge répond (sans toucher au reste de la plateforme)
```bash
curl http://192.168.137.50/health
# {"ok":true,"state":"off","uptime_s":42,"ip":"192.168.137.50"}
curl -X POST http://192.168.137.50/led -H "Content-Type: application/json" -d '{"state":"green_blink"}'
curl -X POST http://192.168.137.50/led -H "Content-Type: application/json" -d '{"state":"off"}'
```
Si `STATIC_IP` a été changé dans `platformio.ini`, mettez aussi à jour `ESP_LED_URL` dans `.env`
(utilisé par les services `face` et `auth` — voir `docs/face-auth.md`) pour qu'ils pointent vers la
même adresse.

## États LED exposés (`POST /led {"state": "..."}`)
| État | Effet | Durée |
|---|---|---|
| `off` | éteinte | — (par défaut au démarrage) |
| `green_blink` | vert clignotant (0,4 s) | indéfini, jusqu'au prochain ordre |
| `green_solid_30` | vert fixe | 30 s puis extinction automatique |
| `red_solid_30` | rouge fixe | 30 s puis extinction automatique |
| `red_blink10` | rouge clignotant (0,3 s) | 10 clignotements puis extinction automatique |

Le minutage (30 s, 10 clignotements) est géré **par le badge lui-même**, pas par le serveur qui envoie
l'ordre : plus robuste si le WiFi du hotspot a un peu de latence ou une coupure ponctuelle.

## Si aucun badge physique n'est branché
Les services `face`/`auth` envoient l'ordre LED en « best-effort » : un badge injoignable (éteint, pas
encore flashé, mauvaise IP) est journalisé mais **ne bloque jamais l'authentification** — la LED est un
indicateur visuel, pas un verrou de sécurité. Vous pouvez développer/tester tout le reste de la chaîne
(caméra, IA, mot de passe) sans le matériel physique branché.
