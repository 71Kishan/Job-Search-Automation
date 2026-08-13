# 🚀 AI-Powered Job Search & Cold Outreach Automation Pipeline

An automated Python pipeline built to streamline daily job discovery, candidate matching, and outreach generation. It scrapes IT Support and Cybersecurity job postings across major job portals (**Naukri**, **Indeed**, **LinkedIn**, and **WorkIndia**), leverages the **Google Gemini API** to rank matches and generate tailored application materials, and synchronizes actionable leads directly to a centralized **Google Sheets** tracker.

---

## 🌟 Key Features

- **Multi-Platform Scraping:** Automates browser sessions via Playwright to fetch daily IT/Cybersecurity listings across Naukri, Indeed, LinkedIn, and WorkIndia.
- **AI Matching & Analysis:** Uses Google Gemini LLM to analyze job descriptions against candidate profiles and assign relevancy scores.
- **Automated Content Drafts:** Automatically generates tailored cold outreach email subjects, concise 3-sentence application emails, and position-specific resume bullets.
- **Google Sheets Synchronization:** Deduplicates job listings and appends fresh leads in real-time via the Google Sheets API (`gspread`).
- **Scheduled Daily Runs:** Configured for automated daily execution via Windows Task Scheduler.

---

## 🛠️ Tech Stack

- **Language:** Python 3.10+
- **Browser Automation & Scraping:** Playwright, BeautifulSoup4, Requests
- **AI Integration:** Google Gemini API (`google-genai`)
- **Data & Storage:** Pandas, Google Sheets API (`gspread`)
- **Environment Management:** `python-dotenv`

---

## ⚙️ Project Structure

```text
Job-Search-Automation/
│
├── job_fetcher.py         # Main pipeline script (Scraping, AI analysis, Sheet sync)
├── requirements.txt       # Python package dependencies
├── .env.example           # Example environment variable template
├── .gitignore             # Excludes sensitive keys and service account credentials
└── README.md              # Project documentation
