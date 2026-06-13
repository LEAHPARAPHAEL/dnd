import requests
import json
from pathlib import Path
import copy

def fetch_5etools_items():
    print("Fetching item database from 5e.tools...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://5e.tools/'
    }
    
    url = "https://5e.tools/data/items.json"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        raw_data = response.json()
    except Exception as e:
        print(f"Failed to fetch item data: {e}")
        return

    TYPE_MAP = {
        "G": "Wondrous Item", "W": "Weapon", "P": "Potion", "SC": "Scroll", 
        "RG": "Ring", "A": "Ammunition", "LA": "Light Armor", "MA": "Medium Armor", 
        "HA": "Heavy Armor", "S": "Shield", "ST": "Staff", "WD": "Wand", "R": "Rod"
    }

    raw_items = {}
    for item in raw_data.get("item", []):
        if "name" in item:
            i_name = item["name"].lower()
            i_source = item.get("source", "Unknown").lower()
            raw_items[(i_name, i_source)] = item

    all_items = []
    for key, item in raw_items.items():
        resolved_item = item
        if "_copy" in item:
            base_name = item["_copy"].get("name", "").lower()
            base_source = item["_copy"].get("source", "").lower()
            base_item = raw_items.get((base_name, base_source))
            if base_item:
                resolved_item = copy.deepcopy(base_item)
                for k, v in item.items():
                    if k != "_copy":
                        resolved_item[k] = v

        if "entries" not in resolved_item and "description" not in resolved_item:
            continue

        name = resolved_item["name"]
        source = resolved_item.get("source", "SRD")
        page = resolved_item.get("page", "")
        rarity = str(resolved_item.get("rarity", "common")).title()
        
        raw_type = resolved_item.get("type", "G")
        item_type = TYPE_MAP.get(raw_type, "Wondrous Item") if isinstance(raw_type, str) else "Wondrous Item"
        if resolved_item.get("wondrous"):
            item_type = "Wondrous Item"

        # Explicit parsing for detailed attunement descriptions
        req_attune = resolved_item.get("reqAttune")
        attunement = False
        attunement_details = ""
        
        if req_attune:
            attunement = True
            if isinstance(req_attune, str):
                attunement_details = req_attune
            elif isinstance(req_attune, dict):
                attunement_details = req_attune.get("text", "")

        processed_entry = {
            "name": name,
            "source": source,
            "page": page,
            "type": item_type,
            "rarity": rarity,
            "attunement": attunement,
            "attunement_details": attunement_details,
            "reqAttune": req_attune or (attunement_details if attunement_details else True),
            "entries": resolved_item.get("entries", []),
            "effect": resolved_item.get("effect", ""),
            "owners": resolved_item.get("owners", []),
            "trait": resolved_item.get("trait", []),
            "action": resolved_item.get("action", []),
            "spellcasting": resolved_item.get("spellcasting", [])
        }
        all_items.append(processed_entry)

    all_items = sorted(all_items, key=lambda x: x["name"].lower())
    
    with open("items.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, indent=4)
    print(f"Successfully scraped and synchronized {len(all_items)} items to items.json!")

if __name__ == "__main__":
    fetch_5etools_items()