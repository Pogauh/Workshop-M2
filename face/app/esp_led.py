"""Client « best-effort » vers le badge ESP8266 (voir esp8266/README.md pour le protocole). Un badge
injoignable (éteint, pas encore flashé, hors de portée WiFi) est journalisé mais NE DOIT JAMAIS bloquer
l'authentification : la LED est un indicateur visuel pour l'opérateur, pas un verrou de sécurité."""
import os

import httpx

ESP_LED_URL = os.getenv("ESP_LED_URL", "").rstrip("/")   # ex. http://192.168.137.50 ; vide = badge non configuré


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
