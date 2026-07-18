from dashboard_gui.ui.common.header_capabilities import build_header_capabilities, build_header_state

def extract_capabilities(frame):
    if not isinstance(frame, dict):
        return []

    return [(cap["id"], cap["icon"]) for cap in build_header_capabilities(build_header_state(frame)) if cap["show_in_picker"] and cap["enabled"]]
