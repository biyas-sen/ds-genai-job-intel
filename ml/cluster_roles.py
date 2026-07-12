"""
Step 4: Clustering.

Uses TF-IDF + KMeans to let the real role categories emerge from the data,
rather than guessing them from job titles (which are often inconsistent --
"Data Scientist", "AI/ML Engineer", "Applied AI Engineer" frequently
describe near-identical roles, and sometimes very different ones share a
title).

Run:
    python -m ml.cluster_roles
"""
import sys
import json
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
import plotly.express as px

sys.path.append(str(Path(__file__).parent.parent))
from config import PROCESSED_DIR

CHARTS_DIR = PROCESSED_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
PLOTLY_JS_MODE = "cdn"

K_RANGE = range(3, 11)  # try 3 to 10 clusters


def load_data() -> pd.DataFrame:
    path = PROCESSED_DIR / "jobs_clean.json"
    if not path.exists():
        print(f"[!] {path} not found -- run `python -m wrangling.extract_skills` first.")
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    return pd.DataFrame(data)


def build_corpus(df: pd.DataFrame) -> list[str]:
    """
    Build the text each posting will be clustered on. Title is repeated for
    extra weight (it's the highest-signal, lowest-noise field), skills are
    included as space-joined tokens, then the cleaned description text.
    """
    corpus = []
    for _, row in df.iterrows():
        title = (row["title"] or "") + " " + (row["title"] or "")  # weight x2
        skills = " ".join(row["skills_extracted"]) if row["skills_extracted"] else ""
        desc = row["description_clean"] or ""
        corpus.append(f"{title} {skills} {desc}")
    return corpus


def find_optimal_k(X) -> tuple[int, dict]:
    """Try a range of k values, score each with silhouette score, return the best."""
    scores = {}
    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        score = silhouette_score(X, labels)
        scores[k] = score
        print(f"  k={k}: silhouette score = {score:.4f}")

    best_k = max(scores, key=scores.get)
    return best_k, scores


def top_terms_per_cluster(vectorizer, km, n_terms: int = 12) -> dict[int, list[str]]:
    terms = np.array(vectorizer.get_feature_names_out())
    centroids = km.cluster_centers_
    result = {}
    for i, centroid in enumerate(centroids):
        top_idx = centroid.argsort()[::-1][:n_terms]
        result[i] = list(terms[top_idx])
    return result


def summarize_clusters(df: pd.DataFrame, vectorizer, km) -> None:
    terms_by_cluster = top_terms_per_cluster(vectorizer, km)
    print("\n" + "=" * 70)
    print("CLUSTER SUMMARY")
    print("=" * 70)
    for cluster_id in sorted(df["cluster"].unique()):
        subset = df[df["cluster"] == cluster_id]
        print(f"\n--- Cluster {cluster_id} ({len(subset)} postings) ---")
        print(f"Top terms: {', '.join(terms_by_cluster[cluster_id])}")
        print("Sample titles:")
        for title in subset["title"].head(5):
            print(f"  - {title}")


def visualize_clusters(df: pd.DataFrame, X):
    """2D PCA scatter plot so clusters are actually visible, not just numbers."""
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X.toarray())

    plot_df = df.copy()
    plot_df["pca_x"] = coords[:, 0]
    plot_df["pca_y"] = coords[:, 1]
    plot_df["cluster_label"] = "Cluster " + plot_df["cluster"].astype(str)

    fig = px.scatter(
        plot_df,
        x="pca_x",
        y="pca_y",
        color="cluster_label",
        hover_data=["title", "company"],
        title=f"Job Postings Clustered by Content Similarity (n={len(df)}, "
              f"{df['cluster'].nunique()} clusters, PCA-reduced to 2D)",
    )
    fig.update_traces(marker=dict(size=8, opacity=0.7))
    out = CHARTS_DIR / "role_clusters_scatter.html"
    fig.write_html(out, include_plotlyjs=PLOTLY_JS_MODE)
    print(f"\nSaved scatter plot -> {out}")


def run():
    df = load_data()
    print(f"Loaded {len(df)} postings.\n")

    print("Building TF-IDF matrix...")
    corpus = build_corpus(df)
    vectorizer = TfidfVectorizer(
        max_features=500,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=3,       # ignore terms that appear in fewer than 3 postings
        max_df=0.7,     # ignore terms that appear in more than 70% of postings (too generic)
    )
    X = vectorizer.fit_transform(corpus)
    print(f"TF-IDF matrix shape: {X.shape[0]} postings x {X.shape[1]} terms\n")

    print("Testing cluster counts (k=3 to 10) via silhouette score...")
    best_k, scores = find_optimal_k(X)
    print(f"\nBest k = {best_k} (silhouette score = {scores[best_k]:.4f})")

    print(f"\nFitting final KMeans with k={best_k}...")
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df["cluster"] = km.fit_predict(X)

    summarize_clusters(df, vectorizer, km)
    visualize_clusters(df, X)

    # Save cluster assignments back into the dataset
    out_json = PROCESSED_DIR / "jobs_clustered.json"
    out_csv = PROCESSED_DIR / "jobs_clustered.csv"

    df_csv = df.copy()
    df_csv["skills_extracted"] = df_csv["skills_extracted"].apply(lambda s: ", ".join(s))
    df_csv.to_csv(out_csv, index=False)
    df.to_json(out_json, orient="records", indent=2)

    print(f"\nSaved -> {out_json}")
    print(f"Saved -> {out_csv}")
    print(f"\nSilhouette score of {scores[best_k]:.4f} note: values range -1 to 1, "
          f"higher is better-separated clusters. Real-world text data (like job "
          f"postings with overlapping vocabulary) typically scores 0.05-0.15 for "
          f"genuinely meaningful clusters -- this isn't image data with hard "
          f"boundaries, so don't expect scores near 1.0.")

    return df


if __name__ == "__main__":
    run()
