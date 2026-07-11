"""
Step 3: Visualization.

Loads data/processed/jobs_clean.json and produces interactive Plotly charts
saved as standalone HTML files (viewable in any browser, and reusable
directly inside the Step 6 Streamlit app later).

Run:
    python -m analysis.visualize
"""
import sys
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.append(str(Path(__file__).parent.parent))
from config import PROCESSED_DIR
from wrangling.skills_taxonomy import SKILL_TO_CATEGORY

CHARTS_DIR = PROCESSED_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    path = PROCESSED_DIR / "jobs_clean.json"
    if not path.exists():
        print(f"[!] {path} not found -- run `python -m wrangling.extract_skills` first.")
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    return pd.DataFrame(data)


def skill_counts(df: pd.DataFrame) -> pd.Series:
    all_skills = [s for skills in df["skills_extracted"] for s in skills]
    return pd.Series(Counter(all_skills)).sort_values(ascending=False)


def chart_top_skills(df: pd.DataFrame, top_n: int = 20):
    counts = skill_counts(df).head(top_n)
    pct = (counts / len(df) * 100).round(1)

    fig = go.Figure(go.Bar(
        x=counts.values[::-1],
        y=counts.index[::-1],
        orientation="h",
        text=[f"{v} ({p}%)" for v, p in zip(counts.values[::-1], pct.values[::-1])],
        textposition="outside",
        marker_color="#2563eb",
    ))
    fig.update_layout(
        title=f"Top {top_n} Skills in Bangalore DS/GenAI Postings (n={len(df)})",
        xaxis_title="Number of postings mentioning this skill",
        height=700,
        margin=dict(l=180),
    )
    out = CHARTS_DIR / "top_skills.html"
    fig.write_html(out)
    print(f"  saved -> {out}")


def chart_category_breakdown(df: pd.DataFrame):
    counts = skill_counts(df)
    cat_totals = Counter()
    for skill, count in counts.items():
        cat = SKILL_TO_CATEGORY.get(skill, "Other")
        cat_totals[cat] += count

    cat_series = pd.Series(cat_totals).sort_values(ascending=False)

    fig = px.pie(
        values=cat_series.values,
        names=cat_series.index,
        title=f"Skill Mentions by Category (n={len(df)} postings)",
        hole=0.4,
    )
    fig.update_traces(textinfo="label+percent")
    out = CHARTS_DIR / "category_breakdown.html"
    fig.write_html(out)
    print(f"  saved -> {out}")


def chart_head_to_head(df: pd.DataFrame, pairs: list[tuple[str, str]], title: str, filename: str):
    """Bar chart comparing specific skill pairs head-to-head."""
    counts = skill_counts(df)
    labels, values = [], []
    for a, b in pairs:
        labels.extend([a, b])
        values.extend([counts.get(a, 0), counts.get(b, 0)])

    colors = ["#2563eb", "#93c5fd"] * len(pairs)
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=colors,
                            text=values, textposition="outside"))
    fig.update_layout(title=f"{title} (n={len(df)} postings)", yaxis_title="Postings mentioning")
    out = CHARTS_DIR / filename
    fig.write_html(out)
    print(f"  saved -> {out}")


def chart_experience_distribution(df: pd.DataFrame):
    exp_df = df[df["exp_min_years"].notna()].copy()
    if exp_df.empty:
        print("  [!] no postings with extractable experience bands -- skipping this chart")
        return

    exp_df["exp_min_years"] = exp_df["exp_min_years"].astype(int)
    counts = exp_df["exp_min_years"].value_counts().sort_index()

    fig = go.Figure(go.Bar(x=counts.index.astype(str), y=counts.values,
                            marker_color="#2563eb", text=counts.values,
                            textposition="outside"))
    fig.update_layout(
        title=f"Minimum Experience Required (extracted from text, n={len(exp_df)} of "
              f"{len(df)} postings had a parseable band)",
        xaxis_title="Minimum years required",
        yaxis_title="Number of postings",
    )
    out = CHARTS_DIR / "experience_distribution.html"
    fig.write_html(out)
    print(f"  saved -> {out}")


def chart_source_breakdown(df: pd.DataFrame):
    counts = df["source"].value_counts()
    fig = px.bar(x=counts.index, y=counts.values,
                 labels={"x": "Source", "y": "Number of postings"},
                 title=f"Postings by Source (n={len(df)} total, after dedup)")
    fig.update_traces(marker_color="#2563eb", text=counts.values, textposition="outside")
    out = CHARTS_DIR / "source_breakdown.html"
    fig.write_html(out)
    print(f"  saved -> {out}")


def run():
    df = load_data()
    print(f"Loaded {len(df)} processed postings.\n")

    print("Building charts...")
    chart_top_skills(df)
    chart_category_breakdown(df)
    chart_source_breakdown(df)
    chart_experience_distribution(df)

    chart_head_to_head(
        df,
        pairs=[("LangChain", "LlamaIndex")],
        title="LangChain vs LlamaIndex",
        filename="langchain_vs_llamaindex.html",
    )
    chart_head_to_head(
        df,
        pairs=[("RAG", "Fine-tuning")],
        title="RAG vs Fine-tuning",
        filename="rag_vs_finetuning.html",
    )
    chart_head_to_head(
        df,
        pairs=[("Python", "SQL")],
        title="Python vs SQL",
        filename="python_vs_sql.html",
    )
    chart_head_to_head(
        df,
        pairs=[("PyTorch", "TensorFlow")],
        title="PyTorch vs TensorFlow",
        filename="pytorch_vs_tensorflow.html",
    )
    chart_head_to_head(
        df,
        pairs=[("AWS", "Azure"), ("Azure", "GCP")],
        title="Cloud Platform Mentions",
        filename="cloud_platforms.html",
    )

    print(f"\nAll charts saved to {CHARTS_DIR}/")
    print("Open any .html file in a browser to view it interactively.")

    # NOTE on trend-over-time: this snapshot is from a single scrape date.
    # Real month-to-month trend charts need multiple timestamped raw files
    # collected over several weeks/months -- the collectors already save
    # timestamped files, so re-running them periodically and re-running this
    # script will let us build that view later without any code changes here.


if __name__ == "__main__":
    run()
