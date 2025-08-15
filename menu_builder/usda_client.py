# menu_builder/usda_client.py
import os
import requests
from typing import Dict, Any, Optional, List

USDA_API_KEY = os.getenv("USDA_API_KEY")  # set this in your environment
FDC_BASE = "https://api.nal.usda.gov/fdc/v1"

# Nutrient IDs (FoodData Central common IDs)
# Energy (kcal)=1008, Protein=1003, Carbs=1005, Fat=1004, Fiber=1079, Sodium=1093, Sugars=2000
NUTRIENT_IDS = [1008, 1003, 1005, 1004, 1079, 1093, 2000]

# Susan's priority: Foundation/SR Legacy first (institutional), then Branded, then FNDDS
DATA_TYPE_PRIORITY = [
    ["Foundation", "SR Legacy"],
    ["Branded"],
    ["Survey (FNDDS)"]
]

def _safe_default() -> Dict[str, Optional[float]]:
    return {k: None for k in ["Calories","Protein_g","Carbs_g","Fat_g","Fiber_g","Sodium_mg","Sugar_g"]}

def _assert_key() -> bool:
    if not USDA_API_KEY:
        # Don't raise; the caller will just get None values
        print("[USDA] Warning: USDA_API_KEY not set; returning empty nutrition")
        return False
    return True

def _search(query: str, data_types: List[str], page_size: int = 5) -> List[Dict[str, Any]]:
    if not _assert_key():
        return []
    try:
        # Query each data type individually for maximum compatibility
        for dt in data_types:
            params = {
                "api_key": USDA_API_KEY,
                "query": query,
                "pageSize": page_size,
                "dataType": [dt]
            }
            resp = requests.get(f"{FDC_BASE}/foods/search", params=params, timeout=30)
            if resp.status_code >= 500:
                # Server hiccup; try next data type
                print(f"[USDA] {resp.status_code} for search dt={dt} query='{query}'. Trying next...")
                continue
            resp.raise_for_status()
            foods = resp.json().get("foods", []) or []
            if foods:
                return foods
    except requests.RequestException as e:
        print(f"[USDA] Search error for '{query}': {e}. Continuing...")
    return []

def search_foods_priority(query: str, page_size: int = 5) -> List[Dict[str, Any]]:
    """Try search across data type buckets in priority order; return first non-empty result set."""
    for bucket in DATA_TYPE_PRIORITY:
        hits = _search(query, bucket, page_size=page_size)
        if hits:
            return hits
    return []

def get_food(fdc_id: int) -> Optional[Dict[str, Any]]:
    if not _assert_key():
        return None
    try:
        params = { "api_key": USDA_API_KEY }
        resp = requests.get(f"{FDC_BASE}/food/{fdc_id}", params=params, timeout=30)
        if resp.status_code >= 500:
            print(f"[USDA] {resp.status_code} on get_food fdcId={fdc_id}.")
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[USDA] get_food error for {fdc_id}: {e}")
        return None

def extract_nutrients(food_json: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Return kcal, protein_g, carbs_g, fat_g, fiber_g, sodium_mg, sugar_g"""
    if not food_json:
        return _safe_default()
    by_id = {}
    for n in food_json.get("foodNutrients", []) or []:
        nid = n.get("nutrient", {}).get("id") or n.get("nutrient", {}).get("number")
        by_id[nid] = n

    def val(nid):
        n = by_id.get(nid)
        if not n:
            return None
        v = n.get("amount")
        if v is None:
            return None
        return float(v)

    return {
        "Calories": val(1008),
        "Protein_g": val(1003),
        "Carbs_g": val(1005),
        "Fat_g": val(1004),
        "Fiber_g": val(1079),
        "Sodium_mg": val(1093),  # mg
        "Sugar_g": val(2000)
    }

def best_match(query: str) -> Optional[Dict[str, Any]]:
    hits = search_foods_priority(query, page_size=5)
    return hits[0] if hits else None

def lookup_nutrition(query: str) -> Dict[str, Optional[float]]:
    hit = best_match(query)
    if not hit:
        return _safe_default()
    food = get_food(hit.get("fdcId"))
    if not food:
        return _safe_default()
    return extract_nutrients(food)
