"""
Step 6: Streamlit app.

Ties together everything built in Steps 1-5 into one live, interactive app:
- Market Overview: charts from Step 3
- Role Clusters: cluster scatter + summaries from Step 4
- Resume Gap Analysis: upload a real PDF/DOCX/TXT resume, pick a job
  posting, get a live gap analysis from Step 5's agent

Run locally:
    streamlit run app/streamlit_app.py
"""
import sys
import json
from pathlib import Path
from io import BytesIO

import streamlit as st
import pandas as pd


sys.path.append(str(Path(__file__).parent.parent))
from config import PROCESSED_DIR, GEMINI_API_KEY
from genai.gap_analysis import build_prompt
from wrangling.extract_skills import extract_skills as extract_skills_from_text

CHARTS_DIR = PROCESSED_DIR / "charts"

st.set_page_config(
    page_title="Bangalore DS/GenAI Job Market Intelligence",
    page_icon="📊",
    layout="wide",
)


# ---------- Data loading (cached so it doesn't reload on every interaction) ----------

@st.cache_data
def load_jobs() -> list[dict]:
    path = PROCESSED_DIR / "jobs_clustered.json"
    with open(path) as f:
        return json.load(f)


def load_chart_html(filename: str) -> str:
    path = CHARTS_DIR / filename
    if not path.exists():
        return f"<p>Chart not found: {filename}</p>"
    return path.read_text()


def render_table(df: pd.DataFrame):
    """
    Render a DataFrame as a plain Markdown table via st.markdown.
    PyArrow is broken on some machines for Streamlit's normal table widgets
    (st.dataframe / st.table both route through PyArrow's Arrow conversion
    internally and can segfault). Building the table as a markdown string
    completely avoids PyArrow -- pure text, no native library involved.
    """
    headers = list(df.columns)
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for _, row in df.iterrows():
        cells = [str(row[h]).replace("|", "-").replace("\n", " ") for h in headers]
        lines.append("| " + " | ".join(cells) + " |")
    st.markdown("\n".join(lines))


# ---------- Resume text extraction (PDF / DOCX / TXT) ----------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(file_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx
    doc = docx.Document(BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_resume_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    if name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif name.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: {name}")


# ---------- Gemini call ----------

def run_gap_analysis(resume_text: str, job: dict) -> str:
    from google import genai
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = build_prompt(resume_text, job)
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
    )
    return response.text


# ---------- App layout ----------

st.title("📊 Bangalore DS/GenAI Job Market Intelligence")
st.caption(
    "Built from real job postings collected via the Adzuna and JSearch APIs. "
    "See the full pipeline and dev log on "
    "[GitHub](https://github.com/biyas-sen/ds-genai-job-intel)."
)

jobs = load_jobs()
df = pd.DataFrame(jobs, dtype=object)

tab1, tab2, tab3 = st.tabs(["📈 Market Overview", "🧩 Role Clusters", "📄 Resume Gap Analysis"])

# ---------- Tab 1: Market Overview ----------
with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total postings analyzed", len(df))
    col2.metric("Unique companies", df["company"].nunique())
    col3.metric("Avg skills extracted / posting", f"{df['skill_count'].mean():.1f}")

    st.subheader("Top Skills")
    st.iframe(load_chart_html("top_skills.html"), height=750)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Skill Category Breakdown")
        st.iframe(load_chart_html("category_breakdown.html"), height=500)
    with col_b:
        st.subheader("Skills Treemap")
        st.iframe(load_chart_html("skills_treemap.html"), height=500)

    st.subheader("Skill Co-occurrence")
    st.iframe(load_chart_html("skill_cooccurrence.html"), height=750)

    st.subheader("Head-to-Head Comparisons")
    h2h_col1, h2h_col2 = st.columns(2)
    with h2h_col1:
        st.iframe(load_chart_html("langchain_vs_llamaindex.html"), height=450)
        st.iframe(load_chart_html("python_vs_sql.html"), height=450)
    with h2h_col2:
        st.iframe(load_chart_html("rag_vs_finetuning.html"), height=450)
        st.iframe(load_chart_html("pytorch_vs_tensorflow.html"), height=450)

# ---------- Tab 2: Role Clusters ----------
with tab2:
    st.subheader("Job Postings Clustered by Content Similarity")
    st.caption(
        "TF-IDF + KMeans clustering on 407 real postings reveals role categories "
        "that don't cleanly map to job titles alone."
    )
    st.iframe(load_chart_html("role_clusters_scatter.html"), height=700)

    st.subheader("Explore a Cluster")
    cluster_ids = sorted(df["cluster"].unique())
    selected_cluster = st.selectbox("Pick a cluster to see sample postings", cluster_ids)
    cluster_df = df[df["cluster"] == selected_cluster][["title", "company", "location", "skills_extracted"]].copy()
    cluster_df["skills_extracted"] = cluster_df["skills_extracted"].apply(
        lambda skills: ", ".join(skills) if isinstance(skills, list) else skills
    )
    render_table(cluster_df.head(15))

