/* 
   ================================================================
   SMARTFARM MAPPI32 - KODE FINAL SERVER LOKAL
   Disesuaikan untuk Menembak ke IP Laptop Jaringan Hotspot HP
   Disusun oleh tim IOT kelompok Smart Broiler PMLD2026_TRI TRPL JAYA
   Dibuat oleh Dafa Novran Hasjrullah dan Muhammad Ilham TRI, SV, UGM, Oktober 2026
   ================================================================
*/

#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <WiFi.h>
#include <HTTPClient.h> 

// 1. PENGATURAN HARDWARE (Jalur Solder Pin 17 Mappi32 Anda)
#define DHTPIN 17           
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

const int ammoniaPin = 25;  // Pin analog MQ137 di IO25 Mappi32
int temperatureOffset = 0;
int humidityOffset = 0;

// 2. PENGATURAN JARINGAN WIFI (Hotspot HP Anda)
char ssid[] = "DNH";
char pass[] = "imdafanh";

// 3. PENGATURAN ENDPOINT API LOKAL (Port 8000 FastAPI)
// Mengarah langsung ke IP laptop Anda di jaringan hotspot yang sama
String serverPath = "http://192.168.43.178:8000/api/v1/sensor-data/iot";

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== SMARTFARM MAPPI32 LOCAL POST STARTED ===");
  connectToWiFi();
  dht.begin();
}

void loop() {
  delay(10000); // Mengirim data berkala setiap 10 detik
  
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  // Proteksi error pembacaan sensor
  if (isnan(h) || isnan(t)) {
    Serial.println("[SENSOR ERROR] Gagal membaca DHT22! Mencoba kembali...");
    return; 
  }

  int humidity = (int)h + humidityOffset;
  int temperature = (int)t + temperatureOffset;

  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.print(" *C\t");
  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.println(" %");

  // Pembacaan Kadar Amonia MQ137
  int ammoniaValue = analogRead(ammoniaPin);
  int ammoniaConcentration = analogToAmmoniaPPM(ammoniaValue);
  
  int finalAmmonia = ammoniaConcentration - 35;
  if (finalAmmonia < 0) finalAmmonia = 0;

  Serial.print("Ammonia Concentration: ");
  Serial.print(finalAmmonia);
  Serial.println(" PPM");
  
  // Kirim data terstruktur ke server backend lokal
  sendDataToServer((float)temperature, (float)humidity, (float)finalAmmonia);
}

void connectToWiFi() {
  Serial.print("Menghubungkan ke WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, pass);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[SUKSES] Terhubung ke jaringan WiFi!");
}

void sendDataToServer(float temperature, float humidity, float amonia) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    WiFiClient client; // Menggunakan WiFiClient biasa karena komunikasi lokal tanpa SSL

    Serial.print("Mengirim POST DATA ke URL: ");
    Serial.println(serverPath);

    http.begin(client, serverPath);
    
    // Header Wajib untuk pengiriman paket JSON murni
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", "broilerpaksulasto2026berkahjaya1");


    // Menyusun JSON Payload sesuai dengan Parameter Dokumentasi Backend
    String jsonPayload = "{";
    jsonPayload += "\"kandang_id\":\"KDG-001\","; 
    jsonPayload += "\"temperature\":" + String(temperature, 1) + ",";
    jsonPayload += "\"humidity\":" + String(humidity, 1) + ",";
    jsonPayload += "\"ammonia\":" + String(amonia, 1);
    jsonPayload += "}";

    // Mengirimkan data dengan metode POST
    int httpResponseCode = http.POST(jsonPayload);
    
    if (httpResponseCode > 0) {
      Serial.print("[SERVER RESPOND] Kode Status HTTP: ");
      Serial.println(httpResponseCode);
      String payload = http.getString();
      Serial.println("Balasan Server Backend: " + payload);
    } else {
      Serial.print("[SERVER ERROR] Gagal mengirim POST. Error: ");
      Serial.println(http.errorToString(httpResponseCode).c_str());
    }
    
    http.end(); 
  } else {
    Serial.println("[WIFI ERROR] Jaringan terputus, gagal mengirim data.");
  }
}

int analogToAmmoniaPPM(int analogValue) {
  int ammoniaPPM = map(analogValue, 0, 4095, 0, 100); 
  return ammoniaPPM;
}
