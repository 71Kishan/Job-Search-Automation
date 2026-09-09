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
# Local paths and the Google Sheet are supplied through environment variables so
# the public repository contains no personal machine paths or private URLs.
BASE_DIR = os.getenv("JOB_SEARCH_BASE_DIR", os.getcwd())
CREDENTIALS_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    os.path.join(BASE_DIR, "service_account.json"),
)
SPREADSHEET_URL = os.getenv("GOOGLE_SHEET_URL", "")

# Store your Gemini key outside the script, e.g. as a Windows environment variable:
#   setx GEMINI_API_KEY "your-key-here"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
PREMIUM_MODEL_ENABLED = os.getenv("PREMIUM_MODEL_ENABLED", "false").strip().lower() == "true"
PREMIUM_MODEL_NAME = os.getenv("PREMIUM_GEMINI_MODEL", "gemini-3.8-flash")
AI_MAX_RETRIES = 3
AI_BASE_DELAY_SECONDS = 5
MAX_JOBS_PER_RUN = 10
AI_BATCH_SIZE = 5
JOB_DESCRIPTION_MAX_CHARS = 6000
PREMIUM_JOBS_PER_RUN = 2
REQUEST_TIMEOUT = 10
PAGE_TIMEOUT = 25000
AI_DELAY_SECONDS = 1
LOCATION = "Ahmedabad, Gujarat"
HEADLESS_BROWSER = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    )
}

SEARCH_KEYWORDS = [
    "IT Technical Support",
    "Technical Support Engineer",
    "Desktop Support",
    "Service Desk",
    "System Administrator",
    "Systems Support",
    "Network Support",
    "Network Engineer",
    "Network Administrator",
    "IT Infrastructure",
    "Infrastructure Support",
    "NOC Engineer",
    "IT Operations",
    "Windows Administrator",
    "Linux Administrator",
]

CANDIDATE_PROFILE = """
Kishan Panchal - IT Systems & Infrastructure-focused IT Professional
- Experience: 2+ years across technical support, systems troubleshooting, networking,
  infrastructure deployment, and technical operations.
- Key Metrics: 95% CSAT, 90% First-Call Resolution, 25% increase in positive feedback,
  30% reduction in average response time, 95% system performance efficiency.
- Networking: TCP/IP, VLANs, DNS, DHCP, network troubleshooting, infrastructure cabling,
  bandwidth optimization.
- OS: Windows, Linux/Unix, GrapheneOS.
- Automation: Python, BASH, Playwright, BeautifulSoup4, Requests, Pandas, SQL,
  Windows Task Scheduler.
- Security: System Hardening, Endpoint Protection, firewall auditing.
- IT Operations: Jira, ServiceNow, M365, Git/GitHub.
- Projects: Network Analyzer, System Hardening Auditor, Python/AI Job Search Automation.
- Career direction: System Administration and Network Engineering, with long-term focus on
  cloud infrastructure, automation, and security.
- Preferences: Open to remote roles and relocation for the right opportunity.
"""


# ==============================================================================
# 2. UTILITIES
# ==============================================================================
def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_company(value):
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\b(private|pvt|limited|ltd|incorporated|inc|llp|llc|corporation|corp)\b", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def canonical_role(value):
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\b(ahmedabad|gandhinagar|gujarat|india|remote|hybrid|full time|full-time|part time|part-time)\b", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def job_key(company, role):
    return (canonical_company(company), canonical_role(role))


def sanitize_url(url):
    url = normalize_text(url)
    return url.split("?", 1)[0].split("#", 1)[0]


REJECT_TITLE_PATTERNS = [
    r"\bsales\b", r"\bbusiness development\b", r"\baccount executive\b",
    r"\baccount manager\b", r"\brelationship manager\b", r"\btele[- ]?sales\b",
    r"\bsales representative\b", r"\bsales executive\b", r"\bmarketing\b",
    r"\brecruiter\b", r"\btalent acquisition\b", r"\bhr executive\b",
    r"\bhuman resources\b", r"\baccountant\b", r"\baccounts executive\b",
    r"\bfinance\b", r"\bmechanical engineer\b", r"\bcivil engineer\b",
    r"\bdata entry\b", r"\btelecaller\b",
]

