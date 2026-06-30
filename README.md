# 🎯 Job Hunter — Local Python Replacement for n8n + Apify

Replaces the entire n8n workflow + Apify LinkedIn scraper with a **free, fully local Python app**.

**Zero ongoing cost** — uses only your existing AI model subscriptions (Google Gemini or Anthropic Claude).

---

## What This Does (mirrors your n8n workflow exactly)

```
Schedule (every 3 days)
  → Scrape LinkedIn jobs (no Apify — direct HTTP, free)
  → Normalize & deduplicate (FNV hash, same logic as n8n)
  → Filter unseen jobs (checks Google Sheets seen-hashes)
  → Bulk AI scoring (Gemini/Claude — keep jobs ≥55 score)
  → Per-job: extract JD structure + write cover letter
  → Save cover letter → Google Drive
  → Append row → Google Sheets (Applications tab)
  → Send Slack summary notification
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| pip | latest | `pip install --upgrade pip` |
| Google account | — | For Sheets + Drive |
| AI model | Gemini or Claude | You already have one |
| Slack workspace | optional | For notifications |

---

## Step 1 — Clone / Download the Project

```bash
# If you downloaded as a ZIP, unzip it:
unzip job_hunter.zip
cd job_hunter

# Or if you're creating from scratch, just cd into it:
cd job_hunter
```

---

## Step 2 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 3 — Google API Setup (Sheets + Drive)

You need a **Google Service Account** (free, takes ~5 minutes).

### 3a. Create a Google Cloud Project
1. Go to https://console.cloud.google.com
2. Click **"New Project"** → name it `job-hunter` → **Create**
3. Make sure this project is selected in the top dropdown

### 3b. Enable APIs
1. Go to **APIs & Services → Library**
2. Search and enable **"Google Sheets API"** → Enable
3. Search and enable **"Google Drive API"** → Enable

### 3c. Create a Service Account
1. Go to **APIs & Services → Credentials**
2. Click **"+ Create Credentials" → "Service Account"**
3. Name: `job-hunter-bot` → **Create and Continue** → **Done**
4. Click the service account email you just created
5. Go to **"Keys" tab → "Add Key" → "Create new key" → JSON**
6. Download the JSON file → rename it `google_credentials.json`
7. Place it in the `job_hunter/` project root

### 3d. Share your Google Sheet with the service account
1. Open your **Job Status Sheet** in Google Sheets
2. Click **Share** (top right)
3. Paste the service account email (looks like `job-hunter-bot@job-hunter-xxxxx.iam.gserviceaccount.com`)
4. Set role to **"Editor"** → **Send**

### 3e. Share your Google Drive cover_letters folder
1. Open **Google Drive** → find your `cover_letters` folder
2. Right-click → **Share** → paste the same service account email → **Editor** → **Done**

---

## Step 4 — Get Your Google Sheet & Drive IDs

### Sheet ID
From your sheet URL:
```
https://docs.google.com/spreadsheets/d/14kVC-tJ-81F-gteKSyyamSlD2uAnJXuL7_Rh2M56WBk/edit
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                         This is your SHEET_ID
```

### Drive Folder ID
From your cover_letters folder URL:
```
https://drive.google.com/drive/folders/1TK89z1QimJLnqCswAPF5DsQt1Ih1Kj__
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        This is your DRIVE_FOLDER_ID
```

### Resume File ID (master_resume.json on Drive)
From the file URL:
```
https://drive.google.com/file/d/1hpsr8CxxPuNQVyI-ci2n0hsAFfewEj6h/view
                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                 This is your RESUME_FILE_ID
```

---

## Step 5 — Configure `.env`

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set:

```env
# Google
GOOGLE_CREDENTIALS_PATH=google_credentials.json
SHEET_ID=14kVC-tJ-81F-gteKSyyamSlD2uAnJXuL7_Rh2M56WBk
DRIVE_FOLDER_ID=1TK89z1QimJLnqCswAPF5DsQt1Ih1Kj__
RESUME_FILE_ID=1hpsr8CxxPuNQVyI-ci2n0hsAFfewEj6h

# AI Model — pick ONE
AI_PROVIDER=gemini           # or: claude
GEMINI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here

# Slack (optional — leave blank to skip)
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C0BDN991ADS

