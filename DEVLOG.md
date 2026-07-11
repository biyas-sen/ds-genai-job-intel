# Development Log

Running log of engineering decisions, issues hit, and how they were resolved.
Kept intentionally raw — the goal is to document real problem-solving, not
present a sanitized "everything worked first try" narrative.

---

## Step 1: Data Collection

**Goal:** pull real DS/GenAI job postings for Bangalore from multiple sources
to avoid single-source bias in later analysis.

### Source 1: Naukri (attempted, parked)

Naukri's job search results are rendered client-side from an internal JSON
endpoint (`naukri.com/jobapi/v3/search`) rather than server-rendered HTML, so
the plan was to call that endpoint directly instead of parsing HTML.

- Initial request returned `406 Not Acceptable` — server-level rejection,
  not a code bug.
- Added browser-realistic headers (`Accept-Language`, `Referer`) to rule out
  simple header-sniffing as the cause — still `406`.
- **Decision:** rather than escalating to full browser automation (Selenium/
  Playwright with session cookies) for one extra source, parked Naukri and
  prioritized two working API-based sources instead. Anti-bot walls that
  require a real browser session are a disproportionate time cost for
  marginal additional coverage when legitimate APIs already cover the need.

### Source 2: Adzuna API (working, primary volume)

Legitimate job aggregator API, free tier (250 calls/month), good India
coverage.

- First run: `401 Unauthorized` — turned out to be a stale/incorrectly
  copied key from the developer dashboard, not a code issue. Re-copying the
  `app_id`/`app_key` pair fixed it.
- **Result:** 397 postings across 7 search terms (data scientist, GenAI
  engineer, ML engineer, applied AI engineer, LLM engineer, NLP engineer, AI
  engineer) for Bangalore.
- **Limitation found in the data itself:** Adzuna's `description` field is a
  **truncated snippet** (~500 chars, often cut mid-sentence), and it doesn't
  structure `skills` or `experience` at all — both come back `null`. This
  means skill/experience extraction from Adzuna postings will have to work
  off thin, incomplete text. Documented here so Step 2's lower extraction
  yield from this source is an expected, explained outcome — not a bug.

### Source 3: JSearch API / RapidAPI (working, richest text)

Aggregates LinkedIn, Indeed, Glassdoor, and regional boards (Shine, etc.)
through one legitimate API.

- First run: `404 Not Found`. Root cause: the documented endpoint had
  changed from `/search` to `/search-v2`, and `/search-v2` requires a
  `country` parameter that wasn't in the original request. Confirmed by
  pulling the current code snippet directly from the RapidAPI console rather
  than trusting the initially-written code.
- Second issue after fixing the URL: `AttributeError: 'str' object has no
  attribute 'get'`. Root cause: assumed response shape was `data["data"]`
  = list of job objects; actual shape is `data["data"]["jobs"]` = list of
  job objects (one level deeper than expected). Iterating the outer dict
  directly was iterating over its *keys* (strings) instead of the job list.
  Fixed by inspecting the raw JSON response directly instead of guessing
  field names from memory/docs.
- **Result:** 70 postings, but with **full, untruncated job descriptions**
  — meaningfully richer text than Adzuna's snippets, and pulled from
  higher-value sources (LinkedIn/Indeed via the aggregator).

### Outcome

~467 real Bangalore DS/GenAI postings from two independent, legitimate
sources, with source-level notes on data quality/completeness carried
forward into Step 2 (wrangling) rather than discovered painfully later.

**Engineering takeaway:** every one of the three sources failed on the first
attempt for a *different* reason (anti-bot wall, invalid credentials, API
version drift + undocumented nested response shape) — none of them were
fixed by guessing. Each was resolved by reading the actual error/response
and adjusting to match reality.

---

## Step 2: Wrangling
*(not started yet)*

---

## Step 3: Visualization
*(not started yet)*

---

## Step 4: Clustering
*(not started yet)*

---

## Step 5: GenAI Gap-Analysis Agent
*(not started yet)*

---

## Step 6: Streamlit App + Deployment
*(not started yet)*
