# DS/GenAI Job Market Intelligence Tool (Bangalore)

Pipeline: scrape live DS/GenAI job postings → clean & extract structured skills →
visualize demand trends → cluster postings into real role categories → LLM agent
that runs a gap analysis between your resume and any target posting.

## Project structure
```
ds-genai-job-intel/
├── collectors/        # Step 1: pull raw job postings
├── wrangling/          # Step 2: clean text, extract structured skills
├── analysis/           # Step 3: demand charts, trend analysis
├── ml/                 # Step 4: TF-IDF/embeddings + clustering
├── genai/               # Step 5: resume-vs-JD gap analysis agent
├── app/                 # Step 6: Streamlit dashboard
├── data/raw/            # raw scraped JSON/CSV (gitignored)
└── data/processed/      # cleaned structured data (gitignored)
```

## Setup
```bash
cd ds-genai-job-intel
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in your keys
```

## Step 1 — Data collection (we are here)
Three sources, all legal and working:

1. **Naukri** — direct scrape of their public search JSON endpoint (no login needed).
2. **Adzuna API** — legitimate job aggregator, free tier 250 calls/month, good
   India coverage. Sign up (instant): https://developer.adzuna.com/
3. **JSearch API (RapidAPI)** — legally aggregates LinkedIn + Indeed + Glassdoor.
   Optional/secondary since Adzuna covers most of the need.
   Sign up: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch

Run:
```bash
python -m collectors.naukri_scraper
python -m collectors.adzuna_client
python -m collectors.jsearch_client   # optional
```
Each writes a timestamped JSON file into `data/raw/`.

Note: Naukri and Adzuna return different fields (Naukri gives a raw skills
tag list; Adzuna doesn't structure skills/experience at all, just free text).
Step 2 (wrangling) is what unifies these into one consistent schema — that's
expected, not a bug.

## Status
- [x] Repo scaffolded
- [x] Step 1: Data collection — see [DEVLOG.md](./DEVLOG.md) for the real
      debugging journey (Naukri anti-bot wall, Adzuna auth fix, JSearch
      endpoint/schema fixes). ~467 real Bangalore postings collected from
      Adzuna + JSearch (LinkedIn/Indeed/Glassdoor aggregation).
- [x] Step 2: Wrangling / skill extraction
- [x] Step 3: Visualization
- [x] Step 4: Clustering
- [x] Step 5: GenAI gap-analysis agent
- [x] Step 6: Streamlit app + deployment
