// sys_config.h
#ifndef SYS_CONFIG_H
#define SYS_CONFIG_H

#include <Arduino.h>

constexpr int SENSOR_OFF = -256;

inline uint8_t get_pull_mode(int pull)
{
    switch (pull) {
        case 1: return INPUT_PULLUP;
        case 2: return INPUT_PULLDOWN;
        default: return INPUT;
    }
}
struct SystemConfig {
    int pin_reset_button;

    int pin_circ_fan;
    int pin_circ_tacho;
    int pin_circ_tacho_pull;

    int pin_exh_fan;
    int pin_exh_tacho;
    int pin_exh_tacho_pull;

    int pin_light;

    int i2c_sda;
    int i2c_scl;

    int rtc_sda;
    int rtc_scl;

    int pin_bat;
    int pin_bat_pull;
};
extern SystemConfig sysConfig;

#endif // SYS_CONFIG_H
