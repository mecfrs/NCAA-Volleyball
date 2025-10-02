# loader.py (diagnostic)
# Usage: python loader.py --in data/structured.json --table wvb_individual_assists

import argparse, json, os, sys
from datetime import datetime, timezone
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

TABLE_COLUMNS = {
    "rank","name","team","per_set","assists","cl","height",
    "source_url","extracted_at","updated_at"
}

def die(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="data/structured.json")
    ap.add_argument("--table", required=True)
    args = ap.parse_args()

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        die("Set SUPABASE_URL and SUPABASE_ANON_KEY in your .env")

    # read JSON
    with open(args.in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) or not data:
        die(f"{args.in_path} is empty or not a JSON array.")

    df = pd.DataFrame(data)
    print("[INFO] Raw JSON rows:", len(df))
    print("[INFO] Raw columns:", list(df.columns))

    #keep only expected columns
    cols_to_send = [c for c in df.columns if c in TABLE_COLUMNS]
    df = df[cols_to_send]
    print("[INFO] After column filter rows/cols:", df.shape)
    print("[INFO] Columns to send:", list(df.columns))

    # convert numerics
    for c in ["rank", "per_set", "assists"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    #drop rows missing required fields 
    before = len(df)
    required = [c for c in ["rank", "name"] if c in df.columns]
    if required:
        df = df.dropna(subset=required).copy()
    print(f"[INFO] Dropped {before - len(df)} rows missing {required}")

    if len(df) == 0:
        die("All rows were dropped after cleaning (missing rank/name?). Open data/structured.json to inspect.")

    # timestamps
    df["updated_at"] = datetime.now(timezone.utc).isoformat()

    rows = df.to_dict(orient="records")

    #connect and upsert
    print("[INFO] Connecting to Supabase:", SUPABASE_URL)
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    try:
        res = client.table(args.table).upsert(rows, on_conflict="name,team").execute()
        # Some drivers return [] on success; we’ll follow-up with a count.
        n = len(res.data) if res.data else 0
        print(f"[INFO] Upsert returned {n} rows in response (may be empty on some versions).")
    except Exception as e:
        # Print full error content
        print("[EXCEPTION] Upsert failed:", repr(e))
        raise

    #  verify by selecting a count
    try:
        verify = client.table(args.table).select("id", count="exact").execute()
        total = verify.count if hasattr(verify, "count") else (len(verify.data) if verify.data else 0)
        print(f"[INFO] Table '{args.table}' total rows now: {total}")
    except Exception as e:
        print("[WARN] Post-insert count failed:", repr(e))

if __name__ == "__main__":
    main()
