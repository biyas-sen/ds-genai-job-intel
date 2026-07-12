"""
Step 5: GenAI Gap-Analysis Agent.

Takes your resume + a real target job posting from the clustered dataset
and asks Gemini to produce a structured gap analysis: what matches, what's
missing, and concretely how to strengthen your candidacy for that role.

Setup:
    1. Save your resume as plain text at ./my_resume.txt (project root)
    2. Put your free Gemini API key in .env as GEMINI_API_KEY
       (get one at https://aistudio.google.com -- no credit card needed)

Usage:
    python -m genai.gap_analysis --list              # see available postings
    python -m genai.gap_analysis --job 42             # analyze posting #42
    python -m genai.gap_analysis --job 42 --resume path/to/resume.txt
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

from google import genai

sys.path.append(str(Path(__file__).parent.parent))
from config import PROCESSED_DIR, GEMINI_API_KEY

ROOT = Path(__file__).parent.parent
DEFAULT_RESUME_PATH = ROOT / "my_resume.txt"
REPORTS_DIR = PROCESSED_DIR / "gap_analysis_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "gemini-3-flash-preview"


def load_jobs() -> list[dict]:
    path = PROCESSED_DIR / "jobs_clustered.json"
    if not path.exists():
        print(f"[!] {path} not found -- run Step 4 (python -m ml.cluster_roles) first.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def list_jobs(jobs: list[dict], limit: int = 30):
    print(f"\nShowing {min(limit, len(jobs))} of {len(jobs)} postings "
          f"(use --job <index> to pick one):\n")
    for i, job in enumerate(jobs[:limit]):
        skills_preview = ", ".join(job["skills_extracted"][:4])
        print(f"[{i}] {job['title']} @ {job['company']} "
              f"(cluster {job['cluster']}) -- {skills_preview}")


def load_resume(path: Path) -> str:
    if not path.exists():
        print(f"[!] Resume file not found at {path}")
        print("    Create a plain text file with your resume content there, then retry.")
        sys.exit(1)
    text = path.read_text().strip()
    if len(text) < 100:
        print(f"[!] {path} seems too short ({len(text)} chars) to be a full resume -- check the file.")
        sys.exit(1)
    return text


def build_prompt(resume_text: str, job: dict) -> str:
    today = datetime.now().strftime("%B %Y")
    return f"""You are a career advisor helping a candidate assess their fit for a specific job posting. Be honest and specific, not generically encouraging.

IMPORTANT: Today's actual date is {today}. Use this as ground truth for any date reasoning (e.g. whether a listed internship or degree date is in the past, present, or future). Do not assume or guess the current date from anything else.

## Candidate's Resume

{resume_text}

## Target Job Posting

Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Extracted skills mentioned in posting: {', '.join(job['skills_extracted']) if job['skills_extracted'] else 'none reliably extracted'}

Full description:
{job['description_clean']}

## Your Task

Produce a gap analysis with these exact sections:

### Strong Matches
Specific skills/experience from the resume that directly match what this posting wants. Cite the actual resume content, don't just restate the job posting.

### Real Gaps
Skills/experience the posting wants that the resume doesn't clearly demonstrate. Be specific -- not "needs more ML experience" but "posting emphasizes production RAG pipelines; resume shows model training but no deployment/serving experience."

### Overstated or Ambiguous
Anything on the resume that's phrased vaguely enough that a reviewer might not credit it, even if the underlying experience might actually count.

### Concrete Next Steps
2-4 specific, actionable things the candidate could do to close the biggest gaps -- a project to build, a concept to learn, or how to rephrase existing experience to surface it better. Not generic advice like "learn more about AI."

### Overall Fit
One honest paragraph: is this a reasonable role to apply for now, a stretch worth trying anyway, or not yet a good match -- and why."""


def run_analysis(resume_text: str, job: dict) -> str:
    if not GEMINI_API_KEY:
        print("[!] GEMINI_API_KEY not set in .env -- get a free key at "
              "https://aistudio.google.com and retry.")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = build_prompt(resume_text, job)

    print(f"Sending resume vs '{job['title']}' @ {job['company']} to Gemini...")
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text


def save_report(job: dict, analysis: str, resume_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in job["title"])[:40]
    out_path = REPORTS_DIR / f"gap_analysis_{safe_title}_{timestamp}.md"

    content = f"""# Gap Analysis: {job['title']} @ {job['company']}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Resume used:** {resume_path.name}
**Job location:** {job['location']}
**Job posting URL:** {job.get('url', 'n/a')}

---

{analysis}
"""
    out_path.write_text(content)
    return out_path


def run():
    parser = argparse.ArgumentParser(description="Resume vs job posting gap analysis")
    parser.add_argument("--list", action="store_true", help="List available job postings")
    parser.add_argument("--job", type=int, help="Index of the job posting to analyze")
    parser.add_argument("--resume", type=str, default=str(DEFAULT_RESUME_PATH),
                         help="Path to your resume text file")
    args = parser.parse_args()

    jobs = load_jobs()

    if args.list or args.job is None:
        list_jobs(jobs)
        if args.job is None:
            print("\nRe-run with --job <index> to analyze a specific posting.")
            return

    job = jobs[args.job]
    resume_path = Path(args.resume)
    resume_text = load_resume(resume_path)

    analysis = run_analysis(resume_text, job)
    out_path = save_report(job, analysis, resume_path)

    print("\n" + "=" * 70)
    print(analysis)
    print("=" * 70)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    run()
