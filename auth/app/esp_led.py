"""Client « best-effort » vers le badge ESP8266 (voir esp8266/README.md pour le protocole). Un badge
injoignable ne doit JAMAIS bloquer l'authentification : la LED est un indicateur visuel, pas un verrou de
sécurité. Dupliqué depuis face/app/esp_led.py (même logique, deux services indépendants — voir
face/app/ticket.py pour la même remarque sur face_ticket.py)."""
import os

import httpx

ESP_LED_URL = os.getenv("ESP_LED_URL", "").rstrip("/")


def set_led(state: str) -> bool:
    if not ESP_LED_URL:
        return False
    try:
        r = httpx.post(f"{ESP_LED_URL}/led", json={"state": state}, timeout=2)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"badge ESP8266 injoignable (état demandé: {state}): {e}", flush=True)
        return False
