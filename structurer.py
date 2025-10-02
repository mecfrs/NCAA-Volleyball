# structurer.py
import os, json, uuid, time
from pathlib import Path
from openai import OpenAI

# ENV: OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_MODEL
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://cdong1--azure-proxy-web-app.modal.run"),
    api_key=os.getenv("OPENAI_API_KEY", "supersecretkey"),
)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

def parse_as_list(content: str):
    """
    Robustly turn model content into a list of dicts.
    Accepts:
      - {"items": [...]}
      - {"data": [...]}
      - [...]
      - text with a single JSON array inside code fences
    """
    try:
        data = json.loads(content)
    except Exception:
        # Try to salvage bracketed array
        start, end = content.find("["), content.rfind("]")
        if start == -1 or end == -1:
            raise ValueError("Model did not return JSON. First 400 chars:\n" + content[:400])
        return json.loads(content[start:end+1])

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Preferred 'items'
        if isinstance(data.get("items"), list):
            return data["items"]
        # Otherwise first list value under any key
        for v in data.values():
            if isinstance(v, list):
                return v
        raise ValueError("Parsed JSON is an object without a list payload. Keys: " + ", ".join(map(str, data.keys())))

    raise ValueError("Parsed JSON is neither list nor object.")

def main():
    blob = json.loads(Path("data/raw_blob.txt").read_text())
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    schema = {
        "id": "string",
        "symbol": "S/RES/#### (2025)",
        "date": "YYYY-MM-DD",
        "title": "string",
        "region_or_country": "string",
        "topics": ["strings"],
        "undocs_url": "string",
        "extracted_at": "ISO8601"
    }

    messages = [
        {"role": "system", "content": "Return strictly JSON. Format EXACTLY as: {\"items\": [ ... ]}. No prose."},
        {"role": "user", "content":
            "You will receive JSON with an 'entries' array of UN Security Council 2025 resolutions. "
            f"For each entry, produce an object with this schema:\n{json.dumps(schema)}\n"
            "- Convert date_text to YYYY-MM-DD.\n"
            "- id: use normalized symbol if available (e.g., S-RES-2792-2025), otherwise UUID.\n"
            "- topics: 3–7 concise keywords.\n"
            "- region_or_country: infer from title.\n"
            "Output EXACTLY: {\"items\": [objects]}."
            f"\n\nINPUT:\n{json.dumps(blob)}"
        }
    ]

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.1,
        response_format={"type": "json_object"}
    )

    content = resp.choices[0].message.content
    items = parse_as_list(content)

    # Normalize & guard types
    out = []
    for rec in items:
        if not isinstance(rec, dict):
            continue  # skip stray strings
        rec.setdefault("extracted_at", blob.get("extracted_at", now))
        if not rec.get("id"):
            base = rec.get("symbol") or str(uuid.uuid4())
            rec["id"] = (
                base.replace("/", "-")
                    .replace(" ", "-")
                    .replace("(", "")
                    .replace(")", "")
            )
        out.append(rec)

    Path("data/structured.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {len(out)} records to data/structured.json")

if __name__ == "__main__":
    main()
