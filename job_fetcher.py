import os
import time
import json
import re
from datetime import datetime

import pandas as pd
import requests
import gspread
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from google import genai


# ==============================================================================
# 1. DIRECTORY & CONFIGURATION
# ==============================================================================
BASE_DIR = r"LOCATION_OF_DIRECTORY"
CREDENTIALS_FILE = os.path.join(BASE_DIR, "service_account.json")
SPREADSHEET_URL = "GOOGLE_SHEET_URL"

# Store your Gemini key outside the script, e.g. as a Windows environment variable:
#   setx GEMINI_API_KEY "your-key-here"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it")

MAX_JOBS_PER_RUN = 15
JOB_DESCRIPTION_MAX_CHARS = 6000
REQUEST_TIMEOUT = 15
PAGE_TIMEOUT = 30000
AI_DELAY_SECONDS = 1.5
LOCATION = "Ahmedabad, Gujarat"
HEADLESS_BROWSER = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    )
}

# Search terms intentionally focus on roles aligned with the current profile.
# Cloud is retained as a direction, but the candidate profile does not claim
# production Azure/AWS/GCP experience unless it is actually present.
SEARCH_KEYWORDS = [
    "IT Technical Support",
    "Desktop Support",
    "System Administrator",
    "Network Support",
    "Network Engineer",
    "IT Infrastructure",
    "L2 Support",
]


# Keep this profile strictly grounded in the verified resume/projects.
CANDIDATE_PROFILE = """
Kishan Panchal - IT Systems & Infrastructure-focused IT Professional

Experience:
- 2+ years across technical support, systems troubleshooting, networking,
  infrastructure deployment, and technical operations.

Key outcomes:
- 90% First-Call Resolution (FCR)
- 95% Customer Satisfaction (CSAT)
- 25% increase in positive feedback
- 30% reduction in average team response time through workflow documentation
- 95% system performance efficiency in a prior support environment

Verified technical skills:
- Networking: TCP/IP, VLANs, DNS, DHCP, network troubleshooting,
  infrastructure cabling, bandwidth optimization
- Operating systems: Windows, Linux/Unix
- Automation: Python, Bash, Playwright, BeautifulSoup4, Requests, Pandas,
  SQL, Windows Task Scheduler
- Security: system hardening, endpoint protection, firewall auditing
- IT operations: Jira, ServiceNow, Microsoft 365, Git/GitHub

Hands-on projects:
- Cross-platform network traffic and latency analyzer in Python
- Windows/Linux system hardening and firewall audit utility in Python
- Python/AI job-search automation pipeline using Playwright, Google Gemini,
  Pandas, gspread, and Google Sheets

Career direction:
- Building deeper capability in System Administration and Network Engineering,
  with a long-term focus on cloud infrastructure, automation, and security.

Preferences:
- Open to remote opportunities and relocation for the right role.
""".strip()


# ==============================================================================
# 2. UTILITIES
# ==============================================================================
def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def unique_key(company, role):
    return (normalize_text(company).lower(), normalize_text(role).lower())


def sanitize_url(url):
    return normalize_text(url).split("?")[0]


def safe_json_loads(raw_text):
    """Parse model JSON even when a provider wraps it in Markdown fences."""
    text = normalize_text(raw_text)
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def get_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Store it as a Windows environment "
            "variable instead of putting the key inside the script."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


# ==============================================================================
# 3. JOB SCRAPERS
# ==============================================================================
def fetch_naukri_jobs(page, keyword, location):
    jobs = []
    url = (
        f"https://www.naukri.com/{keyword.lower().replace(' ', '-')}-jobs-in-"
        f"{location.split(',')[0].strip().lower()}?freshness=1"
    )
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(3500)
        scraped = page.evaluate(
            """() => Array.from(document.querySelectorAll(
                'div.srp-jobtuple-wrapper, article.jobTuple, [data-job-id]'
            )).map(card => {
                const titleElem = card.querySelector('a.title, [class*="title"]');
                const compElem = card.querySelector('a.comp-name, [class*="comp-name"]');
                return titleElem && titleElem.href ? {
                    title: titleElem.innerText.split('\\n')[0].trim(),
                    company: compElem ? compElem.innerText.trim() : 'N/A',
                    url: titleElem.href
                } : null;
            }).filter(Boolean);"""
        )
        for item in scraped:
            jobs.append({
                "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                "Company": normalize_text(item["company"]),
                "Role": normalize_text(item["title"]),
                "Location": location,
                "URL": sanitize_url(item["url"]),
            })
    except Exception as exc:
        print(f"  [Naukri Warn] {exc}")
    return jobs


