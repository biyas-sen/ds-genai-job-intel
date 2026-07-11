"""
Adzuna API client -- legitimate job aggregator API, free tier = 250
calls/month, decent India/Bangalore coverage.

Sign up: https://developer.adzuna.com/  (instant free app_id + app_key)
Put both in .env as ADZUNA_APP_ID and ADZUNA_APP_KEY.

Docs: https://developer.adzuna.com/docs/search
"""
import json
import time
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import SEARCH_QUERIES, LOCATION, RAW_DIR, ADZUNA_APP_ID, ADZUNA_APP_KEY

COUNTRY = "in"  # Adzuna's country code for India
BASE_URL = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search"
RESULTS_PER_PAGE = 20


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def fetch_page(keyword: str, location: str, page: int) -> dict:
    url = f"{BASE_URL}/{page}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword,
        "where": location,
        "results_per_page": RESULTS_PER_PAGE,
        "content-type": "application/json",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def scrape_query(keyword: str, location: str = LOCATION, max_pages: int = 3) -> list[dict]:
    """Adzuna's free tier is call-limited, so default to 3 pages (~60 jobs) per keyword."""
    all_jobs = []
    for page in range(1, max_pages + 1):
        try:
            data = fetch_page(keyword, location, page)
        except requests.RequestException as e:
            print(f"  [!] page {page} failed after retries: {e}")
            break

        results = data.get("results")
        if results is None:
            print(f"  [!] Unexpected response shape. Top-level keys: {list(data.keys())}")
            break
        if not results:
            break  # no more results

        for j in results:
            company = j.get("company") or {}
            loc = j.get("location") or {}
            category = j.get("category") or {}
            all_jobs.append({
                "source": "adzuna",
                "query": keyword,
                "job_id": j.get("id"),
                "title": j.get("title"),
                "company": company.get("display_name"),
                "experience": None,  # Adzuna doesn't give structured exp bands; extract from description in Step 2
                "location": loc.get("display_name"),
                "description_snippet": j.get("description"),
                "skills": None,  # also extracted from description text in Step 2
                "category": category.get("label"),
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "posted_date": j.get("created"),
                "url": j.get("redirect_url"),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

        print(f"  page {page}: +{len(results)} jobs (total {len(all_jobs)})")
        time.sleep(1)

    return all_jobs


def run():
    if not (ADZUNA_APP_ID and ADZUNA_APP_KEY):
        print("[!] ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env -- get free keys at "
              "https://developer.adzuna.com/ and retry.")
        return []

    all_results = []
    for kw in SEARCH_QUERIES:
        print(f"[adzuna] searching: '{kw}' in {LOCATION}")
        results = scrape_query(kw)
        all_results.extend(results)
        time.sleep(1.5)

    outfile = RAW_DIR / f"adzuna_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved {len(all_results)} total postings -> {outfile}")
    return all_results


def debug_single_request():
    """Run this alone if the client breaks, to inspect the raw response shape."""
    data = fetch_page("data scientist", LOCATION, 1)
    print(json.dumps(data, indent=2)[:3000])


if __name__ == "__main__":
    run()
