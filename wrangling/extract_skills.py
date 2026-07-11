"""
Step 2: Wrangling.

Loads every raw JSON file in data/raw/ (from all collectors), merges them
into one consistent schema, cleans the description text, extracts
structured skills via keyword matching against SKILLS_TAXONOMY, and
extracts experience bands via regex. Saves one clean dataset to
data/processed/.

Run:
    python -m wrangling.extract_skills
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from config import RAW_DIR, PROCESSED_DIR
from wrangling.clean_text import clean_text, truncate_flag
from wrangling.skills_taxonomy import FLAT_TAXONOMY, SKILL_TO_CATEGORY

# Pre-compile skill patterns once for speed
COMPILED_SKILLS = {
    name: [re.compile(p, re.IGNORECASE) for p in patterns]
    for name, patterns in FLAT_TAXONOMY.items()
}

EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\s*-\s*(\d+)\s*\+?\s*years?", re.IGNORECASE),      # "3-5 years"
    re.compile(r"(\d+)\s*to\s*(\d+)\s*years?", re.IGNORECASE),           # "3 to 5 years"
    re.compile(r"(\d+)\s*\+\s*years?", re.IGNORECASE),                    # "3+ years"
    re.compile(r"minimum\s*(?:of\s*)?(\d+)\s*years?", re.IGNORECASE),    # "minimum 3 years"
]


def load_raw_files() -> list[dict]:
    """Load and tag every JSON file sitting in data/raw/."""
    all_jobs = []
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        print(f"[!] No raw JSON files found in {RAW_DIR} -- run the collectors first.")
        return []

    for f in files:
        with open(f) as fh:
            jobs = json.load(fh)
        print(f"  loaded {len(jobs)} from {f.name}")
        all_jobs.extend(jobs)
    return all_jobs


def extract_skills(text: str) -> list[str]:
    """Return sorted list of canonical skill names found in the text."""
    found = []
    for name, patterns in COMPILED_SKILLS.items():
        if any(p.search(text) for p in patterns):
            found.append(name)
    return sorted(found)


def extract_experience(text: str) -> tuple[int | None, int | None]:
    """Return (min_years, max_years) parsed from free text, or (None, None)."""
    if not text:
        return None, None
    for pattern in EXPERIENCE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                return int(groups[0]), int(groups[1])
            else:
                return int(groups[0]), None
    return None, None


def build_dataframe(raw_jobs: list[dict]) -> pd.DataFrame:
    rows = []
    for j in raw_jobs:
        title = j.get("title") or ""
        raw_desc = j.get("description_snippet") or ""
        desc_clean = clean_text(raw_desc)

        # Search title + description together -- titles often carry strong
        # signal ("GenAI Engineer", "LLM") that short snippets might miss.
        search_text = f"{title} {desc_clean}"

        skills_found = extract_skills(search_text)

        # Prefer structured experience field if a source ever provides one;
        # otherwise fall back to regex extraction from text.
        exp_min, exp_max = extract_experience(search_text)

        rows.append({
            "source": j.get("source"),
            "search_query": j.get("query"),
            "job_id": j.get("job_id"),
            "title": title,
            "company": j.get("company"),
            "location": j.get("location"),
            "description_clean": desc_clean,
            "description_is_truncated": truncate_flag(raw_desc),
            "skills_extracted": skills_found,
            "skill_count": len(skills_found),
            "exp_min_years": exp_min,
            "exp_max_years": exp_max,
            "posted_date": j.get("posted_date"),
            "url": j.get("url"),
        })

    df = pd.DataFrame(rows)

    # Dedupe: same company + very similar title can appear across sources
    # (e.g. same job cross-posted). Keep the version with richer text.
    df["_desc_len"] = df["description_clean"].str.len()
    df = df.sort_values("_desc_len", ascending=False)
    df = df.drop_duplicates(subset=["company", "title"], keep="first")
    df = df.drop(columns="_desc_len").reset_index(drop=True)

    return df


def run():
    print("Loading raw files...")
    raw_jobs = load_raw_files()
    if not raw_jobs:
        return None

    print(f"\nTotal raw postings loaded: {len(raw_jobs)}")
    print("Cleaning + extracting skills...")
    df = build_dataframe(raw_jobs)
    print(f"After deduping near-identical postings: {len(df)} rows")

    # Save as CSV (skills_extracted flattened to a comma-joined string for
    # spreadsheet-friendliness) and as JSON (keeps skills as a real list,
    # easier for later steps to consume directly).
    csv_path = PROCESSED_DIR / "jobs_clean.csv"
    json_path = PROCESSED_DIR / "jobs_clean.json"

    df_csv = df.copy()
    df_csv["skills_extracted"] = df_csv["skills_extracted"].apply(lambda s: ", ".join(s))
    df_csv.to_csv(csv_path, index=False)

    df.to_json(json_path, orient="records", indent=2)

    print(f"\nSaved -> {csv_path}")
    print(f"Saved -> {json_path}")

    # Quick sanity summary printed to terminal
    print("\n--- Quick summary ---")
    print(f"Postings with zero skills matched: {(df['skill_count'] == 0).sum()} "
          f"({(df['skill_count'] == 0).mean():.1%})")
    print(f"Postings with experience band extracted: {df['exp_min_years'].notna().sum()} "
          f"({df['exp_min_years'].notna().mean():.1%})")
    print(f"Average skills matched per posting: {df['skill_count'].mean():.1f}")
    print("\nTop 15 skills overall:")
    all_skills = [s for skills in df["skills_extracted"] for s in skills]
    print(pd.Series(all_skills).value_counts().head(15))

    return df


if __name__ == "__main__":
    run()
