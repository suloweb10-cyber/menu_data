# menu_builder/cli.py
import argparse, os, glob, pdfplumber, pandas as pd
from .parse_pdfs import parse_outside_menu_text, parse_production_schedule_text
from .build_sharepoint_payload import build_table, merge_items

def extract_texts(pdf_dir: str, meal: str):
    # Heuristics: filenames contain _B_, _L_, _D_ and "OutsideMenu" or "Production_Report" or "Recipes"
    om = []
    pr = []
    for path in glob.glob(os.path.join(pdf_dir, f"*_{meal}_*.pdf")) + glob.glob(os.path.join(pdf_dir, f"*_{meal}_*.PDF")):
        name = os.path.basename(path).lower()
        with pdfplumber.open(path) as pdf:
            text = "\n".join([p.extract_text(x_tolerance=2, y_tolerance=2) or "" for p in pdf.pages])
        if "outsidemenu" in name:
            om.append(text)
        elif "production" in name:
            pr.append(text)
        elif "recipe" in name or "recipes" in name:
            # currently unused: some recipe PDFs have nutrition lines we could parse later
            pass
    return "\n".join(om), "\n".join(pr)

def main():
    ap = argparse.ArgumentParser(description="DFAC → SharePoint menu builder")
    ap.add_argument("--date", required=True, help="Menu date, e.g., 2025-08-19")
    ap.add_argument("--pdf-dir", required=True, help="Folder containing DFAC PDFs")
    ap.add_argument("--out", default="out", help="Output folder")
    ap.add_argument("--append-csv", default=None, help="Optional path to master CSV to append results")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    out_tables = []
    for meal, label in [("B","Breakfast"), ("L","Lunch"), ("D","Dinner")]:
        om_text, pr_text = extract_texts(args.pdf_dir, meal)
        menu_items = parse_outside_menu_text(om_text)
        prod_items = parse_production_schedule_text(pr_text)
        items = merge_items(menu_items, prod_items)
        df = build_table(args.date, label, items, recipe_nutrition=None)
        out_tables.append(df)

    final = pd.concat(out_tables, ignore_index=True)
    csv_path = os.path.join(args.out, f"menu_{args.date}.csv")
    json_path = os.path.join(args.out, f"menu_{args.date}.json")
    final.to_csv(csv_path, index=False)
    final.to_json(json_path, orient="records", indent=2)
    print(f"Wrote {csv_path}\nWrote {json_path}\nRows: {len(final)}")

    if args.append_csv:
        if os.path.exists(args.append_csv):
            master = pd.read_csv(args.append_csv)
            master = pd.concat([master, final], ignore_index=True)
        else:
            master = final
        master.to_csv(args.append_csv, index=False)
        print(f"Appended to master CSV: {args.append_csv} (total rows: {len(master)})")

if __name__ == "__main__":
    main()
