# menu_builder/build_sharepoint_payload.py
import pandas as pd
from typing import List, Dict, Optional
from .usda_client import lookup_nutrition

NUTR_FIELDS = ["Calories","Protein_g","Carbs_g","Fat_g","Fiber_g","Sodium_mg","Sugar_g"]

def normalize_item(name: str) -> str:
    return " ".join(name.strip().split())

def merge_items(menu_items: List[Dict[str,str]], recipe_items: List[Dict[str,str]]) -> List[Dict[str,str]]:
    """Union of items preferring production schedule (recipe_items) spellings and RecipeId."""
    # map name -> recipeId if present
    canon = []
    seen = set()
    # prefer production schedule entries first
    for d in recipe_items + menu_items:
        nm = normalize_item(d.get("Item",""))
        rid = d.get("RecipeId")
        key = (nm, rid or "")
        if nm and key not in seen:
            canon.append({"Item": nm, "RecipeId": rid})
            seen.add(key)
    return canon

def build_table(date_str: str, meal: str, items: List[Dict[str,str]], recipe_nutrition: Optional[pd.DataFrame]=None) -> pd.DataFrame:
    rows = []
    rix = None
    if recipe_nutrition is not None and not recipe_nutrition.empty and "Item" in recipe_nutrition.columns:
        rix = recipe_nutrition.set_index("Item")

    for it in items:
        item = it["Item"]
        recipe_id = it.get("RecipeId")
        rec_vals = {k: None for k in NUTR_FIELDS}
        source = "USDA"
        if rix is not None and item in rix.index:
            rec = rix.loc[item].to_dict()
            for k in NUTR_FIELDS:
                if k in rec and pd.notna(rec[k]):
                    rec_vals[k] = float(rec[k])
            source = "Recipe"

        if any(v is None for v in rec_vals.values()):
            usda = lookup_nutrition(item)
            for k in NUTR_FIELDS:
                if rec_vals[k] is None and usda.get(k) is not None:
                    rec_vals[k] = float(usda[k])
                    source = "Mixed" if source == "Recipe" else "USDA"

        rows.append({
            "MenuDate": date_str,
            "Meal": meal,
            "Item": item,
            **rec_vals,
            "Source": source,
            "RecipeId": recipe_id
        })
    return pd.DataFrame(rows, columns=["MenuDate","Meal","Item"]+NUTR_FIELDS+["Source","RecipeId"])
