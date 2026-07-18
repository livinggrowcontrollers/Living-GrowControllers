#!/usr/bin/env python3
"""Build the selected number of circulation-fan modules from one source.

`source_path/circulation_fan.{cpp,h}` is the only editable implementation.
Every run resets all Patcher marker blocks and generated instance files before
recreating the selected firmware shape.  This makes 3 -> 1 just as safe as
1 -> 3.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


# The one normal setting for interactive use.  Valid values: 1, 2 or 3.
DEFAULT_INSTANCE_COUNT = 3
MAX_INSTANCE_COUNT = 3

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "source_path"
SOURCE_STEM = "circulation_fan"
MARKER_PATTERN = re.compile(
    r"(?P<begin>^(?P<indent>[ \t]*)//\s*PATCHER\s+BEGIN:\s*(?P<id>\w+)\s*$\n)"
    r".*?"
    # In the existing project several END markers are deliberately
    # left-aligned while their BEGIN marker is indented.  Match either form.
    r"(?P<end>^[ \t]*//\s*PATCHER\s+END:\s*(?P=id)\s*$)",
    re.MULTILINE | re.DOTALL,
)


def suffix(instance: int) -> str:
    return "" if instance == 1 else str(instance)


def fan_name(instance: int) -> str:
    return f"circulation_fan{suffix(instance)}"


def marker_lines(marker_id: str, count: int) -> list[str]:
    """Return the complete, canonical content of one Patcher block."""
    instances = range(1, count + 1)

    if marker_id == "CIRCULATION_INIT":
        lines: list[str] = []
        for i in instances:
            s = suffix(i)
            lines.extend([
                f"if (sysConfig.pin_circ_fan{s} == -1 || sysConfig.pin_circ_tacho{s} == -1) {{",
                f'    Serial.println("Circulation Fan{i} disabled (sysConfig). ");',
                "} else {",
                f"    {fan_name(i)}_init(sysConfig.pin_circ_fan{s}, sysConfig.pin_circ_tacho{s});",
                "}",
            ])
        return lines

    if marker_id == "CIRCULATION_UPDATE":
        return [f"{fan_name(i)}_update();" for i in instances]

    if marker_id == "CIRCULATION_INCLUDE":
        return [f'#include "{fan_name(i)}.h"' for i in instances]

    if marker_id == "CIRCULATION_GET_STATUS":
        return [f"{fan_name(i)}_get_status(obj);" for i in instances]

    if marker_id == "CIRCULATION_JSON_UPDATE":
        return [f"{fan_name(i)}_process_json(obj);" for i in instances]

    if marker_id == "CIRCULATION_CONFIG":
        lines = []
        for i in instances:
            s = suffix(i)
            lines.extend((f"int pin_circ_fan{s};", f"int pin_circ_tacho{s};", f"int pin_circ_tacho{s}_pull;"))
        return lines

    if marker_id == "CIRCULATION_CONFIG_DEFAULTS":
        lines = []
        for i in instances:
            s = suffix(i)
            # Extra modules must never claim the base fan's GPIOs by default.
            pwm, tacho = (45, 2) if i == 1 else (-1, -1)
            lines.extend((
                f"/* pin_circ_fan{s} */ {pwm},",
                f"/* pin_circ_tacho{s} */ {tacho},",
                f"/* pin_circ_tacho{s}_pull */ 1,",
            ))
        return lines

    if marker_id == "CIRCULATION_PREFS_LOAD":
        return [
            line
            for i in instances
            for s in (suffix(i),)
            for line in (
                f'sysConfig.pin_circ_fan{s} = growPrefs.getInt("p_c_fan{s}", sysConfig.pin_circ_fan{s});',
                f'sysConfig.pin_circ_tacho{s} = growPrefs.getInt("p_c_tac{s}", sysConfig.pin_circ_tacho{s});',
                f'sysConfig.pin_circ_tacho{s}_pull = growPrefs.getInt("p_c_tac{s}_pull", sysConfig.pin_circ_tacho{s}_pull);',
            )
        ]

    if marker_id == "CIRCULATION_PREFS_SAVE":
        lines = []
        for i in instances:
            s = suffix(i)
            for json_key, field in ((f"p_c_fan{s}", f"pin_circ_fan{s}"), (f"p_c_tac{s}_pull", f"pin_circ_tacho{s}_pull"), (f"p_c_tac{s}", f"pin_circ_tacho{s}")):
                lines.extend((
                    f'if (doc.containsKey("{json_key}")) {{',
                    f'    int v = doc["{json_key}"];',
                    f'    growPrefs.putInt("{json_key}", v);',
                    f"    sysConfig.{field} = v;",
                    "    gpio_changed = true;",
                    "}",
                ))
        return lines

    if marker_id == "CIRCULATION_RECONFIGURE":
        return [f"{fan_name(i)}_reconfigure();" for i in instances]

    if marker_id == "CIRCULATION_GPIO_EXPORT":
        return [
            line
            for i in instances
            for s in (suffix(i),)
            for line in (
                f'doc["gpios"]["p_c_fan{s}"] = sysConfig.pin_circ_fan{s};',
                f'doc["gpios"]["p_c_tac{s}"] = sysConfig.pin_circ_tacho{s};',
                f'doc["gpios"]["p_c_tac{s}_pull"] = sysConfig.pin_circ_tacho{s}_pull;',
            )
        ]
    return []


def reset_marker_blocks(path: Path, count: int) -> bool:
    content = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        lines = marker_lines(match.group("id"), count)
        indent = match.group("indent")
        body = "".join(f"{indent}{line}\n" for line in lines)
        return f"{match.group('begin')}{body}{match.group('end')}"

    updated, changes = MARKER_PATTERN.subn(replace, content)
    if changes:
        path.write_text(updated, encoding="utf-8")
    return bool(changes)


def reset_all_marker_blocks(count: int) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or SOURCE_DIR in path.parents:
            continue
        if path.suffix.lower() in {".ino", ".cpp", ".h", ".hpp", ".c"}:
            reset_marker_blocks(path, count)


def remove_generated_instances() -> None:
    """Remove only files that this script owns; the base source is untouched."""
    for instance in range(2, MAX_INSTANCE_COUNT + 1):
        for extension in (".cpp", ".h"):
            generated = ROOT / f"{fan_name(instance)}{extension}"
            if generated.exists():
                generated.unlink()


def instance_source(text: str, instance: int) -> str:
    """Rename every instance-scoped C++ symbol and protocol key deterministically."""
    if instance == 1:
        return text

    s = suffix(instance)
    replacements = (
        # Specific names first; generic prefixes follow afterwards.
        (r"\brev_circfan\b", f"rev_circfan{s}"),
        (r"\bcount_circ_fan_pulse\b", f"count_circ_fan{s}_pulse"),
        (r"\bcurrent_circ_fan_pin\b", f"current_circ_fan{s}_pin"),
        (r"\bcurrent_circ_tacho_pin\b", f"current_circ_tacho{s}_pin"),
        (r"\b_tacho_pin\b", f"_tacho{s}_pin"),
        (r"\bCIRC_FAN\b", f"CIRC_FAN{s}"),
        (r"\bCIRCULATION_FAN", f"CIRCULATION_FAN{s}"),
        # Underscores zählen bei \b als Wortzeichen.  Diese Regeln erfassen
        # deshalb auch `_circulation_fan_pin` und `current_circulation_fan_*`.
        (r"(?<![A-Za-z0-9])circulation_fan", f"circulation_fan{s}"),
        (r"(?<![A-Za-z0-9])pin_circ_fan", f"pin_circ_fan{s}"),
        (r"(?<![A-Za-z0-9])pin_circ_tacho", f"pin_circ_tacho{s}"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def generate_sources(count: int) -> None:
    source_cpp = (SOURCE_DIR / f"{SOURCE_STEM}.cpp").read_text(encoding="utf-8")
    source_h = (SOURCE_DIR / f"{SOURCE_STEM}.h").read_text(encoding="utf-8")
    for instance in range(1, count + 1):
        stem = fan_name(instance)
        (ROOT / f"{stem}.cpp").write_text(instance_source(source_cpp, instance), encoding="utf-8")
        (ROOT / f"{stem}.h").write_text(instance_source(source_h, instance), encoding="utf-8")


def build(count: int) -> None:
    if not 1 <= count <= MAX_INSTANCE_COUNT:
        raise ValueError(f"Instanzanzahl muss zwischen 1 und {MAX_INSTANCE_COUNT} liegen.")
    if not (SOURCE_DIR / f"{SOURCE_STEM}.cpp").is_file() or not (SOURCE_DIR / f"{SOURCE_STEM}.h").is_file():
        raise FileNotFoundError("Die generische Quelle unter source_path fehlt.")

    remove_generated_instances()
    generate_sources(count)
    reset_all_marker_blocks(count)
    print(f"Circulation-Fan-Firmware für {count} Instanz(en) erzeugt.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Erzeugt 1 bis 3 Circulation-Fan-Instanzen.")
    parser.add_argument("--instances", "-n", type=int, default=DEFAULT_INSTANCE_COUNT, help="Anzahl der Instanzen (1-3)")
    args = parser.parse_args()
    try:
        build(args.instances)
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
