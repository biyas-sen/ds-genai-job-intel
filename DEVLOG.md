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

### Result

9 chart HTML files in `data/processed/charts/`. `.gitignore` originally
excluded all of `data/processed/`, which would have hidden the charts from
the GitHub repo — added an explicit exception so charts are trackable while
raw/processed data files stay excluded.

### Bug found via visual inspection: blank heatmap

Added two more chart types afterward for genuine variety (not just
decoration) -- a skill co-occurrence heatmap and a category/skill treemap.
The heatmap initially rendered as a completely blank pale rectangle with no
visible cells or values. Root cause: the co-occurrence matrix was built
from boolean (`True`/`False`) values, and `pandas.DataFrame.dot()` on
boolean dtype didn't reliably produce the expected numeric matrix
multiplication result. Fixed by explicitly casting the matrix to `int`
before the dot product. Confirmed fixed by opening the regenerated file and
visually checking that populated colored cells with numeric labels
appeared, not just trusting that the script ran without throwing an error
-- a script exiting cleanly doesn't guarantee the *output* is correct.

Final chart set: 11 files, including the top-skills bar chart, category
donut, source breakdown, experience distribution, 4 head-to-head
comparisons, a skill co-occurrence heatmap, and a category/skill treemap.

---

---

## Step 4: Clustering

**Goal:** let real role categories emerge from the data via TF-IDF + KMeans,
rather than trusting inconsistent job titles (companies use "Data
Scientist", "AI/ML Engineer", "Applied AI Engineer" for near-identical
roles, and sometimes identical titles for very different roles).

Built a TF-IDF matrix (title weighted 2x + extracted skills + cleaned
description, 500 features, unigrams+bigrams), tested k=3 through k=10 via
silhouette score rather than picking a cluster count by eye, visualized
with a PCA-reduced 2D scatter plot.

### Bug found via manual verification: company "About Us" boilerplate polluting clusters

First run put a cluster together whose top TF-IDF terms were "ecommerce,
world, pushing boundaries, millions, committed, leader, future" -- not
job-content language at all. Manually inspected the postings inside that
cluster and found they were 14 completely unrelated roles (ML Engineer,
Applied Research Manager, SEO Science Engineer, Data Science Manager) that
all happened to come from eBay, whose postings all open with an identical
"About eBay" company-intro paragraph. That shared paragraph was distinctive
enough (rare vocabulary) that TF-IDF grouped postings by *which company's
boilerplate they had*, not by what the job actually was.

**Fix (generalized, not company-specific):** built `strip_company_boilerplate()`
in the wrangling step -- for any company with 2+ postings, it finds the
longest shared text prefix across that company's listings and strips it
before skill extraction or clustering ever see it. Deliberately generic
(detects the *pattern* of repeated boilerplate) rather than hardcoding
"eBay" or "myGwork" by name, so it also catches company intros we hadn't
manually spotted.

### Second bug found immediately after "fixing" the first one: smart punctuation broke exact-match detection

Re-ran expecting the eBay cluster to disappear -- it didn't. Re-inspected
and found eBay's postings hadn't been stripped at all, despite clearly
sharing the same opening paragraph to a human reader. Root cause: one
posting encoded that paragraph with curly quote/dash characters while
others used plain ASCII -- almost certainly because Adzuna and JSearch
normalize source-site punctuation differently. `os.path.commonprefix()`
compares strings character-by-character, so it stopped at the very first
curly-vs-straight mismatch, well short of the 60-character threshold needed
to trigger stripping.

**Fix:** added smart-punctuation normalization (curly quotes/dashes/ellipsis
-> plain ASCII equivalents) as the very first step of `clean_text()`, before
any other processing. Re-ran -- eBay correctly appeared in the stripped-
boilerplate log this time (18 postings), and the "ecommerce/pushing
boundaries" cluster was gone entirely from the next clustering run.

**Takeaway:** two bugs in a row here shared the same shape -- something
that looked identical to a human ("same eBay intro paragraph") wasn't
actually identical at the character level to the code. Trusting "looks the
same" instead of checking the actual string comparison would have shipped
a silently broken fix.

### Result

Best k=10 (silhouette score 0.073 -- in the expected 0.05-0.15 range for
real-world text with overlapping vocabulary, not image-style hard
boundaries). All 10 clusters now correspond to genuine role-type
distinctions: ML/NLP engineer, general AI/LLM engineer, classic Data
Scientist, applied AI research, software engineer (AI-adjacent), core
GenAI/LLM engineer (largest cluster, 91 postings), "AI Engineer"-titled
roles, data engineering/analytics, senior/staff ML engineer, and GenAI
developer/consultant roles -- confirming that Bangalore job titles alone
meaningfully undercount the number of distinct role types actually being
hired for.

Saved: `data/processed/jobs_clustered.json` / `.csv` (full dataset with
cluster assignments) and an interactive PCA scatter plot,
`data/processed/charts/role_clusters_scatter.html`.

---

---

## Step 5: GenAI Gap-Analysis Agent

**Goal:** an agent that takes a resume + a real target job posting and
produces a structured, honest gap analysis -- not just a portfolio piece,
genuinely useful for the current job search.

### Pivot: Anthropic API -> Google Gemini (cost)

