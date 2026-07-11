"""
Skills taxonomy for DS/GenAI roles.

Organized by category so later analysis can answer questions like
"which category dominates postings" not just "which single skill".

Matching is done as case-insensitive whole-word/phrase search against
cleaned job description text. Keep entries as they'd actually appear in a
posting (e.g. "scikit-learn" not "sklearn" as the canonical form, but we
list common aliases too -- the first alias becomes the display name).
"""

# Each skill: canonical_name -> [list of surface forms to match, first is default]
SKILLS_TAXONOMY = {
    "Programming Languages": {
        "Python": ["python"],
        "SQL": ["sql"],
        "R": [r"\br\b(?=.*(stat|programming|language))", "r programming", "r language"],
        "Java": ["java(?!script)"],
        "Scala": [r"\bscala\b"],
        "C++": ["c\\+\\+"],
    },
    "Core ML / DS": {
        "Machine Learning": ["machine learning", "\\bml\\b"],
        "Deep Learning": ["deep learning", "\\bdl\\b"],
        "scikit-learn": ["scikit-learn", "sklearn"],
        "Pandas": ["pandas"],
        "NumPy": ["numpy"],
        "PyTorch": ["pytorch", "torch"],
        "TensorFlow": ["tensorflow"],
        "Keras": ["keras"],
        "XGBoost": ["xgboost"],
        "Statistics": ["statistics", "statistical"],
        "A/B Testing": ["a/b testing", "ab testing"],
        "Time Series": ["time series", "time-series"],
        "Computer Vision": ["computer vision", "\\bcv\\b(?=.*(image|vision))"],
        "Reinforcement Learning": ["reinforcement learning"],
    },
    "GenAI / LLM": {
        "LLM": ["\\bllm\\b", "large language model"],
        "Generative AI": ["generative ai", "genai", "gen ai"],
        "RAG": ["\\brag\\b", "retrieval augmented generation", "retrieval-augmented generation"],
        "Fine-tuning": ["fine-tun", "finetun"],
        "Prompt Engineering": ["prompt engineering", "prompt design"],
        "LangChain": ["langchain"],
        "LlamaIndex": ["llamaindex", "llama index"],
        "LangGraph": ["langgraph"],
        "AutoGPT": ["autogpt"],
        "CrewAI": ["crewai", "crew ai"],
        "Hugging Face": ["hugging face", "huggingface"],
        "Transformers": ["transformer"],
        "BERT": ["\\bbert\\b"],
        "GPT-4": ["gpt-4", "gpt4"],
        "OpenAI API": ["openai api", "openai"],
        "Claude / Anthropic": ["claude", "anthropic"],
        "Llama (Meta)": ["\\bllama\\b(?!index)"],
        "Mistral": ["mistral"],
        "Gemini": ["gemini"],
        "Agents": ["ai agent", "agentic", "\\bagents?\\b(?=.*(ai|llm|autonomous))"],
        "Embeddings": ["embedding"],
        "Semantic Search": ["semantic search"],
        "Vector Database": ["vector database", "vector db", "vector store"],
        "Pinecone": ["pinecone"],
        "Weaviate": ["weaviate"],
        "FAISS": ["faiss"],
        "ChromaDB": ["chromadb", "chroma db"],
        "NLP": ["\\bnlp\\b", "natural language processing"],
    },
    "MLOps / Infra": {
        "MLOps": ["mlops", "ml ops"],
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "\\bk8s\\b"],
        "MLflow": ["mlflow"],
        "Kubeflow": ["kubeflow"],
        "Airflow": ["airflow"],
        "Git": ["\\bgit\\b"],
        "CI/CD": ["ci/cd", "continuous integration"],
    },
    "Cloud": {
        "AWS": ["\\baws\\b", "amazon web services"],
        "Azure": ["\\bazure\\b"],
        "GCP": ["\\bgcp\\b", "google cloud"],
    },
    "Data Engineering": {
        "Spark": ["spark"],
        "Hadoop": ["hadoop"],
        "ETL": ["\\betl\\b"],
        "PostgreSQL": ["postgresql", "postgres"],
        "MongoDB": ["mongodb"],
        "NoSQL": ["nosql"],
        "Data Engineering": ["data engineering"],
    },
    "BI / Visualization": {
        "Tableau": ["tableau"],
        "Power BI": ["power bi", "powerbi"],
        "Excel": [r"\bexcel\b(?!lent|s\b)"],
    },
}

# Flatten into a single lookup: canonical_name -> [regex patterns]
FLAT_TAXONOMY = {
    name: patterns
    for category in SKILLS_TAXONOMY.values()
    for name, patterns in category.items()
}

# Reverse lookup: canonical_name -> category (for grouped charts later)
SKILL_TO_CATEGORY = {
    name: cat
    for cat, skills in SKILLS_TAXONOMY.items()
    for name in skills
}
