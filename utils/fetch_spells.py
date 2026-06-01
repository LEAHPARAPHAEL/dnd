import requests
import json
from pathlib import Path
import copy
import re

def fetch_5etools_spells():
    print("Fetching spell index from 5e.tools...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://5e.tools/'
    }
    
    index_url = "https://5e.tools/data/spells/index.json"
    response = requests.get(index_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to fetch index. Status Code: {response.status_code}")
        return

    index_data = response.json()
    raw_spells = {}
    
    # 1. Download all spells
    for source, filename in index_data.items():
        file_url = f"https://5e.tools/data/spells/{filename}"
        print(f"Downloading data from: {source}...")
        
        try:
            file_response = requests.get(file_url, headers=headers)
            file_data = file_response.json()
            
            if "spell" in file_data:
                for spell in file_data["spell"]:
                    if "name" in spell:
                        s_name = spell["name"].lower()
                        s_source = spell.get("source", "Unknown").lower()
                        raw_spells[(s_name, s_source)] = spell
        except Exception as e:
            print(f"Error parsing {source}: {e}")

    # 2. Function to resolve _copy fields (e.g. variants from different books)
    def resolve_copy(spell):
        if "_copy" not in spell:
            return spell
            
        copy_info = spell["_copy"]
        base_name = copy_info.get("name", "").lower()
        base_source = copy_info.get("source", "Unknown").lower()
        
        base_spell = raw_spells.get((base_name, base_source))
        if not base_spell:
            return spell
            
        resolved = copy.deepcopy(base_spell)
        
        # Merge top-level overrides
        for k, v in spell.items():
            if k != "_copy":
                resolved[k] = v
        return resolved

    print("Resolving variants...")
    all_spells = []
    for key, spell in raw_spells.items():
        all_spells.append(resolve_copy(spell))

    # Sort alphabetically
    all_spells = sorted(all_spells, key=lambda x: x["name"].lower())
    
    output_path = Path("spells.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_spells, f, indent=4)
        
    print(f"\nSuccess! Saved {len(all_spells)} spells to {output_path.resolve()}")

if __name__ == "__main__":
    fetch_5etools_spells()