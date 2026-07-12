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
import os
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


def strip_company_boilerplate(rows: list[dict], min_group_size: int = 2, min_prefix_len: int = 60) -> tuple[list[dict], dict]:
    """
    Companies often post multiple listings that all open with an identical
    'About Us' paragraph (e.g. eBay's "we're more than a global ecommerce
    leader..." intro, or platform-injected text like myGwork's diversity
    statement). That shared text is pure noise for skill extraction and
    clustering -- it's the same string appearing across otherwise-unrelated
    postings, which distorts TF-IDF and can even accidentally match skill
    keywords. This finds the longest common prefix per company (only when
    >=2 postings share one) and strips it out. Generic by design: catches
    any company's repeated boilerplate, not just ones we've manually seen.
    """
    from collections import defaultdict
    by_company = defaultdict(list)
    for i, row in enumerate(rows):
        by_company[row["company"]].append(i)

    stripped_log = {}
    for company, idxs in by_company.items():
        if len(idxs) < min_group_size or not company:
            continue
        texts = [rows[i]["description_clean"] for i in idxs]
        prefix = os.path.commonprefix(texts)
        if len(prefix) >= min_prefix_len:
            # trim to the last full word so we don't cut mid-word
            prefix = prefix[:prefix.rfind(" ")] if " " in prefix else prefix
            for i in idxs:
                rows[i]["description_clean"] = rows[i]["description_clean"][len(prefix):].strip()
            stripped_log[company] = (len(idxs), prefix[:80])

    return rows, stripped_log


def build_dataframe(raw_jobs: list[dict]) -> pd.DataFrame:
    # Pass 1: clean text only, no skill extraction yet -- we need every
    # posting's cleaned description before we can detect shared company
    # boilerplate across postings.
    rows = []
    for j in raw_jobs:
        title = j.get("title") or ""
        raw_desc = j.get("description_snippet") or ""
        desc_clean = clean_text(raw_desc)
        rows.append({
            "source": j.get("source"),
            "search_query": j.get("query"),
            "job_id": j.get("job_id"),
            "title": title,
            "company": j.get("company"),
            "location": j.get("location"),
            "description_clean": desc_clean,
            "description_is_truncated": truncate_flag(raw_desc),
            "posted_date": j.get("posted_date"),
            "url": j.get("url"),
        })

    # Pass 2: strip any company-level boilerplate shared across >=2 postings
    rows, stripped_log = strip_company_boilerplate(rows)
    if stripped_log:
        print(f"\n  Stripped shared company boilerplate from {len(stripped_log)} companies:")
        for company, (count, sample) in stripped_log.items():
            print(f"    - {company} ({count} postings): \"{sample}...\"")

    # Pass 3: now extract skills/experience from the cleaned (and
    # boilerplate-stripped) text
    for row in rows:
        search_text = f"{row['title']} {row['description_clean']}"
        row["skills_extracted"] = extract_skills(search_text)
        row["skill_count"] = len(row["skills_extracted"])
        exp_min, exp_max = extract_experience(search_text)
        row["exp_min_years"] = exp_min
        row["exp_max_years"] = exp_max

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