Originally built against the Anthropic API, but Anthropic's API is
pay-as-you-go (no ongoing free tier, just a small one-time trial credit),
which isn't viable as a student. Switched to Google's Gemini API instead --
confirmed via research that it has a genuinely free, uncapped-duration tier
(1,500 requests/day, no credit card) as of mid-2026. Trade-off disclosed
and accepted: Google's free tier terms allow using free-tier prompts to
improve their models (paid tier doesn't) -- acceptable here since resume
content isn't sensitive company data, but worth knowing.

### Two quick technical fixes

- `google.generativeai` (the package initially installed) is deprecated;
  switched to the current `google.genai` SDK and updated the client call
  pattern before writing any real code against a dying package.
- The free-tier default model name changed between when this was researched
  and when it was actually run (`gemini-2.5-flash` returned 404 "no longer
  available to new users") -- had to re-check Google's current docs and
  switch to `gemini-3-flash-preview`, the actual current free-tier default.
  Reinforces a pattern from this whole project: provider APIs/model names
  drift faster than any tutorial or documentation can be trusted at face
  value -- always confirm against the live error message or current docs,
  not memory.

### Bug found in the AI's own reasoning, not the code: wrong assumed "current date"

First real run flagged the resume's 2026 internship/degree dates as
"speculative" or "like a typo," reasoning that *"it is currently
2024/2025."* That's wrong -- it's actually mid-2026. The model has no
built-in awareness of today's real date and silently defaulted to an
incorrect assumption, then built a confident-sounding but false claim on
top of it. This is a subtler failure mode than the previous code bugs in
this project: the script ran perfectly, returned a well-formatted, readable
answer, and was simply *wrong* about a specific fact in a way that would
have been easy to miss without reading the output carefully rather than
just checking "did it run."

**Fix:** explicitly inject the real current date into the prompt
(`Today's actual date is {today}`) rather than relying on the model to
infer or guess it. Re-ran the same posting -- the corrected version
correctly reasoned "As of July 2026, you have approximately 10 months of
internship experience," no longer flagging the 2026 dates as suspicious.

**Takeaway:** this project's core discipline -- verify output against
ground truth before trusting it, don't just check that something ran
without error -- applies just as much to LLM-generated reasoning as it does
to regex or clustering code. An LLM stating something fluently and
confidently is not evidence that it's correct.

### Result

Working CLI agent (`genai/gap_analysis.py`) that lists available postings
from the Step 4 clustered dataset, takes a plain-text resume, and produces
a 5-section gap analysis (Strong Matches, Real Gaps, Overstated/Ambiguous,
Concrete Next Steps, Overall Fit) saved as a timestamped markdown report.
First real analysis (own resume vs a mid-level Data Scientist posting)
correctly identified a genuine seniority gap, a title/duties mismatch
between "Software Engineer Intern" and the actual data science work
performed, and gave specific, actionable next steps rather than generic
advice.

---

---

## Step 6: Streamlit App + Deployment
**Goal:** wrap the whole pipeline into a single live link -- market overview
charts, role clusters, and resume gap analysis -- instead of a repo someone
has to clone and run 5 scripts against.

### PDF/DOCX upload instead of plain text
Originally planned a plain-text resume input, but realized before building
that no one trying a live demo has a `.txt` resume sitting around -- they'll
want to drag in their actual PDF or Word doc. Added `pypdf` for PDF text
extraction and `python-docx` for `.docx`, both feeding into the same
skill-matching and gap-analysis pipeline already built in Steps 4-5.

### The PyArrow segfault (multi-day debugging rabbit hole)
`st.dataframe`/`st.table` crashed the app with a hard `zsh: segmentation
fault` on submit, no Python traceback. Chased several plausible causes in
order: pandas defaulting to the PyArrow string backend on 2.x
(`pip install "pandas<3.0.0"` -- didn't fix it), a corrupted venv (full
rebuild -- didn't fix it), Apple Silicon running under Rosetta
(`uname -m` vs `platform.machine()` both returned `arm64`, ruled out), and
pandas being unsafe off the main thread (isolated repro in a bare
`threading.Thread` -- ran clean, ruled out). A fresh traceback with
`PYTHONFAULTHANDLER=1` finally pointed at PyArrow's own Arrow conversion
(`convert_anything_to_arrow_bytes`) choking on nested list objects inside a
DataFrame column -- a real, known PyArrow fragility, not a bug in this
project's code.
**Fix:** stopped trying to work around PyArrow and avoided it entirely.
Replaced every `st.dataframe`/`st.table` call with a custom
`render_table()` that builds an HTML/Markdown table as a plain string via
`st.markdown()` -- no Arrow serialization involved at all. Lost a little
built-in polish (sorting/filtering UI) but the segfault is gone completely,
not just delayed.

### Missing dependencies caught only by a fresh environment
Two separate "works locally, breaks on rebuild" issues, both the same root
cause: a package installed manually mid-session (`pip install X`) but never
actually added to `requirements.txt`.
- `pypdf` -- missing after a full local venv rebuild.
- `google-genai` -- missing on the first Streamlit Community Cloud deploy,
  surfaced as `ImportError: cannot import name 'genai' from 'google'`.
**Takeaway:** `pip install` in an active terminal session is not the same
as the dependency being recorded anywhere. Any package installed
ad hoc needs to be added to `requirements.txt` in the same breath, or it
silently vanishes the next time the environment is rebuilt from scratch --
locally or on a deploy platform.

### Result
Live app on Streamlit Community Cloud with three tabs: Market Overview (9
interactive charts), Role Clusters (TF-IDF/KMeans explorer), and Resume Gap
Analysis (PDF/DOCX/TXT upload -> skill-overlap ranking against all 407
postings -> full Gemini-powered gap analysis on any selected posting).
GEMINI_API_KEY stored in Streamlit Cloud's Secrets manager, not committed
to the repo. First cold-deploy test, run end to end after fixing both
missing dependencies, worked cleanly.
---
