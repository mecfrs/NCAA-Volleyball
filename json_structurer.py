# json_structurer.py
# Usage:
#   python json_structurer.py \
#     --in data/raw_blob.txt \
#     --out data/structured.json \
#     --source https://www.ncaa.com/stats/volleyball-women/d1/current/individual/3

import argparse, json, os
from datetime import datetime, timezone
from textwrap import dedent
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---- OpenAI client ----

ENDPOINT = os.getenv("OPENAI_BASE_URL")
API_KEY = os.getenv("OPENAI_API_KEY")
DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT")

if not ENDPOINT or not API_KEY or not DEPLOYMENT_NAME:
    raise RuntimeError("Missing required OpenAI environment variables.")

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)
# ---------------------------------------------------------

SYSTEM = dedent("""\
You are a careful data structuring assistant.
Return ONLY valid JSON (no prose). Output a JSON **array** of objects with EXACTLY these keys:

- rank        : integer (1-based)
- name        : string (player name)
- team        : string (school)
- per_set     : number (assists per set; e.g., 10.82)
- assists     : number or null (season total if present; else null)
- cl          : string or null (class year like 'Fr.', 'So.', 'Jr.', 'Sr.')
- height      : string or null (e.g., '6-1' or '5-10')

Do not invent rows. If a field is missing, set it to null. Do not include any other keys.
""")

USER_TEMPLATE = """\
SOURCE_URL: {source_url}
EXTRACTED_AT_UTC: {extracted_at}

From the following text, extract NCAA Division I women's volleyball **assists leaders**.
Focus on the main leaderboard table on this page. Convert to the schema in the system message
(rank, name, team, per_set, assists, cl, height). Return ONLY JSON.

TEXT (chunk {idx}/{total}):
{blob}
"""

def call_llm(system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0,
    )
    return resp.choices[0].message.content.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--source", dest="source_url", required=True)
    args = ap.parse_args()

    with open(args.in_path, "r", encoding="utf-8") as f:
        blob = f.read()

    # Simple chunking 
    max_chars = 12000
    chunks = [blob[i:i+max_chars] for i in range(0, len(blob), max_chars)] or [""]

    extracted_at = datetime.now(timezone.utc).isoformat()

    results = []
    for i, ch in enumerate(chunks, start=1):
        user = USER_TEMPLATE.format(
            source_url=args.source_url,
            extracted_at=extracted_at,
            idx=i, total=len(chunks),
            blob=ch,
        )
        text = call_llm(SYSTEM, user)

        # Validate JSON -> list
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                raise ValueError("Model did not return a JSON array.")
        except Exception as e:
            raise SystemExit(f"LLM did not return valid JSON: {e}\n---\n{text[:600]}")

        # Normalize types and add provenance
        normalized = []
        for row in data:
            clean = {
                "rank": row.get("rank"),
                "name": row.get("name"),
                "team": row.get("team"),
                "per_set": row.get("per_set"),
                "assists": row.get("assists"),
                "cl": row.get("cl"),
                "height": row.get("height"),
                "source_url": args.source_url,
                "extracted_at": extracted_at,
            }
           
            for k in ("rank",):
                if clean[k] is not None:
                    try: clean[k] = int(str(clean[k]).strip())
                    except: clean[k] = None
            for k in ("per_set","assists"):
                if clean[k] is not None:
                    try: clean[k] = float(str(clean[k]).replace(",", "").strip())
                    except: clean[k] = None

            normalized.append(clean)

        results.extend(normalized)

    # drop rows missing BOTH name and team
    final = [r for r in results if r.get("name") or r.get("team")]

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    with open(args.out_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.out_path} with {len(final)} rows.")

if __name__ == "__main__":
    main()
