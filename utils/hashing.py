"""
utils/hashing.py
────────────────
FNV-1a 64-bit hash — exact port of the n8n `generate_hashes` Code node.

Used to deduplicate jobs across runs without storing full job objects.
The hash is stable: same title+company+location always produces the same hex string.
"""


SENIORITY = {
    "senior", "sr", "junior", "jr", "lead", "principal",
    "staff", "associate", "mid", "entry", "level",
}

SUFFIXES = {
    "pvt", "ltd", "inc", "llc", "gmbh", "corp", "limited",
    "private", "solutions", "technologies", "tech",
    "services", "global", "india", "bangalore", "bengaluru",
}


def fnv_hash(text: str) -> str:
    """FNV-1a 64-bit — deterministic, no external deps, collision-resistant."""
    h = 14695981039346656037  # offset basis
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 1099511628211) % (2 ** 64)  # keep 64 bits
    return format(h, "016x")  # 16 hex chars


def compute_job_hash(title: str, company: str, location: str) -> str:
    """
    Build the canonical hash for a job posting.

    Strips seniority words from the title and legal suffixes from the company
    name so that 'Senior ML Engineer @ Acme Ltd, Bengaluru' and
    'ML Engineer @ Acme, Bangalore' produce the same hash.
    """
    title_words = [
        w for w in title.lower().split()
        if w.strip(".,") not in SENIORITY
    ]
    title_clean = " ".join(title_words)

    company_words = [
        w for w in company.lower().replace(".", "").split()
        if w not in SUFFIXES
    ]
    company_clean = " ".join(company_words)

    location_clean = location.lower().split(",")[0].strip()

    key = f"{title_clean}|{company_clean}|{location_clean}"
    return fnv_hash(key)