def fetch_indeed_jobs(page, keyword, location):
    jobs = []
    url = (
        f"https://in.indeed.com/jobs?q={keyword.replace(' ', '+')}"
        f"&l={location.split(',')[0].strip()}"
    )
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(3000)
        scraped = page.evaluate(
            """() => Array.from(document.querySelectorAll(
                'div.cardOutline, .job_seen_beacon'
            )).map(card => {
                const titleElem = card.querySelector('h2.jobTitle span, [class*="jobTitle"]');
                const compElem = card.querySelector('[data-testid="company-name"], .companyName');
                const linkElem = card.querySelector('a.jcs-JobTitle, h2.jobTitle a');
                return titleElem && linkElem ? {
                    title: titleElem.innerText.trim(),
                    company: compElem ? compElem.innerText.trim() : 'N/A',
                    url: linkElem.href
                } : null;
            }).filter(Boolean);"""
        )
        for item in scraped:
            jobs.append({
                "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                "Company": normalize_text(item["company"]),
                "Role": normalize_text(item["title"]),
                "Location": location,
                "URL": sanitize_url(item["url"]),
            })
    except Exception as exc:
        print(f"  [Indeed Warn] {exc}")
    return jobs


def fetch_workindia_jobs(page, keyword, location):
    jobs = []
    city_slug = location.split(",")[0].strip().lower()
    url = f"https://www.workindia.in/jobs/{keyword.lower().replace(' ', '-')}-jobs-in-{city_slug}/"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(3000)
        scraped = page.evaluate(
            """() => Array.from(document.querySelectorAll(
                '.job-card, [class*="JobCard"]'
            )).map(card => {
                const titleElem = card.querySelector('h3, [class*="title"]');
                const compElem = card.querySelector('.company-name, [class*="company"]');
                const linkElem = card.querySelector('a');
                return titleElem && linkElem ? {
                    title: titleElem.innerText.trim(),
                    company: compElem ? compElem.innerText.trim() : 'N/A',
                    url: linkElem.href.startsWith('http')
                        ? linkElem.href
                        : 'https://www.workindia.in' + linkElem.href
                } : null;
            }).filter(Boolean);"""
        )
        for item in scraped:
            jobs.append({
                "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                "Company": normalize_text(item["company"]),
                "Role": normalize_text(item["title"]),
                "Location": location,
                "URL": sanitize_url(item["url"]),
            })
    except Exception as exc:
        print(f"  [WorkIndia Warn] {exc}")
    return jobs


def fetch_linkedin_jobs(keyword, location):
    jobs = []
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
        f"keywords={keyword.replace(' ', '%20')}&location={location.split(',')[0].strip()}"
        "&f_TPR=r86400&start=0"
    )
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for card in soup.find_all("li"):
            title = card.find("h3")
            company = card.find("h4")
            link = card.find("a", class_="base-card__full-link")
            if title and company and link:
                jobs.append({
                    "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                    "Company": normalize_text(company.text),
                    "Role": normalize_text(title.text),
                    "Location": location,
                    "URL": sanitize_url(link.get("href", "")),
                })
    except Exception as exc:
        print(f"  [LinkedIn Warn] {exc}")
    return jobs


def scrape_job_description(url):
    """Fetch and extract the most useful job-description text available."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        selectors = [
            ("div", "show-more-less-html__markup"),  # LinkedIn
            ("div", "job-desc"),                      # Naukri
        ]
        for tag_name, class_name in selectors:
            desc_div = soup.find(tag_name, class_=class_name)
            if desc_div:
                text = desc_div.get_text(separator=" ", strip=True)
                if text:
                    return normalize_text(text)[:JOB_DESCRIPTION_MAX_CHARS]

        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
        return normalize_text(text)[:JOB_DESCRIPTION_MAX_CHARS] or "Description not available."
    except Exception:
        return "Description not available."


# ==============================================================================
# 4. AI PROCESSING
# ==============================================================================
def build_ai_prompt(job, job_description):
    return f"""
You are an expert technical recruiter and resume writer.

Target role: {job['Role']}
Company: {job['Company']}
Location: {job['Location']}

CANDIDATE BACKGROUND
{CANDIDATE_PROFILE}

JOB DESCRIPTION
{job_description}

TASK
1. Identify the 3 most important technical requirements in the job description.
2. Write exactly 3 resume bullets that connect the candidate's VERIFIED experience
   to those requirements.
3. Write a concise, professional cold email for the same opportunity.
4. Write a clear email subject line.

CRITICAL RULES
- Never invent experience, tools, certifications, employers, responsibilities,
  cloud platforms, protocols, metrics, or technologies not present in the
  Candidate Background.
- Only use a job-description keyword when the candidate genuinely matches it.
- Do not imply production AWS, Azure, or GCP experience unless the background
  explicitly supports it.
- Do not claim OSPF/BGP expertise unless the background explicitly supports it.
- Prefer concrete actions and verified outcomes over generic phrases.
- Vary the sentence structure across the three resume bullets.
- Keep each resume bullet concise and resume-ready.
- Do not mention that the candidate is "learning" a technology inside a resume bullet.
- The cold email should be around 100 words and should not sound mass-generated.

