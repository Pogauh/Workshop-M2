# Câblage du badge ESP8266 — schéma détaillé

Matériel : 1x carte ESP8266 (NodeMCU v2/v3 ou Wemos D1 Mini — brochage "Dx" identique), 1x LED bicolore
rouge/vert 3 broches **cathode commune**, 2x résistance **220 Ω** (1/4 W), câbles Dupont, breadboard.
Schéma visuel (diagramme) envoyé séparément comme artefact ; ce document en donne le détail exploitable
sans l'image (valeurs, justification, procédure de vérification).

## 1. Repérage des broches de l'ESP8266

| Broche carte (silkscreen) | GPIO interne | Rôle dans ce montage |
|---|---|---|
| **D1** | GPIO5 | Anode LED **verte**, via résistance 220 Ω |
| **D2** | GPIO4 | Anode LED **rouge**, via résistance 220 Ω |
| **G** (GND, n'importe laquelle) | — | Cathode commune de la LED |
| **5V / VU** (ou USB) | — | Alimentation de la carte (uniquement, pas utilisée pour la LED) |

D1/D2 sont choisies volontairement : ce sont des broches GPIO « neutres » au démarrage (contrairement à
GPIO0, GPIO2, GPIO15 qui fixent le mode de boot de l'ESP8266 — une LED branchée dessus peut empêcher la
carte de démarrer correctement) et GPIO16/D0 (sans PWM/interruptions, à éviter par principe même si non
utilisé ici en PWM).

## 2. Repérage des 3 broches de la LED bicolore

Une LED bicolore 3 broches a généralement, dans l'ordre (**à vérifier sur votre composant, voir §4**) :
`Anode Rouge — Cathode commune — Anode Verte`. La cathode commune est très souvent la broche la **plus
longue** du trio sur ce type de boîtier (convention inverse d'une LED simple, où c'est l'anode qui est
longue) — **ne vous fiez pas uniquement à la longueur, vérifiez au multimètre (§4)**.

## 3. Schéma de câblage (texte)

```
                         ESP8266 (NodeMCU / Wemos D1 Mini)
                        ┌───────────────────────────────┐
                        │                                │
              D1 (GPIO5)●────[ R1 : 220 Ω ]────┐         │
                        │                       │         │
              D2 (GPIO4)●────[ R2 : 220 Ω ]──┐  │         │
                        │                     │  │         │
                   G/GND●──────────────┐      │  │         │
                        │              │      │  │         │
                        └──────────────┼──────┼──┼─────────┘
                                       │      │  │
                                       │      │  │      LED bicolore (cathode commune)
                                       │      │  │      ┌─────────────┐
                                       │      │  └──────┤ Anode Verte │
                                       │      │         ├─────────────┤
                                       │      └─────────┤ Anode Rouge │
                                       │                ├─────────────┤
                                       └────────────────┤  Cathode    │ (broche commune, souvent la + longue)
                                                         └─────────────┘
```

Résumé en une ligne par fil :
1. `D1 (GPIO5)` → R1 (220 Ω) → **anode verte** de la LED
2. `D2 (GPIO4)` → R2 (220 Ω) → **anode rouge** de la LED
3. `GND` (n'importe quelle broche G) → **cathode commune** de la LED
4. Alimentation de la carte : câble USB standard (5V), **sans rapport avec le montage LED**

Aucun autre composant nécessaire : pas de régulateur, pas de condensateur — le courant consommé par la
LED (quelques mA, voir §5) est négligeable devant ce que peut fournir la carte.

## 4. Vérifier le brochage AVANT de souder/brancher définitivement

Avec un multimètre en mode « test de diode » (symbole diode, souvent partagé avec le mode continuité) :
1. Touchez une broche avec le fil **rouge (+)** du multimètre, une autre avec le fil **noir (−)**.
2. Si une couleur s'allume faiblement : le fil rouge est sur l'**anode** de cette couleur, le fil noir
   sur la **cathode commune**.
3. Répétez sur la 3ᵉ broche avec le fil noir **laissé en place** : si l'autre couleur s'allume, cette
   broche confirme bien la cathode commune (elle allume les deux couleurs selon l'anode testée).
4. Si rien ne s'allume dans aucune combinaison : c'est probablement une LED **anode commune**, pas
   cathode commune — voir §6 (variante firmware).

## 5. Calcul des résistances (justification, pas une valeur arbitraire)

Loi d'Ohm : `R = (V_alim − V_LED) / I_souhaité`. L'ESP8266 sort 3,3 V en logique haute.

| Couleur | V_LED typique (à vérifier sur la doc du composant) | Courant visé | R calculée | R retenue | Courant réel résultant |
|---|---|---|---|---|---|
| Rouge | ≈ 2,0 V | 8 mA | (3,3−2,0)/0,008 ≈ 162 Ω | **220 Ω** | (3,3−2,0)/220 ≈ 5,9 mA |
| Verte | ≈ 2,2 V | 8 mA | (3,3−2,2)/0,008 ≈ 137 Ω | **220 Ω** | (3,3−2,2)/220 ≈ 5,0 mA |

220 Ω pour les deux couleurs : une seule valeur à acheter/poser, courant obtenu (5-6 mA) largement sous
la limite recommandée par Espressif (~12 mA en continu par broche GPIO, maximum absolu du chip encore
plus contraignant en cumulé) — LED bien visible sans risque pour la broche. Si vous préférez une marge
plus confortable (LED légèrement moins lumineuse, résistances moins sollicitées) : **330 Ω** convient
aussi (≈ 3,5-4 mA) sans aucun changement de firmware.

## 6. Variante : LED à anode commune (si le test du §4 l'indique)

Inversez seulement le fil 3 : la **broche commune va au 3,3V** (pas au GND), et les résistances restent
entre les GPIO et les anodes individuelles **sauf qu'il faut alors relier les GPIO aux CATHODES** de
chaque couleur (le sens change). Dans `esp8266/platformio.ini`, passez `LED_ACTIVE_LOW=0` à
`LED_ACTIVE_LOW=1` — le firmware inverse alors sa logique (LOW = allumé) sans aucune autre modification
de code. Aucune incidence sur les résistances ni leur valeur.

## 7. Vérification finale après câblage (sans dépendre du reste de la plateforme)
```bash
curl -X POST http://192.168.137.50/led -H "Content-Type: application/json" -d '{"state":"green_blink"}'
```
La LED doit clignoter vert. `docs/esp8266-wiring.md` ne couvre que l'électronique ; la prise en main
logicielle (flash via CLion+PlatformIO, tous les états LED disponibles) est dans `esp8266/README.md`,
et l'intégration complète au flux d'authentification dans `docs/face-auth.md`.

## Nomenclature (BOM)
| Réf. | Désignation | Quantité |
|---|---|---|
| U1 | ESP8266 (NodeMCU v2/v3 ou Wemos D1 Mini) | 1 |
| D1 (composant) | LED bicolore rouge/vert, 3 broches, cathode commune | 1 |
| R1, R2 | Résistance 220 Ω, 1/4 W | 2 |
| — | Câbles Dupont mâle-mâle (breadboard) | 3 |
| — | Breadboard (facultatif si câblage direct/soudé) | 1 |
| — | Câble USB (alimentation + programmation) | 1 |
