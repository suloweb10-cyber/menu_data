# menu_builder/parse_pdfs.py
import re
from typing import Dict, List

# Categories to EXCLUDE (static per Susan)
EXCLUDE_KEYWORDS = [
    "BEVERAGE", "BEVERAGES", "CONDIMENT", "CONDIMENTS", "DESSERT",
    "SALAD BAR", "SANDWICH BAR", "BURGER BAR", "PASTA BAR", "WING BAR", "BURRITO BAR",
]

def _should_exclude(line: str) -> bool:
    u = line.upper()
    return any(k in u for k in EXCLUDE_KEYWORDS)

def _extract_name_recipe(fragment: str):
    """Return (Item, RecipeId or None) from a text fragment like 'Roasted Garbanzo Beans R20330'"""
    frag = fragment.strip()
    m = re.search(r'\b([RLY]\d{4,5}|[A-Z]\d{4,5})\b', frag)  # recipe codes often 'R12345' 'L02900' etc.
    rid = m.group(0) if m else None
    # remove recipe id token from name
    name = frag
    if rid:
        name = re.sub(r'\b' + re.escape(rid) + r'\b', '', frag).strip(" -–—\t ")
    # normalize spaces
    name = re.sub(r'\s{2,}', ' ', name).strip()
    return name, rid

def parse_outside_menu_text(text: str) -> List[Dict[str, str]]:
    """Extract item names and recipe IDs from Outside Menu text excluding static categories."""
    items = []
    for raw in (text or "").splitlines():
        ln = raw.strip()
        if not ln or _should_exclude(ln):
            continue
        # hard filter obvious section headers
        if re.match(r'^(MEAL|WEEK|STARCHES|HOT VEGETABLES|LEAN PROTEINS|SHORT ORDER|NON-STARCHY|STARCHY)\b', ln, re.I):
            continue
        # capture lines with names + optional codes
        if re.search(r'[A-Za-z]', ln):
            name, rid = _extract_name_recipe(ln)
            # ignore one-word generic headers like "Poultry"
            if len(name.split()) < 2 and not rid:
                continue
            items.append({"Item": name, "RecipeId": rid})
    # Deduplicate by item+rid
    seen = set()
    uniq = []
    for it in items:
        key = (it["Item"], it.get("RecipeId"))
        if key not in seen:
            uniq.append(it)
            seen.add(key)
    return uniq

def parse_production_schedule_text(text: str) -> List[Dict[str, str]]:
    """Grab the Recipe Name and code from production schedule blocks."""
    items = []
    # Recipe name with trailing recipe code like 'Roasted Red Potatoes R20480'
    for m in re.finditer(r'^\s*([A-Z][A-Za-z0-9 /\-\(\),&\']{3,}?)(?:\s+(R\d{4,5}|[A-Z]\d{4,5}))?\s*$', text or "", flags=re.M):
        name = m.group(1).strip()
        rid = (m.group(2) or "").strip() or None
        if _should_exclude(name):
            continue
        if any(x in name.upper() for x in ["INSTRUCTIONS", "REPORT", "PROJECTED HC", "ASSIGN", "DATE PRINTED"]):
            continue
        if len(name) > 2 and not name.isdigit():
            items.append({"Item": name, "RecipeId": rid})
    # Deduplicate
    seen = set()
    out = []
    for it in items:
        key = (it["Item"], it.get("RecipeId"))
        if key not in seen:
            out.append(it)
            seen.add(key)
    return out
