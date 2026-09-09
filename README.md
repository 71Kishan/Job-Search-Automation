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
│ Batched tailored     │
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
- **Target-role filtering** to reduce unrelated roles such as sales, HR, finance, and other non-IT positions before AI processing.
- **Cross-portal deduplication** using normalized URLs and Company + Role combinations.
- **Historical deduplication** against jobs already present in the Google Sheet.
- **Priority ranking** toward System Administration, Networking, Infrastructure, and IT Operations roles.
- **Job-description extraction** before AI analysis, capped to a controlled input size.
- **Batched AI tailoring** with five jobs per standard Gemini request, reducing unnecessary API calls.
- **Optional premium processing** for a small number of top-priority jobs; disabled by default.
- **Application content generation** including email subjects, personalized cold emails, and resume bullets.
- **Strict anti-fabrication instructions** so generated content stays grounded in verified candidate information.
- **Google Sheets synchronization** that appends new rows without overwriting the existing tracker.
- **Windows Task Scheduler compatibility** for recurring automated runs.
- **Environment-based secret handling** so API credentials and private local configuration are not stored in source code.

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

The pipeline reads these values from environment variables:

```text
GEMINI_API_KEY                  Required Gemini API key
GOOGLE_SHEET_URL                Required private Google Sheet URL
JOB_SEARCH_BASE_DIR             Optional local working directory
GOOGLE_SERVICE_ACCOUNT_FILE     Optional service-account JSON path
GEMINI_MODEL                    Optional standard Gemini model override
PREMIUM_MODEL_ENABLED           Optional; defaults to false
PREMIUM_GEMINI_MODEL            Optional premium model override
```

If `JOB_SEARCH_BASE_DIR` is not set, the current working directory is used. If `GOOGLE_SERVICE_ACCOUNT_FILE` is not set, the script looks for `service_account.json` inside that base directory.

For Windows, the Gemini key can be stored as an environment variable:

```powershell
setx GEMINI_API_KEY "YOUR_API_KEY"
```

For the private Google Sheet, configure `GOOGLE_SHEET_URL` locally rather than committing it to the repository.

Restart the terminal after using `setx` so the new environment variable is available to Python.

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