RETURN ONLY VALID JSON in this exact structure:
{{
  "top_requirements": ["Requirement 1", "Requirement 2", "Requirement 3"],
  "email_subject": "...",
  "cold_email": "...",
  "resume_bullets": "• Bullet 1\\n• Bullet 2\\n• Bullet 3"
}}
""".strip()


def generate_tailored_content(client, job, job_description):
    prompt = build_ai_prompt(job, job_description)
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return safe_json_loads(response.text)


# ==============================================================================
# 5. GOOGLE SHEETS SYNC + SMART DEDUPLICATION
# ==============================================================================
def process_and_sync(df):
    if not os.path.exists(CREDENTIALS_FILE):
        print("[System] service_account.json missing. Skipping sheet sync.")
        return

    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    worksheet = gc.open_by_url(SPREADSHEET_URL).sheet1

    all_sheet_rows = worksheet.get_all_values()
    existing_urls = set()
    existing_jobs_set = set()

    if len(all_sheet_rows) > 1:
        for row in all_sheet_rows[1:]:
            if len(row) >= 3:
                url_val = row[4].strip().lower() if len(row) > 4 else ""
                comp_val = row[1].strip().lower() if len(row) > 1 else ""
                role_val = row[2].strip().lower() if len(row) > 2 else ""

                if url_val:
                    existing_urls.add(sanitize_url(url_val))
                if comp_val and role_val:
                    existing_jobs_set.add((comp_val, role_val))

    df = df.copy()
    df["URL"] = df["URL"].map(sanitize_url)
    df = df.drop_duplicates(subset=["URL"])
    df["temp_comp"], df["temp_role"] = zip(
        *df.apply(lambda row: unique_key(row["Company"], row["Role"]), axis=1)
    )

    filtered_jobs = []
    seen_run_keys = set()

    for _, row in df.iterrows():
        url_key = row["URL"].lower()
        job_key = (row["temp_comp"], row["temp_role"])
        if url_key in existing_urls or job_key in existing_jobs_set or job_key in seen_run_keys:
            continue
        seen_run_keys.add(job_key)
        filtered_jobs.append(row)

    if not filtered_jobs:
        print("[System] No new unique jobs found today. Everything is already tracked!")
        return

    new_df = pd.DataFrame(filtered_jobs).head(MAX_JOBS_PER_RUN)
    client = get_gemini_client()
    rows_to_append = []

    print(f"\n[AI] Tailoring {len(new_df)} genuinely new IT jobs...")

    for _, job in new_df.iterrows():
        try:
            print(f"  Processing: {job['Company']} - {job['Role']}...")
            job_description = scrape_job_description(job["URL"])
            result = generate_tailored_content(client, job, job_description)

            rows_to_append.append([
                job["Date Applied"],
                job["Company"],
                job["Role"],
                job["Location"],
                job["URL"],
                result.get("email_subject", ""),
                result.get("cold_email", ""),
                result.get("resume_bullets", ""),
                "New",
                "Pending",
            ])

            time.sleep(AI_DELAY_SECONDS)

        except Exception as exc:
            print(f"  [AI Warn] Failed to process {job['Company']} - {job['Role']}: {exc}")

    if rows_to_append:
        worksheet.append_rows(rows_to_append)
        print(f"[Success] Appended {len(rows_to_append)} tailored jobs to Master Sheet.")
    else:
        print("[System] No jobs were successfully processed by AI.")


# ==============================================================================
# 6. MAIN
# ==============================================================================
def main():
    print("=" * 72)
    print("KISHAN PANCHAL | IT JOB SEARCH AUTOMATION")
    print("Systems • Networking • Automation • Security")
    print("=" * 72)

    all_jobs = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=HEADLESS_BROWSER)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])

        for keyword in SEARCH_KEYWORDS:
            print(f"\nSearching: {keyword}")
            all_jobs.extend(fetch_naukri_jobs(page, keyword, LOCATION))
            all_jobs.extend(fetch_indeed_jobs(page, keyword, LOCATION))
            all_jobs.extend(fetch_workindia_jobs(page, keyword, LOCATION))
            all_jobs.extend(fetch_linkedin_jobs(keyword, LOCATION))

        browser.close()

    if not all_jobs:
        print("[System] No jobs found across any platform.")
        return

    df = pd.DataFrame(all_jobs)
    df["URL"] = df["URL"].map(sanitize_url)
    df = df.drop_duplicates(subset=["URL"])

    os.makedirs(BASE_DIR, exist_ok=True)
    csv_path = os.path.join(
        BASE_DIR,
        f"it_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )
    df.to_csv(csv_path, index=False)
    print(f"[System] Raw job results saved to: {csv_path}")

    process_and_sync(df)


if __name__ == "__main__":
    main()
