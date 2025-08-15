# DFAC Dynamic Menu Builder (SharePoint-ready)

This toolkit parses DFAC menu PDFs (Outside Menu, Production Schedule, Recipes), 
fills missing nutrition via the USDA FoodData Central (FDC) API, and outputs a clean CSV/JSON
you can import into a SharePoint List (or publish via a web part).

## Features
- Parse Breakfast/Lunch/Dinner menu items from DFAC PDFs (Outside Menu + Production Schedule).
- Merge recipe-level nutrition if present; fetch missing nutrition from FDC API (calories, macros, fiber, sodium, sugar).
- Output a daily menu table with the exact fields SharePoint needs.
- Optional: publish records to a SharePoint List via Graph (stub provided).

## Quick Start
1. **Python 3.10+** with: `pip install pdfplumber pandas requests python-dotenv`  
2. Set env var for USDA:  
   - macOS/Linux: `export USDA_API_KEY='YOUR_KEY'`  
   - Windows (Powershell): `$env:USDA_API_KEY='YOUR_KEY'`
3. Put your PDFs in a folder (or use `sample_data/` as a pattern).  
4. Run:  
```bash
python -m menu_builder.cli --date 2025-08-19 --pdf-dir sample_data --out out
```
5. Import `out/menu_2025-08-19.csv` to your SharePoint List (“DFAC Menu”).

## SharePoint List Schema (recommended)
Create a SharePoint List named **DFAC Menu** with columns:
- **MenuDate** (Date) – required
- **Meal** (Choice: Breakfast, Lunch, Dinner) – required
- **Item** (Single line of text) – required
- **Calories** (Number)
- **Protein_g** (Number, 2 decimals)
- **Carbs_g** (Number, 2 decimals)
- **Fat_g** (Number, 2 decimals)
- **Fiber_g** (Number, 2 decimals)
- **Sodium_mg** (Number, 0 decimals)
- **Sugar_g** (Number, 2 decimals)
- **Source** (Choice: Recipe, USDA, Mixed)
- **RecipeId** (Single line of text, optional)

### Optional: JSON view formatting (adds a Date picker and group by Meal)
1. In list view, open **Format current view** → **Advanced** and paste JSON from `sharepoint_view_format.json`.
2. Use the built-in **Filter** to pick a date; items group under Breakfast/Lunch/Dinner.

## USDA API Notes
- Uses FoodData Central endpoints: search by query, then fetch details for nutrients.
- We target kcal (energy), protein, carbs, fat, fiber, sodium, and sugars. 
- Priority order: branded > SR Legacy/Foundation > Survey data (configurable).

## Safety
- **Never** commit your API keys. Use environment variables or `.env` (excluded via `.gitignore`).

## Roadmap
- Robust fuzzy matching & alias dictionary per installation.
- Direct SharePoint publish via Microsoft Graph.
- Unit tests for parser.


### Susan's Configuration
- Excludes static categories: beverages, condiments, desserts, salad bar, sandwich/burger/pasta/wing/burrito bars.
- Breakfast is a single group (no hot/cold split).
- Dinner uses its own specific menu (no roll-over).
- Recipe codes captured when present and stored in `RecipeId`.
- USDA priority search order: Foundation/SR Legacy → Branded → FNDDS.
- Use `--append-csv` to accumulate multiple cycle days into one master file.
