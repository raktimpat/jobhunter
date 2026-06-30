"""
config/search_targets.py
────────────────────────
Mirrors the Apify actor input from the n8n workflow exactly.

Edit SEARCH_URLS to add/remove locations or job titles.
Edit RESUME_KEYWORDS to match your current skill set.
"""

# ── LinkedIn job search URLs ─────────────────────────────────────────────
# Copied directly from the n8n workflow's linkedin_actor startUrls.
# Each URL is a pre-filtered LinkedIn public job search page.
# You can generate new ones by:
#   1. Opening linkedin.com/jobs in an incognito window
#   2. Searching for a title + applying location/date filters
#   3. Copying the URL from the address bar
SEARCH_URLS = [
    # Singapore
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Singapore&geoId=102454443&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Singapore&geoId=102454443&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Singapore&geoId=102454443&f_TPR=r604800",
    # Dubai
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Dubai%2C+United+Arab+Emirates&geoId=106204383&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Dubai%2C+United+Arab+Emirates&geoId=106204383&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Dubai%2C+United+Arab+Emirates&geoId=106204383&f_TPR=r604800",
    # Abu Dhabi
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Abu+Dhabi%2C+United+Arab+Emirates&geoId=101271938&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Abu+Dhabi%2C+United+Arab+Emirates&geoId=101271938&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Abu+Dhabi%2C+United+Arab+Emirates&geoId=101271938&f_TPR=r604800",
    # Sydney
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Sydney%2C+Australia&geoId=105995015&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Sydney%2C+Australia&geoId=105995015&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Sydney%2C+Australia&geoId=105995015&f_TPR=r604800",
    # Melbourne
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Melbourne%2C+Australia&geoId=101399767&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Melbourne%2C+Australia&geoId=101399767&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Melbourne%2C+Australia&geoId=101399767&f_TPR=r604800",
    # Brisbane
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Brisbane%2C+Australia&geoId=103980767&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Brisbane%2C+Australia&geoId=103980767&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Brisbane%2C+Australia&geoId=103980767&f_TPR=r604800",
    # Amsterdam
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Amsterdam%2C+Netherlands&geoId=102011674&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Amsterdam%2C+Netherlands&geoId=102011674&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Amsterdam%2C+Netherlands&geoId=102011674&f_TPR=r604800",
    # Rotterdam
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Rotterdam%2C+Netherlands&geoId=102418430&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Rotterdam%2C+Netherlands&geoId=102418430&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Rotterdam%2C+Netherlands&geoId=102418430&f_TPR=r604800",
    # Eindhoven
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Eindhoven%2C+Netherlands&geoId=104337823&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Eindhoven%2C+Netherlands&geoId=104337823&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=nlp+engineer&location=Eindhoven%2C+Netherlands&geoId=104337823&f_TPR=r604800",
    # Bangalore (from second actor in workflow)
    "https://www.linkedin.com/jobs/search/?keywords=machine+learning+engineer&location=Bengaluru%2C+Karnataka%2C+India&geoId=105214831&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=ai+engineer&location=Bengaluru%2C+Karnataka%2C+India&geoId=105214831&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=llm+engineer&location=Bengaluru%2C+Karnataka%2C+India&geoId=105214831&f_TPR=r604800",
]

# ── Resume keywords for skill matching ──────────────────────────────────
# Same as the n8n workflow's resumeKeywords array.
# Each entry: {"keyword": str, "aliases": [str, ...]}
RESUME_KEYWORDS = [
    {"keyword": "Python",           "aliases": ["FastAPI", "Flask", "Django", "Pandas", "NumPy"]},
    {"keyword": "Machine Learning", "aliases": ["PyTorch", "TensorFlow", "Scikit-learn", "Deep Learning"]},
    {"keyword": "LLM",              "aliases": ["Generative AI", "GenAI", "Large Language Models", "Transformers", "Prompt Engineering"]},
    {"keyword": "RAG",              "aliases": ["Retrieval Augmented Generation", "LangChain", "FAISS", "Vector Database", "Semantic Search"]},
    {"keyword": "Google Cloud",     "aliases": ["GCP", "Vertex AI", "Cloud Spanner", "Google Cloud Storage", "GCS"]},
    {"keyword": "AWS",              "aliases": ["SageMaker", "S3", "ECS"]},
    {"keyword": "MLOps",            "aliases": ["Docker", "Kubernetes", "CI/CD", "GitHub Actions", "Model Registry", "Model Monitoring"]},
    {"keyword": "Computer Vision",  "aliases": ["OpenCV", "CNN", "Image Segmentation", "Object Detection"]},
    {"keyword": "NLP",              "aliases": ["Natural Language Processing", "BERT", "Transformers", "Text Classification"]},
    {"keyword": "Data Engineering", "aliases": ["SQL", "PostgreSQL", "MySQL", "BigQuery", "Snowflake"]},
]

# ── Job title exclusion list ─────────────────────────────────────────────
# Jobs whose title contains any of these words (case-insensitive) are skipped
EXCLUDE_TITLE_KEYWORDS = ["senior", "sr.", "lead", "principal", "staff", "manager", "director", "head of"]

# ── Company exclusion list ───────────────────────────────────────────────
EXCLUDE_COMPANIES = ["Randstad", "Adecco", "ManpowerGroup", "Robert Half", "Hays"]

# ── Minimum keyword match score to even attempt AI scoring ───────────────
MIN_KEYWORD_SCORE = 0   # 0 = score everything; raise to e.g. 20 to skip poor matches
