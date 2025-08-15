#!/usr/bin/env python3
"""
fill_usda_nutrients.py

Read an Excel file with a food *Item* column and fill any missing
Fiber (g), Sodium (mg), and Sugar (g) using the USDA FoodData Central API.

Usage (Git Bash / Terminal):
    # one-time installs
    pip install pandas requests openpyxl

    # run with API key in env var
    export USDA_API_KEY="YOUR_REAL_KEY"
    python fill_usda_nutrients.py --in 21_day_menu_database_wk3_tuesday_with_usda.xlsx --out filled.xlsx

Args:
  --in / -i        Path to input .xlsx
  --out / -o       Path to output .xlsx (default: adds _filled to filename)
  --sheet / -s     Sheet name (default: first sheet)
  --item-col       Column name for item names (auto-detects: Item, Item Name)
  --delay          Seconds to wait between API calls (default: 0.1)
  --dry-run        Show what would change without writing file

Notes:
- Only fills cells that are blank/NaN for Fiber_g, Sodium_mg, Sugar_g.
- Data type priority for search: Foundation → SR Legacy → Branded → Survey (FNDDS).
- Robust to USDA errors; missing lookups are left blank rather than crashing.
"""

import argparse
import os
import sys
import time
from typing import Dict, Optional, List

import pandas as pd
import requests

FDC_BASE = "https://api.nal.usda.gov/fdc/v1"
TARGETS = {
    "Fiber_g": 1079,     # Dietary fiber (g)
    "Sodium_mg": 1093,   # Sodium (mg)
    "Sugar_g": 2000      # Total sugars (g)
}
# Priority buckets (searched in order). We query each type individually.
DATA_TYPE_PRIORITY: List[List[str]] = [
    ["Foundation", "SR Legacy"],
    ["Branded"],
    ["Survey (FNDDS)"],
]

def env_api_key() -> Optional[str]:
    key = os.getenv("USDA_API_KEY")
    if not key:
        print("[WARN] USDA_API_KEY is not set. Set it with: export USDA_API_KEY='...'", file=sys.stderr)
    return key

def search_food(query: str, api_key: str) -> Optional[Dict]:
    """Search USDA in our priority order and return the first hit (dict) or None."""
    session = requests.Session()
    for bucket in DATA_TYPE_PRIORITY:
        for dt in bucket:
            try:
                params = {
                    "api_key": api_key,
                    "query": query,
                    "pageSize": 5,
                    "dataType": [dt]  # request each data type individually
                }
                r = session.get(f"{FDC_BASE}/foods/search", params=params, timeout=30)
                if r.status_code >= 500:
                    # Server side hiccup; move on to next data type
                    print(f"[USDA] {r.status_code} searching '{query}' (dataType={dt}) - skipping")
                    continue
                r.raise_for_status()
                foods = (r.json() or {}).get("foods") or []
                if foods:
                    return foods[0]
            except requests.RequestException as e:
                print(f"[USDA] search error for '{query}' (dataType={dt}): {e}")
                continue
    return None

def fetch_food(fdc_id: int, api_key: str) -> Optional[Dict]:
    try:
        r = requests.get(f"{FDC_BASE}/food/{fdc_id}", params={"api_key": api_key}, timeout=30)
        if r.status_code >= 500:
            print(f"[USDA] {r.status_code} fetching fdcId={fdc_id} - skipping")
            return None
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"[USDA] get_food error for {fdc_id}: {e}")
        return None

def extract_targets(food_json: Dict) -> Dict[str, Optional[float]]:
    """Return just Fiber_g, Sodium_mg, Sugar_g from a USDA food JSON."""
    out = {k: None for k in TARGETS.keys()}
    if not food_json:
        return out
    by_id = {}
    for n in (food_json.get("foodNutrients") or []):
        nid = (n.get("nutrient") or {}).get("id")
        if nid is not None:
            by_id[nid] = n
    for col, nid in TARGETS.items():
        n = by_id.get(nid)
        if n is not None:
            amount = n.get("amount")
            if amount is not None:
                out[col] = float(amount)
    return out

def pick_item_col(df: pd.DataFrame, provided: Optional[str]) -> str:
    if provided and provided in df.columns:
        return provided
    # try common variants (case-insensitive)
    lower = {c.lower(): c for c in df.columns}
    for candidate in ["item", "item name", "food", "name"]:
        if candidate in lower:
            return lower[candidate]
    raise SystemExit("Could not find an item column. Use --item-col to specify it.")

def is_missing(v) -> bool:
    return (v is None) or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and v.strip() == "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", "-i", dest="infile", required=True, help="Input Excel (.xlsx)")
    ap.add_argument("--out", "-o", dest="outfile", default=None, help="Output Excel (.xlsx)")
    ap.add_argument("--sheet", "-s", dest="sheet", default=0, help="Sheet name or index (default: first)")
    ap.add_argument("--item-col", dest="item_col", default=None, help="Column name for items (auto-detects)")
    ap.add_argument("--delay", type=float, default=0.1, help="Seconds to sleep between API calls")
    ap.add_argument("--dry-run", action="store_true", help="Do not write file; just print changes")
    args = ap.parse_args()

    api_key = env_api_key()
    if not api_key:
        print("[ERROR] No USDA_API_KEY set. Aborting.", file=sys.stderr)
        sys.exit(1)

    try:
        df = pd.read_excel(args.infile, sheet_name=args.sheet)
    except Exception as e:
        print(f"[ERROR] Failed to read Excel: {e}", file=sys.stderr)
        sys.exit(1)

    item_col = pick_item_col(df, args.item_col)
    # Make sure target columns exist
    for col in TARGETS.keys():
        if col not in df.columns:
            df[col] = None

    cache: Dict[str, Dict[str, Optional[float]]] = {}
    fills = 0

    for idx, row in df.iterrows():
        name = str(row[item_col]).strip()
        if not name:
            continue

        need_cols = [c for c in TARGETS.keys() if is_missing(row.get(c))]
        if not need_cols:
            continue  # nothing to fill for this row

        key = name.lower()
        if key not in cache:
            hit = search_food(name, api_key)
            if not hit:
                cache[key] = {k: None for k in TARGETS.keys()}
            else:
                food = fetch_food(hit.get("fdcId"), api_key)
                cache[key] = extract_targets(food)
                time.sleep(args.delay)

        # Fill only missing fields
        for col in need_cols:
            val = cache[key].get(col)
            if val is not None:
                df.at[idx, col] = val
                fills += 1

    if args.dry_run:
        print(f"[DRY RUN] Would fill {fills} cells")
        return

    out = args.outfile
    if not out:
        base, ext = os.path.splitext(args.infile)
        out = f"{base}_filled{ext or '.xlsx'}"

    try:
        df.to_excel(out, index=False)
        print(f"Done. Filled {fills} cells. Wrote: {out}")
    except Exception as e:
        print(f"[ERROR] Failed to write Excel: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
