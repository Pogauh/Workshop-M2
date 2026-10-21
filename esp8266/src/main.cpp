/* PROJECT RESILIENCE-ALPHA — badge lumineux ESP8266
 * LED bicolore (rouge/vert) pilotée en WiFi par les services « face » (reconnaissance) et « auth »
 * (mot de passe) du PC Hôte, pendant la connexion renforcée au back-office.
 *
 * Volontairement « bête » côté réseau : reçoit un ÉTAT discret (ex. "green_blink") et gère LUI-MÊME le
 * minutage (clignotement, extinction après 30 s, 10 clignotements rouges...) sans dépendre d'appels
 * réseau répétés et parfaitement synchronisés depuis le serveur — plus robuste sur un WiFi de hotspot.
 * Boucle principale non bloquante (millis(), jamais delay()) : le serveur HTTP reste réactif pendant
 * qu'un motif de clignotement est en cours.
 *
 * Câblage détaillé : docs/esp8266-wiring.md (racine du dépôt).
 * IDE : JetBrains CLion + plugin PlatformIO (voir esp8266/README.md pour la prise en main). */
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>

// ---- Broches et réseau : définis dans platformio.ini (build_flags), jamais codés en dur ici ----
#ifndef LED_GREEN_PIN
#define LED_GREEN_PIN 5   // D1
#endif
#ifndef LED_RED_PIN
#define LED_RED_PIN 4     // D2
#endif
#ifndef LED_ACTIVE_LOW
#define LED_ACTIVE_LOW 0  // 0 = cathode commune (HIGH = allumé) ; 1 = anode commune (LOW = allumé)
#endif

static const uint16_t HTTP_PORT = 80;
static const uint32_t BLINK_SLOW_MS = 400;    // vert clignotant (attente mot de passe)
static const uint32_t BLINK_FAST_MS = 300;    // rouge clignotant x10 (mot de passe refusé)
static const uint32_t SOLID_MS = 30000;       // vert fixe / rouge fixe : 30 s (cf. consigne)
static const uint8_t  RED_BLINK_COUNT = 10;   // nombre de clignotements rouges avant extinction

ESP8266WebServer server(HTTP_PORT);

enum class LedState : uint8_t { OFF, GREEN_BLINK, GREEN_SOLID_30, RED_SOLID_30, RED_BLINK10 };

LedState state = LedState::OFF;
uint32_t stateStartMs = 0;     // date d'entrée dans l'état courant
uint32_t lastToggleMs = 0;     // dernier basculement on/off (états clignotants)
bool ledPhysOn = false;        // la LED est-elle physiquement allumée à cet instant ?
uint8_t blinkToggles = 0;      // compteur de bascules pour RED_BLINK10 (2 bascules = 1 clignotement complet)

void setLeds(bool green, bool red) {
#if LED_ACTIVE_LOW
  digitalWrite(LED_GREEN_PIN, green ? LOW : HIGH);   // anode commune : la broche GPIO tire vers le bas pour allumer
  digitalWrite(LED_RED_PIN, red ? LOW : HIGH);
#else
  digitalWrite(LED_GREEN_PIN, green ? HIGH : LOW);   // cathode commune (defaut) : la broche GPIO fournit le courant
  digitalWrite(LED_RED_PIN, red ? HIGH : LOW);
#endif
}

const char *stateName(LedState s) {
  switch (s) {
    case LedState::OFF: return "off";
    case LedState::GREEN_BLINK: return "green_blink";
    case LedState::GREEN_SOLID_30: return "green_solid_30";
    case LedState::RED_SOLID_30: return "red_solid_30";
    case LedState::RED_BLINK10: return "red_blink10";
  }
  return "off";
}

/* Démarre un nouvel état : remet les compteurs à zéro, impose immédiatement la bonne sortie LED
 * (pas d'attente du prochain tick de boucle avant le premier affichage). */
void enterState(LedState s) {
  state = s; stateStartMs = millis(); lastToggleMs = stateStartMs; blinkToggles = 0;
  switch (s) {
    case LedState::OFF:            ledPhysOn = false; setLeds(false, false); break;
    case LedState::GREEN_BLINK:    ledPhysOn = true;  setLeds(true, false);  break;
    case LedState::GREEN_SOLID_30: ledPhysOn = true;  setLeds(true, false);  break;
    case LedState::RED_SOLID_30:   ledPhysOn = true;  setLeds(false, true);  break;
    case LedState::RED_BLINK10:    ledPhysOn = true;  setLeds(false, true);  break;
  }
}

