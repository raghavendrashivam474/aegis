#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "config.h"

// --- Networking Globals ---
WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastPublishTime = 0;
unsigned long observationSeq = 0;

// --- Sensor Reading / Controlled Generator ---
struct SensorReadings {
    float temperature;
    float humidity;
    float vibration_rms;
};

SensorReadings readSensors() {
    SensorReadings r;
    // Base values with controlled micro-fluctuations (or real analog/I2C reads)
    float jitter = ((random(0, 100) - 50) / 100.0f);
    r.temperature = 26.5f + (jitter * 0.8f);
    r.humidity = 48.0f + (jitter * 2.0f);
    r.vibration_rms = 1.85f + (jitter * 0.15f);
    return r;
}

// --- ISO 8601 Timestamp Approximation ---
String getIsoTimestamp() {
    unsigned long sec = millis() / 1000;
    char buf[32];
    snprintf(buf, sizeof(buf), "2026-03-01T%02lu:%02lu:%02lu+00:00", (sec / 3600) % 24, (sec / 60) % 60, sec % 60);
    return String(buf);
}

// --- Connection Management ---
void ensureWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.print("Connecting to Wi-Fi: ");
    Serial.println(WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWi-Fi Connected. IP: " + WiFi.localIP().toString());
    } else {
        Serial.println("\nWi-Fi connection timed out. Will retry next cycle.");
    }
}

void ensureMQTT() {
    if (mqttClient.connected()) return;
    if (WiFi.status() != WL_CONNECTED) return;

    Serial.print("Connecting to MQTT Broker at ");
    Serial.print(MQTT_HOST);
    Serial.print(":");
    Serial.println(MQTT_PORT);

    if (mqttClient.connect(MQTT_CLIENT_ID)) {
        Serial.println("Connected to MQTT Broker successfully!");
    } else {
        Serial.print("MQTT connection failed, state=");
        Serial.println(mqttClient.state());
    }
}

// --- Telemetry Publishing ---
void publishTelemetry() {
    SensorReadings readings = readSensors();
    String ts = getIsoTimestamp();
    observationSeq++;

    // Construct JSON payload compliant with Aegis TelemetryEnvelope v1 contract
    StaticJsonDocument<1024> doc;
    doc["schema_version"] = SCHEMA_VERSION;
    doc["source_device_id"] = DEVICE_ID;
    doc["sent_at_iso"] = ts;

    JsonArray observations = doc.createNestedArray("observations");

    // Observation 1: Temperature
    JsonObject obsTemp = observations.createNestedObject();
    char obsIdTemp[32];
    snprintf(obsIdTemp, sizeof(obsIdTemp), "obs-esp-temp-%lu", observationSeq);
    obsTemp["observation_id"] = obsIdTemp;
    obsTemp["sensor_id"] = SENSOR_TEMP_ID;
    obsTemp["timestamp_iso"] = ts;
    obsTemp["value"] = serialized(String(readings.temperature, 2));
    obsTemp["unit"] = "celsius";
    obsTemp["quality"] = "GOOD";

    // Observation 2: Humidity
    JsonObject obsHum = observations.createNestedObject();
    char obsIdHum[32];
    snprintf(obsIdHum, sizeof(obsIdHum), "obs-esp-hum-%lu", observationSeq);
    obsHum["observation_id"] = obsIdHum;
    obsHum["sensor_id"] = SENSOR_HUMIDITY_ID;
    obsHum["timestamp_iso"] = ts;
    obsHum["value"] = serialized(String(readings.humidity, 2));
    obsHum["unit"] = "percent";
    obsHum["quality"] = "GOOD";

    // Observation 3: Vibration
    JsonObject obsVib = observations.createNestedObject();
    char obsIdVib[32];
    snprintf(obsIdVib, sizeof(obsIdVib), "obs-esp-vib-%lu", observationSeq);
    obsVib["observation_id"] = obsIdVib;
    obsVib["sensor_id"] = SENSOR_VIBRATION_ID;
    obsVib["timestamp_iso"] = ts;
    obsVib["value"] = serialized(String(readings.vibration_rms, 2));
    obsVib["unit"] = "mm/s";
    obsVib["quality"] = "GOOD";

    // Metadata
    JsonObject meta = doc.createNestedObject("metadata");
    meta["source"] = "physical_esp32";
    meta["transport"] = "mqtt";
    meta["seq"] = observationSeq;

    char output[1024];
    serializeJson(doc, output);

    if (mqttClient.publish(MQTT_TOPIC, output)) {
        Serial.printf("[TX] Telemetry published to %s: %s\n", MQTT_TOPIC, output);
    } else {
        Serial.println("[ERR] Failed to publish telemetry to MQTT broker.");
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n=== Aegis ESP32 Edge Producer Node Starting ===");
    Serial.println("Device ID: " DEVICE_ID);

    mqttClient.setServer(MQTT_HOST, MQTT_PORT);
    mqttClient.setBufferSize(1024); // Expand buffer to fit full envelope
}

void loop() {
    ensureWiFi();
    ensureMQTT();

    mqttClient.loop();

    unsigned long now = millis();
    if (now - lastPublishTime >= PUBLISH_INTERVAL_MS) {
        lastPublishTime = now;
        if (mqttClient.connected()) {
            publishTelemetry();
        }
    }
    delay(10);
}