TECHNICAL_TITLE_SIGNALS = [
    r"\bit\b", r"\btechnical\b", r"\bsystem\b", r"\bsystems\b",
    r"\bnetwork\b", r"\binfrastructure\b", r"\bnoc\b", r"\bdesktop\b",
    r"\bhelp desk\b", r"\bservice desk\b", r"\badministrator\b",
    r"\badmin\b", r"\bengineer\b", r"\boperations\b", r"\btechnician\b",
    r"\bhardware\b", r"\bsecurity\b", r"\bsupport\b", r"\bserver\b",
    r"\bwindows\b", r"\blinux\b",
]


def is_relevant_job_title(title):
    normalized = normalize_text(title).lower()
    if not normalized:
        return False
    if any(re.search(pattern, normalized) for pattern in REJECT_TITLE_PATTERNS):
        return False
    return any(re.search(pattern, normalized) for pattern in TECHNICAL_TITLE_SIGNALS)


def job_priority_score(row):
    title = normalize_text(row.get("Role", "")).lower()
    score = 0
    if re.search(r"\bsystem(s)? administrator\b|\bwindows administrator\b|\blinux administrator\b", title): score += 40
    if re.search(r"\bnetwork engineer\b|\bnetwork administrator\b|\bnetwork support\b|\bnoc\b", title): score += 38
    if re.search(r"\binfrastructure\b|\bit operations\b|\bsystems support\b", title): score += 32
    if re.search(r"\bdesktop support\b|\btechnical support\b|\bservice desk\b|\bl2 support\b", title): score += 22
    if re.search(r"\btechnician\b|\bhardware\b", title): score += 10
    if re.search(r"\bcloud\b", title): score += 8
    if re.search(r"\bsecurity\b", title): score += 6
    return score


def parse_ai_json(raw_text):
    text = normalize_text(raw_text).replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


# ==============================================================================
# 3. SCRAPERS
# ==============================================================================
def fetch_naukri_jobs(page, keyword, location):
    jobs = []
    url = f"https://www.naukri.com/{keyword.lower().replace(' ', '-')}-jobs-in-{location.split(',')[0].strip().lower()}?freshness=1"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(3500)
        scraped = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('div.srp-jobtuple-wrapper, article.jobTuple, [data-job-id]')).map(card => {
                const titleElem = card.querySelector('a.title, [class*="title"]');
                const compElem = card.querySelector('a.comp-name, [class*="comp-name"]');
                return titleElem && titleElem.href ? {title: titleElem.innerText.split('\\n')[0].trim(), company: compElem ? compElem.innerText.trim() : 'N/A', url: titleElem.href} : null;
            }).filter(Boolean);
        }""")
        for item in scraped:
            jobs.append({"Date Applied": datetime.now().strftime("%Y-%m-%d"), "Company": item["company"], "Role": item["title"], "Location": location, "URL": item["url"]})
    except Exception as e:
        print(f"  [Naukri Warn] {e}")
    return jobs


def fetch_indeed_jobs(page, keyword, location):
    jobs = []
    url = f"https://in.indeed.com/jobs?q={keyword.replace(' ', '+')}&l={location.split(',')[0].strip()}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(3000)
        scraped = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('div.cardOutline, .job_seen_beacon')).map(card => {
                const titleElem = card.querySelector('h2.jobTitle span, [class*="jobTitle"]');
                const compElem = card.querySelector('[data-testid="company-name"], .companyName');
                const linkElem = card.querySelector('a.jcs-JobTitle, h2.jobTitle a');
                return titleElem && linkElem ? {title: titleElem.innerText.trim(), company: compElem ? compElem.innerText.trim() : 'N/A', url: linkElem.href} : null;
            }).filter(Boolean);
        }""")
        for item in scraped:
            jobs.append({"Date Applied": datetime.now().strftime("%Y-%m-%d"), "Company": item["company"], "Role": item["title"], "Location": location, "URL": item["url"]})
    except Exception as e:
        print(f"  [Indeed Warn] {e}")
    return jobs


