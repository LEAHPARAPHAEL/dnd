import re
import requests
import json
from pathlib import Path

# ==================== CONSTANTS & TRANSLATION MAPS ====================
SCHOOL_MAP = {
    "A": "Abjuration", "C": "Conjuration", "D": "Divination", "E": "Enchantment", 
    "I": "Illusion", "N": "Necromancy", "T": "Transmutation", "V": "Evocation", "P": "Psionic"
}
INV_SCHOOL_MAP = {v: k for k, v in SCHOOL_MAP.items()}

SIZE_MAP = {"Tiny": "T", "Small": "S", "Medium": "M", "Large": "L", "Huge": "H", "Gargantuan": "G"}
INV_SIZE_MAP = {v: k for k, v in SIZE_MAP.items()}

ALIGN_MAP = {
    "Lawful Good": ["L", "G"], "Neutral Good": ["N", "G"], "Chaotic Good": ["C", "G"],
    "Lawful Neutral": ["L", "N"], "True Neutral": ["N"], "Chaotic Neutral": ["C", "N"],
    "Lawful Evil": ["L", "E"], "Neutral Evil": ["N", "E"], "Chaotic Evil": ["C", "E"],
    "Unaligned": ["U"], "Any": ["A"]
}

ATTACK_TAGS = {
    "None": "", 
    "Melee Weapon Attack": "{@atk mw}", "Ranged Weapon Attack": "{@atk rw}", 
    "Melee/Ranged Weapon Attack": "{@atk mw,rw}", "Melee Spell Attack": "{@atk ms}", 
    "Ranged Spell Attack": "{@atk rs}", "Melee/Ranged Spell Attack": "{@atk ms,rs}", 
    "Melee Attack Roll": "{@atkr m}", "Ranged Attack Roll": "{@atkr r}", 
    "Melee/Ranged Attack Roll": "{@atkr m,r}"
}
INV_ATTACK_TAGS = {v: k for k, v in ATTACK_TAGS.items() if v}

# ==================== MATH & PARSING UTILITIES ====================
def calculate_avg(formula: str) -> int:
    if formula.isdigit(): 
        return int(formula)
    match = re.match(r'(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?', formula.replace(' ', ''))
    if match:
        n_dice, d_size, m_sign, m_val = int(match.group(1)), int(match.group(2)), match.group(3), match.group(4)
        m_val = int(m_val) if m_val else 0
        avg = int(n_dice * ((d_size + 1) / 2.0))
        return (avg + m_val) if m_sign == '+' else (avg - m_val) if m_sign == '-' else avg
    return 0

def calculate_modifier(score: int) -> str:
    mod = (score - 10) // 2
    return f"+{mod}" if mod >= 0 else str(mod)

def parse_cr(cr_str: str) -> float:
    if not cr_str or cr_str in ["—", "Unknown"]: 
        return -1.0
    if "/" in cr_str:
        num, den = cr_str.split("/")
        return float(num) / float(den)
    return float(cr_str)

def parse_complex_list(data_list) -> str:
    if not data_list: return ""
    if isinstance(data_list, str): return data_list
    out = []
    for item in data_list:
        if isinstance(item, str): 
            out.append(item)
        elif isinstance(item, dict):
            if "special" in item: 
                out.append(str(item["special"]))
            else:
                keys = [k for k in item.keys() if k not in ["note", "preNote", "cond"]]
                if keys:
                    main_val = item[keys[0]]
                    main_str = ", ".join(main_val) if isinstance(main_val, list) else str(main_val)
                    if "note" in item: main_str += f" ({item['note']})"
                    out.append(main_str)
    res = ", ".join(out)
    return res[0].upper() + res[1:] if res else ""

def get_full_ability_name(text : str) -> str:
    abilities = {
        'str' : 'Strength',
        'dex' : 'Dexterity',
        'con' : 'Constitution',
        'int' : 'Intelligence',
        'wis' : 'Wisdom',
        'cha' : 'Charisma'
    }
    return abilities.get(text, "")

def clean_5etools_text(text: str) -> str:
    # 1. Resolve scaledamage expressions to their last pipe-separated element
    text = re.sub(r'{@scaledamage ([^}]+)}', lambda m: m.group(1).split('|')[-1].strip(), text, flags=re.IGNORECASE)
    
    # 2. Handle variant rules explicitly: extract display text (3rd element) if present, otherwise the rule name (1st element)
    def parse_variantrule(m):
        parts = [p.strip() for p in m.group(1).split('|')]
        return parts[2] if len(parts) >= 3 else parts[0]
    text = re.sub(r'{@variantrule ([^}]+)}', parse_variantrule, text, flags=re.IGNORECASE)

    replacements = {
        r'{@atk mw,rw}': 'Melee or Ranged Weapon Attack:', r'{@atk ms,rs}': 'Melee or Ranged Spell Attack:',
        r'{@atkr m,r}': 'Melee or Ranged Attack Roll:', r'{@atk mw}': 'Melee Weapon Attack:', 
        r'{@atk rw}': 'Ranged Weapon Attack:', r'{@atk ms}': 'Melee Spell Attack:', 
        r'{@atk rs}': 'Ranged Spell Attack:', r'{@atkr m}': 'Melee Attack Roll:', 
        r'{@atkr r}': 'Ranged Attack Roll:', r'{@h}': 'Hit: ', r'{@hit (\d+)}': r'+\1', 
        r'{@damage (.*?)}': r'\1', r'{@dc (\d+)}': r'DC \1', r'{@condition (.*?)(?:\|.*?)?}': r'\1', 
        r'{@recharge\s*(\d*)}': lambda m: f"(Recharge {m.group(1)}-6)" if m.group(1) else "(Recharge 6)",
        r'{@actSaveFail}': "Failure :",
        r'{@actSaveSuccess}': "Success :",
        r'{@actSaveSuccessOrFail}': "Failure or Success :"
    }
    
    text = re.sub(r'{@spell ([^|}]+)[^}]*}', r'«SPELL:\1»', text, flags=re.IGNORECASE)
    for pattern, repl in replacements.items(): 
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        
    text = re.sub(r'{@actSave (\w+)}', lambda m: f"{get_full_ability_name(m.group(1).lower())} Saving Throw:", text)
    return re.sub(r'{@\w+ ([^|}]+)[^}]*}', r'\1', text)

def clean_spell_display_name(spell_name : str) -> str:
    disp_name = clean_5etools_text(spell_name)
    if ":" in disp_name: 
        disp_name = disp_name.split(":", 1)[1]
    disp_name = disp_name.replace("«", "").replace("»", "").strip().title()
                                    
    return disp_name