#include <Arduino.h>
#include "driver/twai.h"
#include <map>

#define CAN_TX_PIN GPIO_NUM_5
#define CAN_RX_PIN GPIO_NUM_4

// Minimum time gap (in milliseconds) between sending frames for the SAME CAN ID
// 20ms = ~50 updates/sec max per ID (ideal balance for SavvyCAN-style analysis)
const uint32_t MIN_ID_INTERVAL_MS = 20;

// Track last send timestamp for each CAN ID
std::map<uint32_t, uint32_t> last_send_time;

void initCAN() {
    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, TWAI_MODE_NORMAL);
    twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS(); // Standard OBD-II speed
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    if (twai_driver_install(&g_config, &t_config, &f_config) == ESP_OK) {
        Serial.println("TWAI Driver Installed");
    }
    if (twai_start() == ESP_OK) {
        Serial.println("TWAI Driver Started");
    }
}

void setup() {
    Serial.begin(115200);
    while (!Serial) { delay(10); }
    initCAN();
}

void loop() {
    twai_message_t message;
    
    // Non-blocking receive check
    if (twai_receive(&message, pdMS_TO_TICKS(1)) == ESP_OK) {
        if (!message.rtr) {
            uint32_t current_time = millis();
            uint32_t id = message.identifier;

            // Rate-limiting check per CAN ID
            if (last_send_time.find(id) != last_send_time.end()) {
                if (current_time - last_send_time[id] < MIN_ID_INTERVAL_MS) {
                    return; // Skip sending to prevent serial log flooding
                }
            }
            
            // Update last sent timestamp
            last_send_time[id] = current_time;

            // Output in standard SLCAN format
            if (!message.extd) {
                Serial.printf("t%03X%d", id, message.data_length_code);
            } else {
                Serial.printf("T%08X%d", id, message.data_length_code);
            }

            for (int i = 0; i < message.data_length_code; i++) {
                Serial.printf("%02X", message.data[i]);
            }
            Serial.print("\r");
        }
    }
}