def fetch_workindia_jobs(page, keyword, location):
    jobs = []
    city_slug = location.split(',')[0].strip().lower()
    url = f"https://www.workindia.in/jobs/{keyword.lower().replace(' ', '-')}-jobs-in-{city_slug}/"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(3000)
        scraped = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.job-card, [class*="JobCard"]')).map(card => {
                const titleElem = card.querySelector('h3, [class*="title"]');
                const compElem = card.querySelector('.company-name, [class*="company"]');
                const linkElem = card.querySelector('a');
                return titleElem && linkElem ? {title: titleElem.innerText.trim(), company: compElem ? compElem.innerText.trim() : 'N/A', url: linkElem.href.startsWith('http') ? linkElem.href : 'https://www.workindia.in' + linkElem.href} : null;
            }).filter(Boolean);
        }""")
        for item in scraped:
            jobs.append({"Date Applied": datetime.now().strftime("%Y-%m-%d"), "Company": item["company"], "Role": item["title"], "Location": location, "URL": item["url"]})
    except Exception as e:
        print(f"  [WorkIndia Warn] {e}")
    return jobs


def fetch_linkedin_jobs(keyword, location):
    jobs = []
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keyword.replace(' ', '%20')}&location={location.split(',')[0].strip()}&f_TPR=r86400&start=0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for card in soup.find_all("li"):
                title, comp, link = card.find("h3"), card.find("h4"), card.find("a", class_="base-card__full-link")
                if title and comp and link:
                    jobs.append({"Date Applied": datetime.now().strftime("%Y-%m-%d"), "Company": comp.text.strip(), "Role": title.text.strip(), "Location": location, "URL": link["href"].split("?")[0]})
    except Exception as e:
        print(f"  [LinkedIn Warn] {e}")
    return jobs


def scrape_job_description(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(res.text, "html.parser")
        if "linkedin.com" in url:
            desc_div = soup.find("div", class_="show-more-less-html__markup")
            if desc_div:
                return desc_div.get_text(separator=" ", strip=True)[:JOB_DESCRIPTION_MAX_CHARS]
        elif "naukri.com" in url:
            desc_div = soup.find("div", class_="job-desc")
            if desc_div:
                return desc_div.get_text(separator=" ", strip=True)[:JOB_DESCRIPTION_MAX_CHARS]
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text(strip=True) for p in paragraphs])
        return text[:JOB_DESCRIPTION_MAX_CHARS] if text else "Description not available."
    except Exception:
        return "Description not available."


# ==============================================================================
# 4. AI PROCESSING
# ==============================================================================
def build_batch_prompt(jobs):
    job_blocks = []
    for idx, job in enumerate(jobs, start=1):
        job_blocks.append(
            f"JOB {idx}\n"
            f"Company: {job['Company']}\n"
            f"Role: {job['Role']}\n"
            f"Location: {job['Location']}\n"
            f"URL: {job['URL']}\n"
            f"Job Description:\n{job.get('Job Description', 'Description not available.')[:JOB_DESCRIPTION_MAX_CHARS]}"
        )

    return f"""You are an expert technical recruiter and resume writer.

CANDIDATE BACKGROUND:
{CANDIDATE_PROFILE}

PROCESS ALL {len(jobs)} JOBS BELOW IN THIS SINGLE REQUEST.

{chr(10).join(job_blocks)}

For EACH job:
1. Identify the 3 most important requirements.
2. Write exactly 3 resume bullets connecting VERIFIED candidate experience to those requirements.
3. Write one concise personalized cold email.
4. Write one email subject.

