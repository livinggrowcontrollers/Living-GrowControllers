#ifndef CONFIG_H
#define CONFIG_H

// DEPRECATED: The static macro-based `config.h` has been replaced by
// `sys_config.h` which provides a runtime-configurable `SystemConfig`.
//
// This header remains as a lightweight compatibility shim. Do not add new
// macros here; migrate code to include `sys_config.h` and read pins via
// `sysConfig` (e.g. `sysConfig.pin_light`).

#include "sys_config.h"

#endif // CONFIG_H