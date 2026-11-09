/*
 * Fila Zero UBS — sensor de lotação da sala de espera (ESP32, Wokwi)
 *
 * Dois HC-SR04 na porta: a ordem em que disparam diz se alguém entrou ou saiu.
 * DHT22 mede a temperatura. LED acende quando a ocupação passa de 90% da capacidade.
 * Publica um JSON por MQTT a cada 30 s (ou logo após uma passagem).
 *
 * Bibliotecas (Library Manager do Wokwi): PubSubClient, DHT sensor library, ArduinoJson.
 */
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ---- configuração -------------------------------------------------------
const char* WIFI_SSID   = "Wokwi-GUEST";
const char* WIFI_SENHA  = "";
const char* MQTT_HOST   = "broker.hivemq.com";   // Wokwi não alcança o Mosquitto local
const int   MQTT_PORTA  = 1883;
const char* UBS_ID      = "jardim-esperanca";
const char* UBS_NOME    = "UBS Jardim Esperanca";
const int   CAPACIDADE  = 30;                    // cadeiras na sala
const float LIMITE      = 0.90;                  // alerta acima de 90%
const unsigned long INTERVALO_MS = 30000;

// ---- pinos --------------------------------------------------------------
const int TRIG_DENTRO = 5,  ECHO_DENTRO = 18;
const int TRIG_FORA   = 19, ECHO_FORA   = 21;
const int PINO_DHT = 4, PINO_LED = 2, PINO_BOTAO = 15;
const float DIST_PASSAGEM_CM = 60.0;

DHT dht(PINO_DHT, DHT22);
WiFiClient wifi;
PubSubClient mqtt(wifi);
char topico[64];

int ocupacao = 0, entradas = 0, saidas = 0;
unsigned long ultimaPublicacao = 0;
unsigned long disparoFora = 0, disparoDentro = 0;   // millis() da última detecção em cada sensor
const unsigned long JANELA_MS = 1500;               // tempo máximo entre os dois sensores

float medirCm(int trig, int echo) {
  digitalWrite(trig, LOW);  delayMicroseconds(2);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  long duracao = pulseIn(echo, HIGH, 30000);
  return duracao == 0 ? 999.0 : duracao * 0.0343 / 2.0;
}

void conectar() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.begin(WIFI_SSID, WIFI_SENHA);
    while (WiFi.status() != WL_CONNECTED) { delay(250); Serial.print("."); }
    Serial.println("\nWi-Fi ok");
  }
  while (!mqtt.connected()) {
    String id = String("filazero-") + UBS_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqtt.connect(id.c_str())) Serial.println("MQTT ok");
    else { Serial.print("MQTT falhou, rc="); Serial.println(mqtt.state()); delay(2000); }
  }
}

void publicar() {
  bool alerta = ocupacao >= CAPACIDADE * LIMITE;
  digitalWrite(PINO_LED, alerta ? HIGH : LOW);

  StaticJsonDocument<256> doc;
  doc["ubs"] = UBS_NOME;
  doc["ocupacao"] = ocupacao;
  doc["capacidade"] = CAPACIDADE;
  float t = dht.readTemperature();
  if (!isnan(t)) doc["temperatura"] = round(t * 10) / 10.0;
  doc["entradas"] = entradas;
  doc["saidas"] = saidas;
  doc["alerta"] = alerta;
  doc["origem"] = "esp32";

  char corpo[256];
  serializeJson(doc, corpo);
  mqtt.publish(topico, corpo, true);   // retain: quem assinar depois recebe a última leitura
  Serial.println(corpo);
  ultimaPublicacao = millis();
}

void detectarPassagem() {
  unsigned long agora = millis();
  if (medirCm(TRIG_FORA, ECHO_FORA) < DIST_PASSAGEM_CM && agora - disparoFora > JANELA_MS) disparoFora = agora;
  if (medirCm(TRIG_DENTRO, ECHO_DENTRO) < DIST_PASSAGEM_CM && agora - disparoDentro > JANELA_MS) disparoDentro = agora;

  bool ambos = disparoFora && disparoDentro && labs((long)disparoFora - (long)disparoDentro) < JANELA_MS;
  if (!ambos) return;
  if (disparoFora < disparoDentro) { ocupacao++; entradas++; Serial.println("entrou"); }
  else if (ocupacao > 0)           { ocupacao--; saidas++;   Serial.println("saiu"); }
  disparoFora = disparoDentro = 0;
  publicar();
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_DENTRO, OUTPUT); pinMode(ECHO_DENTRO, INPUT);
  pinMode(TRIG_FORA, OUTPUT);   pinMode(ECHO_FORA, INPUT);
  pinMode(PINO_LED, OUTPUT);    pinMode(PINO_BOTAO, INPUT_PULLUP);
  dht.begin();
  snprintf(topico, sizeof(topico), "filazero/ubs/%s/sala", UBS_ID);
  mqtt.setServer(MQTT_HOST, MQTT_PORTA);
  conectar();
  publicar();
}

void loop() {
  conectar();
  mqtt.loop();
  detectarPassagem();
  if (digitalRead(PINO_BOTAO) == LOW) { ocupacao = entradas = saidas = 0; publicar(); delay(500); }
  if (millis() - ultimaPublicacao > INTERVALO_MS) publicar();
  delay(50);
}