CRITICAL RULES:
- Never invent experience, tools, certifications, employers, responsibilities, metrics,
  protocols, cloud platforms, or technologies.
- Only use a job-description keyword when the candidate genuinely matches it.
- Do not claim AWS, Azure, GCP, OSPF, or BGP expertise unless explicitly supported.
- Prefer concrete actions and verified metrics.
- Do not fabricate missing job-description details.
- Keep bullets concise, varied, and ready to paste into a resume.
- Personalize each email to the actual company and role.
- Return exactly one JSON object with a "jobs" array containing exactly {len(jobs)} items,
  in the same order as the input jobs.
- Return ONLY valid JSON. No Markdown fences and no commentary.

JSON format:
{{
  "jobs": [
    {{
      "top_requirements": ["Requirement 1", "Requirement 2", "Requirement 3"],
      "email_subject": "...",
      "cold_email": "...",
      "resume_bullets": "• Bullet 1\\n• Bullet 2\\n• Bullet 3"
    }}
  ]
}}"""


def generate_batch_with_retry(client, jobs, model_name):
    last_error = None
    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            print(f"    [AI] {model_name} | {len(jobs)} job batch | attempt {attempt}/{AI_MAX_RETRIES}...")
            interaction = client.interactions.create(model=model_name, input=build_batch_prompt(jobs))
            output_text = getattr(interaction, "output_text", "")
            if not output_text:
                raise RuntimeError("Gemini returned an empty response.")
            data = parse_ai_json(output_text)
            results = data.get("jobs") if isinstance(data, dict) else None
            if not isinstance(results, list) or len(results) != len(jobs):
                count = len(results) if isinstance(results, list) else 0
                raise RuntimeError(f"Gemini returned {count} results for {len(jobs)} jobs.")
            return results
        except Exception as exc:
            last_error = exc
            msg = str(exc).upper()
            transient = any(code in msg for code in ("429", "500", "502", "503", "504", "INTERNAL", "UNAVAILABLE", "DEADLINE", "RESOURCE EXHAUSTED"))
            if not transient or attempt == AI_MAX_RETRIES:
                raise
            delay = AI_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"    [AI Retry] Temporary Gemini/API error; waiting {delay}s...")
            time.sleep(delay)
    raise last_error


# ==============================================================================
# 5. GOOGLE SHEETS SYNC + SMART DEDUPLICATION
# ==============================================================================
def process_and_sync(df):
    if not os.path.exists(CREDENTIALS_FILE):
        return print("[System] service_account.json missing. Skipping sheet sync.")

    if not SPREADSHEET_URL:
        raise RuntimeError("GOOGLE_SHEET_URL is not set. Store your private Google Sheet URL as an environment variable.")

    if not GEMINI_API_KEY:
        raise RuntimeError('GEMINI_API_KEY is not set. Store it as a Windows environment variable.')

    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    worksheet = gc.open_by_url(SPREADSHEET_URL).sheet1

    all_sheet_rows = worksheet.get_all_values()
    existing_urls = set()
    existing_jobs_set = set()
    for row in all_sheet_rows[1:]:
        company = row[1] if len(row) > 1 else ""
        role = row[2] if len(row) > 2 else ""
        url = row[4] if len(row) > 4 else ""
        if url:
            existing_urls.add(sanitize_url(url).lower())
        if company and role:
            existing_jobs_set.add(job_key(company, role))

    df = df.copy()
    df["URL"] = df["URL"].map(sanitize_url)
    df = df.drop_duplicates(subset=["URL"])

    before_filter = len(df)
    df = df[df["Role"].map(is_relevant_job_title)].copy()
    rejected = before_filter - len(df)
    if rejected:
        print(f"[Filter] Removed {rejected} non-target roles (sales, HR, finance, unrelated roles, etc.).")

    filtered_jobs = []
    seen_urls_this_run = set()
    seen_jobs_this_run = set()
    for _, row in df.iterrows():
        url_key = row["URL"].lower()
        role_key = job_key(row["Company"], row["Role"])
        if url_key in existing_urls or role_key in existing_jobs_set or url_key in seen_urls_this_run or role_key in seen_jobs_this_run:
            continue
        seen_urls_this_run.add(url_key)
        seen_jobs_this_run.add(role_key)
        filtered_jobs.append(row.to_dict())

    if not filtered_jobs:
        return print("[System] No new relevant jobs found. Everything is already tracked or filtered out!")

    filtered_jobs.sort(key=job_priority_score, reverse=True)
    selected_jobs = filtered_jobs[:MAX_JOBS_PER_RUN]
    print(f"\n[System] Selected {len(selected_jobs)} top jobs from {len(filtered_jobs)} unique relevant jobs.")

    for job in selected_jobs:
        job["Job Description"] = scrape_job_description(job["URL"])

    client = genai.Client(api_key=GEMINI_API_KEY)
    rows_to_append = []

    premium_count = min(PREMIUM_JOBS_PER_RUN, len(selected_jobs)) if PREMIUM_MODEL_ENABLED else 0
    premium_jobs = selected_jobs[:premium_count]
    standard_jobs = selected_jobs[premium_count:]

    def append_results(jobs, results):
        if len(jobs) != len(results):
            raise RuntimeError("Gemini result count does not match batch size.")
        for job, result in zip(jobs, results):
            rows_to_append.append([
                job["Date Applied"], job["Company"], job["Role"], job["Location"], job["URL"],
                result.get("email_subject", ""), result.get("cold_email", ""),
                result.get("resume_bullets", ""), "New", "Pending",
            ])

    for start_idx in range(0, len(premium_jobs), AI_BATCH_SIZE):
        batch = premium_jobs[start_idx:start_idx + AI_BATCH_SIZE]
        print(f"  [Priority] {len(batch)} top job(s) -> {PREMIUM_MODEL_NAME}")
        append_results(batch, generate_batch_with_retry(client, batch, PREMIUM_MODEL_NAME))
        time.sleep(AI_DELAY_SECONDS)

    for start_idx in range(0, len(standard_jobs), AI_BATCH_SIZE):
        batch = standard_jobs[start_idx:start_idx + AI_BATCH_SIZE]
        append_results(batch, generate_batch_with_retry(client, batch, MODEL_NAME))
        time.sleep(AI_DELAY_SECONDS)

    if rows_to_append:
        worksheet.append_rows(rows_to_append)
        standard_batches = (len(standard_jobs) + AI_BATCH_SIZE - 1) // AI_BATCH_SIZE if standard_jobs else 0
        premium_batches = (len(premium_jobs) + AI_BATCH_SIZE - 1) // AI_BATCH_SIZE if premium_jobs else 0
        print(f"[Success] Appended {len(rows_to_append)} tailored jobs after the last populated row.")
        print(f"[System] Gemini requests used: {standard_batches} standard batch(es) + {premium_batches} premium batch(es).")
    else:
        print("[System] No jobs were successfully processed by AI.")


def main():
    all_jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADLESS_BROWSER)
        page = browser.new_page()
        for kw in SEARCH_KEYWORDS:
            print(f"Searching keyword: {kw}")
            all_jobs.extend(fetch_naukri_jobs(page, kw, LOCATION))
            all_jobs.extend(fetch_indeed_jobs(page, kw, LOCATION))
            all_jobs.extend(fetch_workindia_jobs(page, kw, LOCATION))
            all_jobs.extend(fetch_linkedin_jobs(kw, LOCATION))
        browser.close()

    if all_jobs:
        df = pd.DataFrame(all_jobs)
        df.to_csv(os.path.join(BASE_DIR, f"it_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"), index=False)
        process_and_sync(df)
    else:
        print("[System] No jobs found across any platform.")


if __name__ == "__main__":
    main()
