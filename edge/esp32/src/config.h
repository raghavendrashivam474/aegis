#ifndef AEGIS_CONFIG_H
#define AEGIS_CONFIG_H

// --- Wi-Fi Configuration ---
// Replace with your local Wi-Fi credentials or define via build flags
#ifndef WIFI_SSID
#define WIFI_SSID "YOUR_WIFI_SSID"
#endif

#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#endif

// --- MQTT Broker Configuration ---
#ifndef MQTT_HOST
#define MQTT_HOST "192.168.1.100" // IP address of computer running broker
#endif

#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif

#define MQTT_TOPIC "aegis/telemetry/device-esp32-01"
#define MQTT_CLIENT_ID "aegis-esp32-01"

// --- Stable Aegis Domain Identities ---
#define SCHEMA_VERSION "v1"
#define DEVICE_ID "device-esp32-01"
#define SENSOR_TEMP_ID "sensor-temp-esp32-01"
#define SENSOR_HUMIDITY_ID "sensor-humidity-esp32-01"
#define SENSOR_VIBRATION_ID "sensor-vibration-esp32-01"

// --- Telemetry Sampling Settings ---
#define PUBLISH_INTERVAL_MS 2000 // 2 seconds between telemetry frames

#endif // AEGIS_CONFIG_H
