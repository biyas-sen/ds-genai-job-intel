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

**Goal:** merge both raw sources into one clean dataset, extract structured
skills and experience bands from free text.

- Loaded 467 raw postings (397 Adzuna + 70 JSearch), deduped near-identical
  cross-posted listings down to 407 unique postings (matched on
  company + title).
- Built a ~80-term skills taxonomy across 7 categories (languages, core ML,
  GenAI/LLM-specific, MLOps, cloud, data engineering, BI) and matched it
  against combined title + description text via regex.
- Extracted experience bands ("3-5 years" style patterns) from free text
  since neither source provides this as a structured field — only
  successful for ~12.5% of postings, since most listings don't state an
  explicit numeric band in the visible text.

### Bug found via manual verification: substring false positives

Initial run put **Scala at #6 overall (75 postings)** and Excel in the top
15 — both implausibly high for the current Bangalore DS/GenAI market.
Manually inspected the actual matched text spans instead of trusting the
aggregate number, and found the "Scala" pattern was a naive substring match
matching inside the unrelated word **"scal-able"** ("scalable AI platform",
"scalable production systems" — extremely common phrasing, nothing to do
with the Scala language). Same risk for "Excel" matching the verb "excel"
("excel in a fast-paced environment").

**Fix:** added regex word boundaries (`\bscala\b`) so patterns only match
whole words, not substrings. Re-ran the pipeline — Scala dropped out of the
top 15 entirely (real finding: Scala is essentially absent from Bangalore
DS/GenAI postings right now, not a data quality gap).

Also manually spot-checked "Agents" (88 matches) given it uses a looser
lookahead pattern with similar false-positive risk — confirmed via the same
method that every sampled match was genuine agentic-AI language, not a
coincidental match. Kept as-is.

**Takeaway:** every extracted skill/number in this project gets spot-checked
against the actual matched text before being trusted, not just eyeballed as
a plausible-looking count. Caught one real bug this way; confirmed one
number that looked suspicious but was actually correct.

### Result

407 clean postings, `data/processed/jobs_clean.csv` + `.json`, each with:
source, title, company, location, cleaned description, extracted skills
list, skill count, experience band (where extractable), posting date, URL.

Top skills (post-fix): Machine Learning (178), LLM (107), Generative AI
(102), Python (95), Agents (88), RAG (64), NLP (49), Azure (49), Prompt
Engineering (42), AWS (42).

---

---

## Step 3: Visualization

**Goal:** turn the 407 cleaned postings into charts answering: which skills
dominate, LangChain vs LlamaIndex, RAG vs fine-tuning, Python vs SQL, and
(eventually) demand trend over time.

Built 9 interactive Plotly charts (top skills, category breakdown, source
breakdown, experience distribution, and 4 head-to-head skill comparisons),
saved as standalone HTML.

**Headline numbers:** Machine Learning (178), LLM (107), Generative AI
(102), Python (95), Agents (88) lead overall. RAG outpaces Fine-tuning
64-to-28. LangChain outpaces LlamaIndex 31-to-11.

### Caveat found via verification: SQL undercount is a data artifact, not a real signal

SQL showed up at only 20 mentions (~5% of postings) — surprisingly low for
data science roles, where SQL is normally near-universal. Rather than plot
this as-is, checked it: of the 78 postings that mention Python but not SQL,
**57 (73%) have a truncated description** (mostly Adzuna snippets cut off
mid-sentence, per the `description_is_truncated` flag from Step 2). This
strongly suggests SQL is being under-counted because the truncated text
never reaches the skills section of the posting, not because Bangalore
DS/GenAI roles genuinely don't want SQL.

**Handling:** documenting this as a known data limitation rather than
treating the number as ground truth. Any future re-run that adds a source
with fuller description text (or re-scrapes Adzuna via their full-listing
page instead of the search snippet) should shrink this gap. Not fixing it
by inflating the number artificially — an honest caveat is better than a
falsely confident chart.

### On month-to-month trend

Not built yet — this snapshot is a single scrape (2026-07-11). The
collectors already save timestamped raw files, so re-running them
periodically over the coming weeks/months and re-running this script will
produce a real trend line without any code changes. Documenting this
limitation now rather than faking a trend chart from one data point.

### Result

9 chart HTML files in `data/processed/charts/`. `.gitignore` originally
excluded all of `data/processed/`, which would have hidden the charts from
the GitHub repo — added an explicit exception so charts are trackable while
raw/processed data files stay excluded.

---

---

## Step 4: Clustering
*(not started yet)*

---

## Step 5: GenAI Gap-Analysis Agent
*(not started yet)*

---

## Step 6: Streamlit App + Deployment
*(not started yet)*
