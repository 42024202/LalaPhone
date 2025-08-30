import re

COLORS = [
    "черный", "белый", "синий", "красный", "зеленый", "желтый", "розовый", "фиолетовый", "серый",
    "black", "white", "blue", "red", "green", "yellow", "pink", "purple", "gray", "silver", "gold"
]

STORAGE_PATTERN = re.compile(r"(\d+\s*(ГБ|GB))", re.IGNORECASE)
BATTERY_PATTERN = re.compile(r"(\d{1,3}\s*%)")

def extract_phone_info(title: str, description: str = "") -> dict:
    if not title:
        return {"model": "", "storage": None, "battery": None, "color": None}

    parts = [p.strip() for p in title.split(",")]
    model = parts[0] if parts else ""

    text_to_parse = " ".join(parts[1:] + [description])

    storage = None
    battery = None
    color = None

    match_storage = STORAGE_PATTERN.search(text_to_parse)
    if match_storage:
        storage = match_storage.group(1)

    match_battery = BATTERY_PATTERN.search(text_to_parse)
    if match_battery:
        battery = match_battery.group(1)

    for c in COLORS:
        if c.lower() in text_to_parse.lower():
            color = c
            break

    return {
        "model": model,
        "storage": storage,
        "battery": battery,
        "color": color
    }