# Scraper behaviour
MAX_ITEMS=200
PUBLISH_WITHIN=r604800       # r86400=24h, r604800=7d, r2592000=30d
AI_SCORE_THRESHOLD=55        # keep jobs with score >= this
```

### Where to get your Gemini API key
1. Go to https://aistudio.google.com/apikey
2. Click **"Create API key"** → copy it → paste into `.env`

### Where to get your Claude/Anthropic API key
1. Go to https://console.anthropic.com/settings/keys
2. Click **"Create Key"** → copy it → paste into `.env`

---

## Step 6 — Add Your Resume

Place your resume JSON file at:
```
job_hunter/data/master_resume.json
```

**Format:** the same `master_resume.json` you have on Google Drive. The pipeline downloads it automatically, but having it locally lets you test without Drive access.

If you don't have a JSON resume yet, run the extractor prompt:

```
Open any LLM and paste:

"Extract my resume into a structured JSON object with these top-level keys:
name, email, phone, linkedin, summary, experience (array of {company, title, start, end, achievements[]}),
skills[], education[]. Output ONLY raw JSON, no markdown."

Then paste your CV text.
```

Save the output as `data/master_resume.json`.

---

## Step 7 — Configure Search Targets

Edit `config/search_targets.py` to set your LinkedIn search URLs and resume keywords.

The file is pre-populated with your existing n8n workflow settings (Singapore, Dubai, Abu Dhabi, Sydney, Melbourne, Brisbane, Amsterdam, Rotterdam, Eindhoven — for ML Engineer, AI Engineer, NLP Engineer).

---

## Step 8 — Run It

### Single run (manual)
```bash
python main.py
```

### Run on a schedule (every 3 days, like your n8n trigger)
```bash
python scheduler.py
```

The scheduler runs in the foreground. To keep it running after you close the terminal:

**On Linux/Mac:**
```bash
nohup python scheduler.py > logs/scheduler.log 2>&1 &
```

**On Windows (PowerShell):**
```powershell
Start-Process python -ArgumentList "scheduler.py" -WindowStyle Hidden
```

**Or use cron (Linux/Mac):**
```bash
crontab -e
# Add this line (runs every 3 days at 7am):
0 7 */3 * * cd /path/to/job_hunter && python main.py >> logs/cron.log 2>&1
```

---

## Step 9 — Verify the Output

After running:

1. **Google Sheet** → check the `Applications` tab for new rows
2. **Google Drive** → check the `cover_letters` folder for `.md` files
3. **Slack** → check your `#jobn_search` channel (if configured)
4. **Local logs** → `logs/run_YYYY-MM-DD.log`

---

## Project Structure

```
job_hunter/
├── main.py                  # Entry point — orchestrates the full pipeline
├── scheduler.py             # Runs main.py every 3 days
├── requirements.txt
├── .env.example
├── .env                     # YOUR secrets (gitignored)
├── google_credentials.json  # YOUR service account key (gitignored)
│
├── config/
│   └── search_targets.py    # LinkedIn URLs + resume keywords
│
├── scrapers/
│   └── linkedin.py          # LinkedIn scraper (replaces Apify actor)
│
├── agents/
│   ├── scorer.py            # Bulk AI job scorer (replaces bulk_scorer_agent)
│   ├── jd_extractor.py      # JD structured extractor (replaces jd_extractor_agent)
│   └── cover_letter.py      # Cover letter writer (replaces cover_letter_writer_agent)
│
├── storage/
│   ├── sheets.py            # Google Sheets read/write
│   └── drive.py             # Google Drive upload/share
│
├── utils/
│   ├── hashing.py           # FNV-1a hash (same as n8n Code node)
│   ├── normalizer.py        # Field normalizer (same as n8n normalize_fields)
│   └── notify.py            # Slack notifications
│
├── data/
│   └── master_resume.json   # Your resume (gitignored)
│
├── cover_letters/           # Local copies of generated cover letters
└── logs/                    # Run logs
```

---

## Troubleshooting

**"403 Forbidden" from Google APIs**
→ Make sure you shared the Sheet and Drive folder with the service account email (Step 3d/3e).

**"No jobs found" every run**
→ LinkedIn sometimes blocks scrapers. Try running again in 30 minutes. The scraper uses rotating delays and public endpoints only.

**AI quota errors**
→ Gemini free tier has per-minute limits. The pipeline automatically adds delays between API calls. If you hit daily limits, set `MAX_ITEMS=50` in `.env`.

**Cover letter is empty**
→ Check that `data/master_resume.json` exists and is valid JSON. Run `python -c "import json; json.load(open('data/master_resume.json'))"` to validate.

**Duplicate jobs appearing in Sheet**
→ The FNV hash deduplication requires the `Job Hash` column to exist in your Sheet. Make sure the column header matches exactly: `Job Hash`.
