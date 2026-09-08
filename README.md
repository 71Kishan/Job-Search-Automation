# AI-Powered Job Search & Cold Outreach Automation Pipeline

A Python automation pipeline for discovering IT/Cybersecurity job postings, matching opportunities against a candidate profile, generating tailored application content, and synchronizing actionable leads to Google Sheets.

## Workflow

```text
Job Portals
   ↓
Playwright / Requests / BeautifulSoup
   ↓
Job Discovery & Deduplication
   ↓
Google Gemini Analysis
   ↓
Relevance Scoring + Tailored Content
   ↓
Google Sheets Tracking
```

## Key Features

- **Multi-platform discovery:** Automates browser sessions and requests across Naukri, Indeed, LinkedIn, and WorkIndia.
- **Job-description extraction:** Retrieves available job-description content for downstream analysis.
- **AI matching:** Uses Google Gemini to analyze job descriptions against a structured candidate profile and generate relevance-focused output.
- **Application-content generation:** Produces tailored email subjects, concise cold emails, and position-specific resume bullets.
- **Deduplication:** Filters previously tracked jobs by URL and Company + Role combinations before processing.
- **Google Sheets synchronization:** Appends actionable leads and generated application material to a centralized tracker.
- **Scheduled execution:** Designed for daily Windows Task Scheduler runs.

## Tech Stack

**Python 3.10+ · Playwright · BeautifulSoup4 · Requests · Pandas · Google Gemini API · gspread · Google Sheets API · python-dotenv · Windows Task Scheduler**

## Project Structure

```text
Job-Search-Automation/
├── job_fetcher.py         # Scraping, analysis, deduplication, and sheet sync
├── requirements.txt       # Python dependencies
├── .env.example           # Environment-variable template
├── .gitignore             # Excludes sensitive credentials
└── README.md              # Project documentation
```

## Security Note

Credentials and API keys are kept outside source control through environment/configuration files and are excluded from commits via `.gitignore`.
