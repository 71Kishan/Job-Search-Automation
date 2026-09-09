# AI-Powered IT Job Search & Application Automation

A Python automation pipeline that discovers fresh IT job opportunities, filters out non-target roles, removes duplicates across job portals and previous runs, uses Google Gemini to tailor application content, and synchronizes the results to Google Sheets.

The project is built around Kishan Panchal's current career direction: **System Administration, Network Engineering, IT Infrastructure, Automation, and Security**.

## What the pipeline does

```text
┌──────────────────────┐
│  Job Portals         │
│  Naukri / Indeed     │
│  LinkedIn / WorkIndia│
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Job discovery        │
│ Playwright / Requests│
│ BeautifulSoup        │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Normalize & dedupe   │
│ URL + Company/Role   │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Target-role filter   │
│ Systems / Networking │
│ Infrastructure / IT  │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Gemini analysis      │
│ Relevance + tailored │
│ application content  │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Google Sheets        │
│ Central application  │
│ tracker              │
└──────────────────────┘
```

## Key capabilities

- **Multi-platform job discovery** across Naukri, Indeed, LinkedIn, and WorkIndia.
- **Fresh-job collection** focused on the configured search keywords and location.
- **Target-role filtering** to reduce unrelated roles such as sales, HR, finance, and other non-IT positions.
- **Cross-portal deduplication** using normalized URLs and Company + Role combinations.
- **Historical deduplication** against jobs already present in the Google Sheet.
- **Job-description extraction** before AI analysis.
- **AI-assisted tailoring** using a structured candidate profile and strict anti-fabrication instructions.
- **Application content generation** including email subjects, personalized cold emails, and resume bullets.
- **Google Sheets synchronization** for centralized job tracking and follow-up status.
- **Windows Task Scheduler compatibility** for recurring automated runs.
- **Environment-based secret handling** so API credentials are not stored in source code.

## AI safety / accuracy rules

The AI prompt is deliberately constrained to keep generated application content grounded in verified candidate information.

The pipeline is instructed **not to invent**:

- employers or job responsibilities
- certifications
- performance metrics
- cloud experience
- networking protocols or expertise
- tools or technologies not supported by the candidate profile

This is important because the purpose of the AI layer is to **tailor genuine experience to a job**, not manufacture qualifications.

## Tech stack

**Python · Playwright · Requests · BeautifulSoup4 · Pandas · Google Gemini API · gspread · Google Sheets API · Windows Task Scheduler**

The Gemini integration uses Google's official `google-genai` Python SDK and the Interactions API.

## Project structure

```text
Job-Search-Automation/
├── job_fetcher.py      # Main discovery, filtering, AI, and Sheets pipeline
├── requirements.txt    # Python dependencies
├── .gitignore          # Sensitive/local files excluded from Git
├── job_fetcher.png     # Project reference image
└── README.md           # Project documentation
```

## Configuration

The repository intentionally does **not** contain personal credentials, Google service-account files, or Gemini API keys.

Configure the following on the local machine instead:

```text
GEMINI_API_KEY
GEMINI_MODEL       (optional)
BASE_DIR           (local configuration)
SPREADSHEET_URL    (local configuration)
service_account.json
```

For Windows, the Gemini key can be stored as an environment variable:

```powershell
setx GEMINI_API_KEY "YOUR_API_KEY"
```

Restart the terminal after using `setx` so the new environment variable is available to Python.

Google's current Gemini documentation recommends the official `google-genai` SDK and environment-variable based API-key handling.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

## Running the pipeline

```powershell
python job_fetcher.py
```

The normal workflow is designed to be run manually or through Windows Task Scheduler.

## Security

Sensitive local files are excluded through `.gitignore`, including:

- `service_account.json`
- `.env`
- generated CSV files
- Python cache files

Never commit API keys, service-account credentials, private Google Sheet URLs, or other secrets to the repository.

## Project purpose

This project is both a practical personal automation system and a hands-on infrastructure/automation portfolio project. It demonstrates the ability to combine web automation, data processing, API integration, AI-assisted workflows, scheduling, and secure configuration into one end-to-end system.