# ---------- Tab 3: Resume Gap Analysis ----------
with tab3:
    st.subheader("Step 1: Upload your resume")
    st.caption(
        "Upload a PDF, Word doc, or plain text resume. We'll instantly rank all "
        f"{len(jobs)} postings by skill overlap with your resume -- no API calls, "
        "no waiting. Then pick any match for a full AI-generated gap analysis."
    )

    if not GEMINI_API_KEY:
        st.warning(
            "GEMINI_API_KEY isn't configured -- the ranking below will still work, "
            "but the deep-dive analysis in Step 2 needs it. Add it to your .env "
            "locally, or under App Settings -> Secrets on Streamlit Cloud."
        )

    uploaded_file = st.file_uploader(
        "Upload your resume", type=["pdf", "docx", "txt"], accept_multiple_files=False
    )

    if uploaded_file is not None and st.button("Find My Best Matches", type="primary"):
        with st.spinner("Extracting resume text and scanning all postings..."):
            try:
                resume_text = extract_resume_text(uploaded_file)
            except Exception as e:
                st.error(f"Couldn't read that file: {e}")
                st.stop()

            if len(resume_text.strip()) < 100:
                st.error(
                    "Extracted very little text from that file -- it might be a "
                    "scanned image PDF rather than real text. Try a different file."
                )
                st.stop()

            resume_skills = set(extract_skills_from_text(resume_text))
            st.session_state["resume_text"] = resume_text
            st.session_state["resume_skills"] = resume_skills

    if "resume_skills" in st.session_state:
        resume_skills = st.session_state["resume_skills"]

        st.markdown(f"**Skills detected on your resume:** {', '.join(sorted(resume_skills)) or 'none detected'}")

        scored = []
        for j in jobs:
            job_skills = set(j["skills_extracted"])
            matched = resume_skills & job_skills
            coverage = (len(matched) / len(job_skills) * 100) if job_skills else 0
            scored.append({
                "title": j["title"],
                "company": j["company"],
                "cluster": j["cluster"],
                "matched_count": len(matched),
                "job_requires": len(job_skills),
                "coverage_%": round(coverage),
                "matched_skills": ", ".join(sorted(matched)) or "-",
            })

        scored_df = pd.DataFrame(scored, dtype=object).sort_values(
            ["matched_count", "coverage_%"], ascending=[False, False]
        ).reset_index(drop=True)

        st.subheader("Step 2: Your Best Matches")
        st.caption("Ranked by number of your skills that appear in each posting.")
        render_table(scored_df.head(25))

        st.subheader("Step 3: Deep-Dive Gap Analysis")
        st.caption("Pick any posting above (or search all postings below) for a full AI-generated breakdown.")

        top_matches = scored_df.head(25)
        match_labels = [
            f"{r['title']} @ {r['company']} -- {r['matched_count']} skills matched"
            for _, r in top_matches.iterrows()
        ]
        all_labels = [f"{j['title']} @ {j['company']}" for j in jobs]

        use_full_list = st.checkbox("Search all postings instead of just top matches")
        if use_full_list:
            selected_label = st.selectbox("Select any job posting", all_labels)
            selected_job = jobs[all_labels.index(selected_label)]
        else:
            selected_label = st.selectbox("Select a top match", match_labels)
            selected_idx = match_labels.index(selected_label)
            selected_title = top_matches.iloc[selected_idx]["title"]
            selected_company = top_matches.iloc[selected_idx]["company"]
            selected_job = next(
                j for j in jobs if j["title"] == selected_title and j["company"] == selected_company
            )

        with st.expander("View full job posting"):
            st.write(f"**Location:** {selected_job['location']}")
            st.write(f"**Extracted skills:** {', '.join(selected_job['skills_extracted']) or 'none reliably extracted'}")
            st.write(selected_job["description_clean"])

        if st.button("Run Full Gap Analysis", type="primary"):
            with st.spinner("Analyzing fit against the job posting..."):
                try:
                    analysis = run_gap_analysis(st.session_state["resume_text"], selected_job)
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    st.stop()

            st.success("Analysis complete")
            st.markdown(analysis)

st.divider()
st.caption(
    "Data collected via Adzuna and JSearch APIs, July 2026. "
    "Pipeline: collection -> wrangling -> visualization -> clustering -> GenAI gap analysis. "
    "Full source and dev log on GitHub."
)
