# decoders/binary_parser.py

# -*- coding: utf-8 -*-
import os
import json

# Die Pfade werden später vom Hauptmodul übergeben oder global ermittelt
PROFILES = ""

def set_profiles_path(path):
    global PROFILES
    PROFILES = path

def load_profile(name):
    if not name:
        return None
    fname = f"{name}.json"
    candidates = [
        os.path.join(PROFILES, "adv", fname),
        os.path.join(PROFILES, "gatt", fname),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    prof = json.load(f)
                if isinstance(prof, dict) and prof.get("fields"):
                    return prof
                print("[Decoder] Invalid profile:", p)
                return None
            except Exception:
                print("[Decoder] JSON error:", p)
                return None
    print("[Decoder] Missing profile (no fallback):", fname)
    return None

# --- LOW LEVEL BIT HELPERS ---
def _be16(b, pos):
    if pos + 1 >= len(b): return None
    v = (b[pos] << 8) | b[pos+1]
    if v in (0xFFFF, 0x0FFF): return None
    if v & 0x8000: v -= 0x10000
    return v

def _be16u(b, pos):
    if pos + 1 >= len(b): return None
    v = (b[pos] << 8) | b[pos+1]
    if v in (0xFFFF, 0x0FFF): return None
    return v

def _u8(b, pos):
    if pos >= len(b): return None
    v = b[pos] & 0xFF
    if v == 0xFF: return None
    return v

def _le16(b, pos):
    if pos + 1 >= len(b): return None
    v = b[pos] | (b[pos+1] << 8)
    if v in (0xFFFF, 0x0FFF): return None
    if v & 0x8000: v -= 0x10000
    return v

def _le16u(b, pos):
    if pos + 1 >= len(b): return None
    v = b[pos] | (b[pos+1] << 8)
    if v in (0xFFFF, 0x0FFF): return None
    return v

# --- DECODIERUNG (ROH -> WERTE) ---
def decode_with_profile(raw_hex, prof):
    if not raw_hex or set(raw_hex) == {"0"}:
        return None

    fields = prof.get("fields")
    if not isinstance(fields, dict):
        return None

    try:
        b = bytes.fromhex(raw_hex)
    except Exception:
        return None

    company_id = int(prof.get("company_id", 25))
    cid = (b[1] << 8) | b[0] if len(b) >= 2 else -1

    if cid != company_id:
        msd = bytearray(2 + len(b))
        msd[0] = company_id & 0xFF
        msd[1] = (company_id >> 8) & 0xFF
        msd[2:] = b
        b = bytes(msd)

    base_offset = int(prof.get("base_offset", 0))
    if base_offset > 0:
        pos = base_offset
    else:
        pos = 2 + int(prof.get("mac_len", 6)) + int(prof.get("skip_after_mac", 2))

    endian = (prof.get("endian") or "le").lower()
    r16  = _be16  if endian == "be" else _le16
    r16u = _be16u if endian == "be" else _le16u

    try:
        prof_name = str(prof.get("name", "")).lower()
        ti_raw = r16(b, pos + int(fields["T_i"]))
        
        if "thermopro" in prof_name:
            hi_raw = _u8(b, pos + int(fields["H_i"]))
            he_raw = _u8(b, pos + int(fields["H_e"])) if "H_e" in fields else None
        elif "lgs" in prof_name:
            hi_raw = r16(b, pos + int(fields["H_i"]))
            he_raw = r16(b, pos + int(fields["H_e"])) if "H_e" in fields else None
        else:
            hi_raw = r16u(b, pos + int(fields["H_i"]))
            he_raw = r16u(b, pos + int(fields["H_e"])) if "H_e" in fields else None

        te_raw = r16(b, pos + int(fields["T_e"])) if "T_e" in fields else None
        tl_raw = r16(b, pos + int(fields["T_l"])) if "T_l" in fields else None
        vb_raw = r16u(b, pos + int(fields["V_b"])) if "V_b" in fields else None
        fr_raw = r16u(b, pos + int(fields["F_r"])) if "F_r" in fields else None

        sT = float(prof.get("scale_temperature", 100.0))
        sH = float(prof.get("scale_humidity", 100.0))
        sB = float(prof.get("scale_battery", 100.0))
        MISSING_VAL = -256.0 * sT 

        te_final = te_raw / sT if (te_raw is not None and te_raw > MISSING_VAL) else None
        he_final = he_raw / sH if (he_raw is not None and he_raw > MISSING_VAL) else None
        tl_final = tl_raw / sT if (tl_raw is not None and tl_raw > MISSING_VAL) else None
        
        ti_final = ti_raw / sT if (ti_raw is not None and ti_raw > MISSING_VAL) else None
        hi_final = hi_raw / sH if (hi_raw is not None and hi_raw > MISSING_VAL) else None
        vb_final = vb_raw / sB if vb_raw is not None else None

    except Exception:
        return None

    return {
        "raw": raw_hex,
        "T_i": ti_final, "H_i": hi_final,
        "T_e": te_final, "H_e": he_final,
        "T_l": tl_final, "V_b": vb_final,
        "F_r": fr_raw
    }