/* Appelée à chaque tour de loop() : fait avancer le minutage de l'état courant sans jamais bloquer. */
void tickState() {
  uint32_t now = millis();
  switch (state) {
    case LedState::OFF:
      break;                                        // rien à faire, éteint tant qu'aucun ordre n'arrive
    case LedState::GREEN_BLINK:
      if (now - lastToggleMs >= BLINK_SLOW_MS) { ledPhysOn = !ledPhysOn; setLeds(ledPhysOn, false); lastToggleMs = now; }
      break;                                        // clignote indéfiniment : s'arrête sur un ordre explicite (mot de passe saisi)
    case LedState::GREEN_SOLID_30:
    case LedState::RED_SOLID_30:
      if (now - stateStartMs >= SOLID_MS) enterState(LedState::OFF);   // extinction automatique après 30 s
      break;
    case LedState::RED_BLINK10:
      if (now - lastToggleMs >= BLINK_FAST_MS) {
        ledPhysOn = !ledPhysOn; setLeds(false, ledPhysOn); lastToggleMs = now; blinkToggles++;
        if (blinkToggles >= RED_BLINK_COUNT * 2) enterState(LedState::OFF);   // 2 bascules = 1 clignotement complet
      }
      break;
  }
}

void sendJson(int code, JsonDocument &doc) {
  String body; serializeJson(doc, body);
  server.sendHeader("Access-Control-Allow-Origin", "*");   // diagnostic depuis un navigateur ; aucune action sensible exposée
  server.send(code, "application/json", body);
}

void handleHealth() {
  JsonDocument doc;
  doc["ok"] = true; doc["state"] = stateName(state); doc["uptime_s"] = millis() / 1000; doc["ip"] = WiFi.localIP().toString();
  sendJson(200, doc);
}

void handleLed() {
  if (server.method() != HTTP_POST) { server.send(405, "application/json", "{\"ok\":false,\"error\":\"POST uniquement\"}"); return; }
  JsonDocument in;
  if (deserializeJson(in, server.arg("plain")) != DeserializationError::Ok || !in["state"].is<const char *>()) {
    server.send(400, "application/json", "{\"ok\":false,\"error\":\"JSON attendu : {\\\"state\\\":\\\"...\\\"}\"}"); return;
  }
  String want = in["state"].as<String>();
  LedState next;
  if      (want == "off")            next = LedState::OFF;
  else if (want == "green_blink")    next = LedState::GREEN_BLINK;
  else if (want == "green_solid_30") next = LedState::GREEN_SOLID_30;
  else if (want == "red_solid_30")   next = LedState::RED_SOLID_30;
  else if (want == "red_blink10")    next = LedState::RED_BLINK10;
  else { server.send(400, "application/json", "{\"ok\":false,\"error\":\"etat inconnu\"}"); return; }
  enterState(next);
  JsonDocument out; out["ok"] = true; out["state"] = stateName(state);
  sendJson(200, out);
}

void setup() {
  pinMode(LED_GREEN_PIN, OUTPUT); pinMode(LED_RED_PIN, OUTPUT);
  enterState(LedState::OFF);                          // par défaut, LED éteinte (cf. consigne)

  Serial.begin(115200); Serial.println("\nRESILIENCE-ALPHA badge — demarrage");

  IPAddress ip, gw, mask;
  ip.fromString(STATIC_IP); gw.fromString(GATEWAY_IP); mask.fromString(SUBNET_MASK);
  WiFi.mode(WIFI_STA);
  WiFi.config(ip, gw, mask);                           // IP fixe : les services du PC Hôte n'ont pas à (re)découvrir l'IP du badge
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Connexion a %s", WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300); Serial.print(".");                     // acceptable ici : avant setup() complet, le serveur HTTP n'existe pas encore
    // Avertit visuellement d'une tentative de connexion en cours (vert/rouge alterné) sans dépendre du serveur HTTP
    setLeds((millis() / 300) % 2 == 0, (millis() / 300) % 2 != 0);
  }
  setLeds(false, false);
  Serial.printf("\nConnecte : %s\n", WiFi.localIP().toString().c_str());

  server.on("/health", HTTP_GET, handleHealth);
  server.on("/", HTTP_GET, handleHealth);
  server.on("/led", HTTP_POST, handleLed);
  server.begin();
  Serial.println("Serveur HTTP demarre sur le port 80 (POST /led, GET /health)");
}

void loop() {
  server.handleClient();
  tickState();
  // Reconnexion automatique si le hotspot redémarre (ex. relance du PC Hôte) : pas de blocage, juste une tentative périodique.
  static uint32_t lastReconnectAttempt = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - lastReconnectAttempt > 5000) {
    lastReconnectAttempt = millis(); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}
