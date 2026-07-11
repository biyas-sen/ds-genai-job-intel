"""
JSearch API client (RapidAPI) -- legally aggregates LinkedIn, Indeed,
Glassdoor and more. Free tier = 200 requests/month, ~10 results/request,
so budget your calls (this script uses ~1 call per query = 7 calls per run).

Sign up: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
Then put your key in .env as RAPIDAPI_KEY.
"""
import json
import time
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import SEARCH_QUERIES, LOCATION, RAW_DIR, RAPIDAPI_KEY

API_URL = "https://jsearch.p.rapidapi.com/search-v2"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def fetch(query: str, page: int = 1) -> dict:
    params = {
        "query": f"{query} in {LOCATION}",
        "page": page,
        "num_pages": 1,
	"country": "in",
        "date_posted": "month",
    }
    resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def scrape_query(keyword: str) -> list[dict]:
    data = fetch(keyword)
    jobs = data.get("data", {}).get("jobs", [])
    out = []
    for j in jobs:
        out.append({
            "source": j.get("job_publisher", "jsearch"),
            "query": keyword,
            "job_id": j.get("job_id"),
            "title": j.get("job_title"),
            "company": j.get("employer_name"),
            "experience": j.get("job_required_experience", {}).get("required_experience_in_months") if j.get("job_required_experience") else None,
            "location": j.get("job_city") or j.get("job_country"),
            "description_snippet": j.get("job_description"),
            "skills": j.get("job_required_skills"),
            "posted_date": j.get("job_posted_at_datetime_utc"),
            "url": j.get("job_apply_link"),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


def run():
    if not RAPIDAPI_KEY:
        print("[!] RAPIDAPI_KEY not set in .env -- get one at "
              "https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch and retry.")
        return []

    all_results = []
    for kw in SEARCH_QUERIES:
        print(f"[jsearch] searching: '{kw}' in {LOCATION}")
        try:
            results = scrape_query(kw)
            print(f"  +{len(results)} jobs")
            all_results.extend(results)
        except requests.RequestException as e:
            print(f"  [!] failed: {e}")
        time.sleep(1.5)  # stay well under free-tier rate limits

    outfile = RAW_DIR / f"jsearch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved {len(all_results)} total postings -> {outfile}")
    return all_results

def debug_single_request():
	"""Run this alone to inspect the raw response shape."""
	data = fetch("data scientist")
	print(json.dumps(data, indent=2)[:3000])

if __name__ == "__main__":
    run()
