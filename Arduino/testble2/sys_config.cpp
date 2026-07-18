// sys_config.cpp
#include "sys_config.h"

// Default-Werte entsprechend alter config.h
SystemConfig sysConfig = {
    /* pin_reset_button */ 7,
    
    // PATCHER BEGIN: CIRCULATION_CONFIG_DEFAULTS

    /* pin_circ_fan */ 45,
    /* pin_circ_tacho */ 2,
    /* pin_circ_tacho_pull */ 1,
    /* pin_circ_fan2 */ -1,
    /* pin_circ_tacho2 */ -1,
    /* pin_circ_tacho2_pull */ 1,
    /* pin_circ_fan3 */ -1,
    /* pin_circ_tacho3 */ -1,
    /* pin_circ_tacho3_pull */ 1,
// PATCHER END: CIRCULATION_CONFIG_DEFAULTS


    /* pin_exh_fan */ 47,
    /* pin_exh_tacho */ 1,
    /* pin_exh_tacho_pull */ 1,

    /* pin_light */ 21,

    /* i2c_sda */ 4,
    /* i2c_scl */ 5,

    /* rtc_sda */ 13,
    /* rtc_scl */ 14,

    /* pin_bat */ 6,
    /* pin_bat_pull */ 0
};