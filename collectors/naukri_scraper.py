"""
Naukri.com job scraper.

Naukri's search results page is rendered client-side from a JSON endpoint
that doesn't require login. This hits that endpoint directly instead of
parsing HTML (far more stable). No auth needed, but we rate-limit
ourselves to be a respectful scraper and avoid getting IP-blocked.

NOTE: Naukri can change this endpoint/response shape without notice.
If this breaks, run `debug_single_request()` at the bottom and paste the
printed JSON keys back so we can fix field names together.
"""
import json
import time
import random
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import SEARCH_QUERIES, LOCATION, RAW_DIR

SEARCH_URL = "https://www.naukri.com/jobapi/v3/search"

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "appid": "109",
    "systemid": "Naukri",
    "clientid": "d3skt0p",
    "content-type": "application/json",
    "referer": "https://www.naukri.com/data-scientist-jobs-in-bangalore",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def fetch_page(keyword: str, location: str, page: int) -> dict:
    params = {
        "noOfResults": 20,
        "urlType": "search_by_key_loc",
        "searchType": "adv",
        "keyword": keyword,
        "location": location,
        "pageNo": page,
    }
    resp = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def scrape_query(keyword: str, location: str = LOCATION, max_pages: int = 5) -> list[dict]:
    """Scrape up to max_pages of results (~20 jobs/page) for one keyword."""
    all_jobs = []
    for page in range(1, max_pages + 1):
        try:
            data = fetch_page(keyword, location, page)
        except requests.RequestException as e:
            print(f"  [!] page {page} failed after retries: {e}")
            break

        jobs = data.get("jobDetails")
        if jobs is None:
            # Response shape didn't match what we expected -- surface it
            # instead of silently returning nothing, so we can fix it fast.
            print(f"  [!] Unexpected response shape. Top-level keys: {list(data.keys())}")
            break
        if not jobs:
            break  # no more results

        for j in jobs:
            all_jobs.append({
                "source": "naukri",
                "query": keyword,
                "job_id": j.get("jobId"),
                "title": j.get("title"),
                "company": j.get("companyName"),
                "experience": j.get("footerPlaceholderLabel") or j.get("experienceText"),
                "location": j.get("placeholders", j.get("location")),
                "description_snippet": j.get("jobDescription"),
                "skills": j.get("tagsAndSkills"),
                "posted_date": j.get("footerLabel") or j.get("createdDate"),
                "url": "https://www.naukri.com/job-listings-" + str(j.get("jdURL", j.get("jobId", ""))),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

        print(f"  page {page}: +{len(jobs)} jobs (total {len(all_jobs)})")
        time.sleep(random.uniform(2, 4))  # be a polite scraper

    return all_jobs


def run():
    all_results = []
    for kw in SEARCH_QUERIES:
        print(f"[naukri] searching: '{kw}' in {LOCATION}")
        results = scrape_query(kw)
        all_results.extend(results)
        time.sleep(random.uniform(3, 6))

    outfile = RAW_DIR / f"naukri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved {len(all_results)} total postings -> {outfile}")
    return all_results


def debug_single_request():
    """Run this alone if the scraper breaks, to inspect the raw response shape."""
    data = fetch_page("data scientist", LOCATION, 1)
    print(json.dumps(data, indent=2)[:3000])


if __name__ == "__main__":
    run()
