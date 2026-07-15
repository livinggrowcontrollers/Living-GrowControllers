#!/usr/bin/env python3
import os
import re
import sys

def get_pristine_lines(marker_id, s=""):
    """Gibt NUR die zusätzlichen Zeilen für Instanz 2 oder 3 zurück."""
    if not s:
        return [] # Instanz 1 bleibt im Code unangetastet!
        
    if marker_id == "CIRCULATION_INIT":
        return [
            f"if (sysConfig.pin_circ_fan{s} == -1 || sysConfig.pin_circ_tacho{s} == -1) {{",
            f"    Serial.println(\"Circulation Fan{s} disabled (sysConfig).\");",
            f"}} else {{",
            f"    circulation_fan{s}_init((uint8_t)sysConfig.pin_circ_fan{s}, (uint8_t)sysConfig.pin_circ_tacho{s});",
            f"}}"
        ]
    elif marker_id == "CIRCULATION_UPDATE":
        return [f"circulation_fan{s}_update();"]
    elif marker_id == "CIRCULATION_INCLUDE":
        return [f'#include "circulation_fan{s}.h"']
    elif marker_id == "CIRCULATION_GET_STATUS":
        return [f"circulation_fan{s}_get_status(obj);"]
    elif marker_id == "CIRCULATION_JSON_UPDATE":
        return [f"circulation_fan{s}_process_json(obj);"]
    elif marker_id == "CIRCULATION_CONFIG":
        return [
            f"int pin_circ_fan{s};",
            f"int pin_circ_tacho{s};",
            f"int pin_circ_tacho_pull{s};"
        ]
    elif marker_id == "CIRCULATION_CONFIG_DEFAULTS":
        return [
            f"/* pin_circ_fan{s} */ 45,",
            f"/* pin_circ_tacho{s} */ 2,",
            f"/* pin_circ_tacho_pull{s} */ 1,"
        ]
    elif marker_id == "CIRCULATION_PREFS_LOAD":
        return [
            f"sysConfig.pin_circ_fan{s}        = growPrefs.getInt(\"p_c_fan{s}\", sysConfig.pin_circ_fan{s});",
            f"sysConfig.pin_circ_tacho{s}      = growPrefs.getInt(\"p_c_tac{s}\", sysConfig.pin_circ_tacho{s});",
            f"sysConfig.pin_circ_tacho_pull{s} = growPrefs.getInt(\"p_c_tac_pull{s}\", sysConfig.pin_circ_tacho_pull{s});"
        ]
    elif marker_id == "CIRCULATION_PREFS_SAVE":
        return [
            f"if (doc.containsKey(\"p_c_fan{s}\")) {{",
            f"    int v = doc[\"p_c_fan{s}\"];",
            f"    growPrefs.putInt(\"p_c_fan{s}\", v);",
            f"    sysConfig.pin_circ_fan{s} = v;",
            f"    gpio_changed = true;",
            f"}}",
            f"if (doc.containsKey(\"p_c_tac_pull{s}\")) {{",
            f"    int v = doc[\"p_c_tac_pull{s}\"];",
            f"    growPrefs.putInt(\"p_c_tac_pull{s}\", v);",
            f"    sysConfig.pin_circ_tacho_pull{s} = v;",
            f"    gpio_changed = true;",
            f"}}",
            f"if (doc.containsKey(\"p_c_tac{s}\")) {{",
            f"    int v = doc[\"p_c_tac{s}\"];",
            f"    growPrefs.putInt(\"p_c_tac{s}\", v);",
            f"    sysConfig.pin_circ_tacho{s} = v;",
            f"    gpio_changed = true;",
            f"}}"
        ]
    elif marker_id == "CIRCULATION_RECONFIGURE":
        return [f"circulation_fan{s}_reconfigure();"]
    elif marker_id == "CIRCULATION_GPIO_EXPORT":
        return [
            f"doc[\"gpios\"][\"p_c_fan{s}\"] = sysConfig.pin_circ_fan{s};",
            f"doc[\"gpios\"][\"p_c_tac{s}\"] = sysConfig.pin_circ_tacho{s};",
            f"doc[\"gpios\"][\"p_c_tac_pull{s}\"] = sysConfig.pin_circ_tacho_pull{s};"
        ]
    return []

