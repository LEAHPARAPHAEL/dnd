import requests
import json
from pathlib import Path

def fetch_5etools_monsters():
    print("Fetching master index from 5e.tools...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Referer': 'https://5e.tools/'
    }
    
    index_url = "https://5e.tools/data/bestiary/index.json"
    response = requests.get(index_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to fetch index. Status Code: {response.status_code}")
        return

    index_data = response.json()
    
    # ---------------------------------------------------------
    # PASS 1: Download everything and build a lookup dictionary
    # ---------------------------------------------------------
    raw_monsters = {}
    
    for source, filename in index_data.items():
        file_url = f"https://5e.tools/data/bestiary/{filename}"
        print(f"Downloading data from: {source}...")
        
        try:
            file_response = requests.get(file_url, headers=headers)
            file_data = file_response.json()
            
            if "monster" in file_data:
                for monster in file_data["monster"]:
                    if "name" in monster:
                        # Store using a tuple of (name, source) as a unique key
                        m_name = monster["name"].lower()
                        m_source = monster.get("source", "Unknown").lower()
                        raw_monsters[(m_name, m_source)] = monster
        except Exception as e:
            print(f"Error parsing {source}: {e}")

    # ---------------------------------------------------------
    # PASS 2: Extract data, resolving _copy references for missing fields
    # ---------------------------------------------------------
    all_monsters = []

    def resolve_field(monster, field_name):
        """Recursively look for a field, following _copy links if it's missing."""
        # If the copied monster overrides the field (like a stronger variant having a higher CR), use it!
        if field_name in monster:
            return monster[field_name]
        
        # Otherwise, look at the base monster it was copied from
        if "_copy" in monster:
            base_name = monster["_copy"].get("name", "").lower()
            base_source = monster["_copy"].get("source", "").lower()
            
            base_monster = raw_monsters.get((base_name, base_source))
            if base_monster:
                return resolve_field(base_monster, field_name)
                
        return None # Field truly doesn't exist

    for (m_name, m_source), monster in raw_monsters.items():
        # 1. Safely extract Challenge Rating (Checking parent if copied)
        raw_cr = resolve_field(monster, "cr")
        if raw_cr is None: raw_cr = "—"
        cr_val = str(raw_cr.get("cr", raw_cr)) if isinstance(raw_cr, dict) else str(raw_cr)

        # 2. Safely extract Type (Checking parent if copied)
        raw_type = resolve_field(monster, "type")
        if raw_type is None: raw_type = "Unknown"
        type_val = str(raw_type.get("type", raw_type)).title() if isinstance(raw_type, dict) else str(raw_type).title()

        all_monsters.append({
            "name": monster["name"],
            "type": type_val,
            "cr": cr_val,
            "source": monster.get("source", "Unknown")
        })

    # Sort alphabetically by name
    all_monsters = sorted(all_monsters, key=lambda x: x["name"].lower())
    
    output_path = Path("monsters.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_monsters, f, indent=4)
        
    print(f"\nSuccess! Saved {len(all_monsters)} monsters to {output_path.resolve()}")

if __name__ == "__main__":
    fetch_5etools_monsters()