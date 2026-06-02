import re
import copy
import json
import requests
import urllib.parse
from io import BytesIO
from pathlib import Path
from PIL import Image

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://5e.tools/'
}

def resolve_copy(child_data: dict, headers: dict = None) -> dict:
    if headers is None:
        headers = HEADERS
    if "_copy" not in child_data: 
        return child_data
    copy_info = child_data["_copy"]
    base_name = copy_info.get("name")
    base_source = copy_info.get("source", "Unknown").lower()

    url = f"https://5e.tools/data/bestiary/bestiary-{base_source}.json"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        base_monster = next((m for m in response.json().get("monster", []) if m.get("name") == base_name), None)
        if not base_monster: 
            return child_data
            
        resolved = copy.deepcopy(base_monster)
        mods = copy_info.get("_mod", {})
        
        if "*" in mods:
            star_mods = mods["*"] if isinstance(mods["*"], list) else [mods["*"]]
            for global_mod in star_mods:
                if isinstance(global_mod, dict) and global_mod.get("mode") == "replaceTxt":
                    rep, with_txt = global_mod.get("replace", ""), global_mod.get("with", "")
                    def replace_in_strings(obj):
                        if isinstance(obj, dict): return {k: replace_in_strings(v) for k, v in obj.items()}
                        elif isinstance(obj, list): return [replace_in_strings(v) for v in obj]
                        elif isinstance(obj, str): return re.sub(re.escape(rep), with_txt, obj, flags=re.IGNORECASE)
                        return obj
                    resolved = replace_in_strings(resolved)

        for mod_key, mod_val in mods.items():
            if mod_key == "*": continue
            for m_action in (mod_val if isinstance(mod_val, list) else [mod_val]):
                if isinstance(m_action, str) and m_action == "remove":
                    resolved.pop(mod_key, None)
                    continue
                mode = m_action.get("mode")
                if mode == "removeArr" and mod_key in resolved and isinstance(resolved[mod_key], list):
                    names = m_action.get("names", [])
                    names = [names] if isinstance(names, str) else names
                    resolved[mod_key] = [item for item in resolved[mod_key] if not (isinstance(item, dict) and item.get("name") in names)]
                elif mode == "appendArr":
                    items = m_action.get("items", [])
                    resolved.setdefault(mod_key, []).extend([items] if isinstance(items, dict) else items)

        for k, v in child_data.items():
            if k != "_copy": resolved[k] = v

        return resolve_copy(resolved, headers)
    except Exception: 
        return child_data

def download_monster_data(monster_meta, target_monsters_dir: Path):
    """
    Downloads raw monster data and portraits directly to the global root directory.
    Returns a tuple containing (downloaded_monster_dir_path, safe_alphanumeric_name)
    """
    name = monster_meta["name"]
    source = monster_meta.get("source", "").lower()
    if not source:
        raise ValueError("Missing valid source parameter.")

    url = f"https://5e.tools/data/bestiary/bestiary-{source}.json"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    book_data = response.json()
    monster_data = next((m for m in book_data.get("monster", []) if m.get("name") == name), None)
    if not monster_data:
        raise ValueError(f"Monster '{name}' not found inside bestiary source book.")

    monster_data = resolve_copy(monster_data)
    safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
    
    monster_dir = target_monsters_dir / safe_name
    monster_dir.mkdir(parents=True, exist_ok=True)

    with open(monster_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
        json.dump(monster_data, f, indent=4)

    safe_name_url = urllib.parse.quote(name)
    safe_source_url = urllib.parse.quote(monster_meta.get("source", "Unknown"))
    token_url = f"https://5e.tools/img/bestiary/tokens/{safe_source_url}/{safe_name_url}.webp"
    portrait_base = f"https://5e.tools/img/bestiary/{safe_source_url}/{safe_name_url}"

    try:
        t_res = requests.get(token_url, headers=HEADERS, timeout=10)
        if t_res.status_code == 200:
            img = Image.open(BytesIO(t_res.content))
            img.thumbnail((64, 64))
            img.save(monster_dir / "icon.webp", "WEBP")
    except:
        pass

    for ext in [".webp", ".png"]:
        try:
            p_res = requests.get(f"{portrait_base}{ext}", headers=HEADERS, timeout=10)
            if p_res.status_code == 200:
                with open(monster_dir / "portrait.png", "wb") as f:
                    f.write(p_res.content)
                break 
        except:
            continue

    return monster_dir, safe_name