def patch_file(filepath, target_instances):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return

    pattern = r"(//\s*PATCHER\s+BEGIN:\s*(\w+)\s*\n)(.*?)(//\s*PATCHER\s+END:\s*\2)"
    if not re.search(pattern, content, flags=re.DOTALL):
        return

    def replacer(match):
        begin_tag = match.group(1)
        marker_id = match.group(2)
        inner_content = match.group(3)
        end_tag = match.group(4)
        
        match_indent = re.match(r"^([ \t]*)", begin_tag)
        detected_indent = match_indent.group(1) if match_indent else ""
        
        # Bestehenden Inhalt säubern von alten Duplikaten, aber deine Zeilen behalten
        base_lines = []
        for line in inner_content.splitlines():
            if any(f"fan2" in line or f"tacho2" in line or f"tac2" in line for x in []): continue
            if any(f"fan3" in line or f"tacho3" in line or f"tac3" in line for x in []): continue
            if line.strip():
                base_lines.append(line)

        final_lines = base_lines
        
        for inst in target_instances:
            suffix = str(inst)
            inst_lines = get_pristine_lines(marker_id, s=suffix)
            for line in inst_lines:
                if not any(f"fan{suffix}" in bl or f"tacho{suffix}" in bl or f"tac{suffix}" in bl for bl in final_lines):
                    final_lines.append(detected_indent + line)
                
        extended = "\n".join(final_lines)
        if extended and not extended.endswith("\n"):
            extended += "\n"
            
        return f"{begin_tag}{extended}{detected_indent}{end_tag}"
        
    new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

def copy_and_rename_sources(target_instances):
    source_dir = "source_path"
    cpp_src = os.path.join(source_dir, "circulation_fan.cpp")
    h_src = os.path.join(source_dir, "circulation_fan.h")
    
    if not os.path.exists(cpp_src) or not os.path.exists(h_src):
        print(f"Error: Base source files not found in '{source_dir}/'")
        sys.exit(1)

    for inst in target_instances:
        suffix = str(inst)
        with open(cpp_src, "r", encoding="utf-8") as f: cpp_content = f.read()
        with open(h_src, "r", encoding="utf-8") as f: h_content = f.read()
        
        # Radikaler Austausch: Alle Fan- und Tacho-Variablen, ob alleinstehend oder in sysConfig, ERZWUNGEN matchen
        def repl(match):
            val = match.group(0)
            if "circulation_fan" in val: return val.replace("circulation_fan", f"circulation_fan{suffix}")
            if "CIRCULATION_FAN" in val: return val.replace("CIRCULATION_FAN", f"CIRCULATION_FAN{suffix}")
            if "pin_circ_fan" in val: return val.replace("pin_circ_fan", f"pin_circ_fan{suffix}")
            if "pin_circ_tacho_pull" in val: return val.replace("pin_circ_tacho_pull", f"pin_circ_tacho_pull{suffix}")
            if "pin_circ_tacho" in val: return val.replace("pin_circ_tacho", f"pin_circ_tacho{suffix}")
            return val
            
        # Sucht exakt nach den Schlüsselwörtern und stellt sicher, dass kein Suffix übersehen wird
        pattern = re.compile(r'(circulation_fan|CIRCULATION_FAN|pin_circ_fan|pin_circ_tacho_pull|pin_circ_tacho)[a-zA-Z0-9_]*')
        new_cpp = pattern.sub(repl, cpp_content).replace('"circulation_fan"', f'"circulation_fan{suffix}"')
        new_h = pattern.sub(repl, h_content).replace('"circulation_fan"', f'"circulation_fan{suffix}"')
        
        with open(f"circulation_fan{suffix}.cpp", "w", encoding="utf-8") as f: f.write(new_cpp)
        with open(f"circulation_fan{suffix}.h", "w", encoding="utf-8") as f: f.write(new_h)

def main():
    try:
        selection = int(input("Anzahl der Instanzen (1, 2, oder 3):\n>> ").strip())
    except ValueError:
        sys.exit(1)
        
    target_instances = []
    if selection >= 2: target_instances.append(2)
    if selection == 3: target_instances.append(3)
        
    exclude_dirs = {".git", "source_path"}
    valid_extensions = {".ino", ".cpp", ".h", ".hpp", ".c"}
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if os.path.splitext(file)[1].lower() in valid_extensions:
                patch_file(os.path.join(root, file), target_instances)
                
    copy_and_rename_sources(target_instances)
    print("Fertig.")

if __name__ == "__main__":
    main()