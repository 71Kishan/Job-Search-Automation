import os
import json
import time
import requests
import traceback
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Google Sheets Library
try:
    import gspread
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Google GenAI Library
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# --- CONFIGURATION ---
SPREADSHEET_NAME = "Master job Search Tracker"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1rZQz-4MwJUSJr7B2mTKs89mguS4lmYuvu76GX-YjUeY/edit?gid=0#gid=0"
CREDENTIALS_FILE = "service_account.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

SEARCH_KEYWORDS = [
    "IT Technical Support",
    "Technical Support Engineer",
    "Desktop Support Engineer",
    "Service Desk Analyst",
    "Systems Administrator",
    "Network Engineer",
    "Network Support Specialist",
    "Cybersecurity Analyst",
    "SOC Analyst",
    "Network Security Analyst",
    "IT Operations Analyst",
    "Technical Account Manager"
]

LOCATION = "Ahmedabad, Gujarat"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# Candidate profile context for AI generation & matching
CANDIDATE_PROFILE = """
Candidate Details:
- Education: Undergraduate in Computer Networking and Cybersecurity.
- Background: Technical Support Specialist / IT Technical Support Representative with experience in hardware/software troubleshooting, network administration, active directory, incident resolution, and customer support.
"""


def select_top_jobs(df, max_jobs=25):
    """Uses Gemma to select the top N best-matching jobs from the scraped dataframe."""
    if len(df) <= max_jobs:
        return df

    if not GENAI_AVAILABLE or not GEMINI_API_KEY:
        print(f"\n[AI Filter] API not available. Taking the first {max_jobs} jobs.")
        return df.head(max_jobs)

    try:
        print(f"\n[AI Filter] Selecting the top {max_jobs} best-matching jobs out of {len(df)} total jobs...")
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        job_summaries = []
        for idx, row in df.reset_index(drop=True).iterrows():
            job_summaries.append(f"Index: {idx}, Role: {row['Role']}, Company: {row['Company']}")
        
        job_text = "\n".join(job_summaries)
        
        prompt = f"""
        {CANDIDATE_PROFILE}

        Here is a list of available job postings:
        {job_text}

        Select the top {max_jobs} jobs that are the absolute best match for the candidate's profile (focusing on IT Support, Technical Support, Networking, and Cybersecurity roles).
        Return ONLY a JSON list of the integer indices corresponding to the selected jobs, formatted strictly as:
        [0, 2, 5, 10, ...]
        """

        response = client.models.generate_content(
            model='gemma-4-26b-a4b-it',
            contents=prompt,
        )

        text = response.text.strip()
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()
        
        selected_indices = json.loads(text)
        if isinstance(selected_indices, list) and len(selected_indices) > 0:
            df_reset = df.reset_index(drop=True)
            valid_indices = [i for i in selected_indices if isinstance(i, int) and 0 <= i < len(df_reset)]
            if valid_indices:
                filtered_df = df_reset.iloc[valid_indices]
                print(f"[AI Filter] Successfully selected {len(filtered_df)} top-matching jobs.")
                return filtered_df

    except Exception as e:
        print(f"[AI Filter Note] Failed to filter via AI: {e}. Falling back to top {max_jobs} jobs.")
    
    return df.head(max_jobs)


def generate_ai_content(role, company):
    """Generates an email subject, tailored cold email, and 3 resume bullets using Gemma API."""
    if not GENAI_AVAILABLE or not GEMINI_API_KEY:
        return "", "", ""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
        {CANDIDATE_PROFILE}

        Target Job Role: {role}
        Target Company: {company}

        Generate three outputs:
        1. EMAIL_SUBJECT: A compelling, professional subject line for a cold email applying to this exact position.
        2. COLD_EMAIL: A professional, concise 3-sentence cold email pitching the candidate for this exact position.
        3. RESUME_BULLETS: Exactly 3 impactful, tailored resume bullet points highlighting relevant skill sets for this role.

        Return the result strictly formatted in JSON like this:
        {{
            "email_subject": "...",
            "cold_email": "...",
            "resume_bullets": "• Bullet 1\\n• Bullet 2\\n• Bullet 3"
        }}
        """

        response = client.models.generate_content(
            model='gemma-4-26b-a4b-it',
            contents=prompt,
        )

        text = response.text.strip()
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()

        data = json.loads(text)
        return data.get("email_subject", ""), data.get("cold_email", ""), data.get("resume_bullets", "")

    except Exception as e:
        print(f"    [AI Generation Note] Skipped AI draft for {role}: {e}")
        return "", "", ""


def fetch_naukri_jobs(page, keyword, location):
    """Fetch Naukri jobs via Playwright live DOM extraction."""
    jobs = []
    city = location.split(",")[0].strip().lower()
    formatted_kw = keyword.lower().replace(" ", "-")
    url = f"https://www.naukri.com/{formatted_kw}-jobs-in-{city}?freshness=1"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(3500)
        page.evaluate("window.scrollBy(0, 400)")

        scraped = page.evaluate("""() => {
            const items = [];
            const cards = document.querySelectorAll('div.srp-jobtuple-wrapper, article.jobTuple, div.cust-job-tuple, [data-job-id]');
            
            cards.forEach(card => {
                const titleElem = card.querySelector('a.title, [class*="title"]');
                const companyElem = card.querySelector('a.comp-name, [class*="comp-name"], [class*="company"]');
                
                if (titleElem && titleElem.href) {
                    items.push({
                        title: titleElem.innerText.split('\\n')[0].trim(),
                        company: companyElem ? companyElem.innerText.trim() : 'N/A',
                        url: titleElem.href
                    });
                }
            });
            return items;
        }""")

        for item in scraped:
            if item["title"] and item["url"]:
                jobs.append({
                    "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                    "Company": item["company"],
                    "Role": item["title"],
                    "Location": location,
                    "URL": item["url"]
                })
    except Exception as e:
        print(f"    [Naukri Error] {e}")

    return jobs


def fetch_indeed_jobs(page, keyword, location):
    """Fetch Indeed jobs via Playwright live DOM extraction."""
    jobs = []
    city = location.split(",")[0].strip()
    formatted_kw = keyword.replace(" ", "+")
    url = f"https://in.indeed.com/jobs?q={formatted_kw}&l={city}"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(3000)

        scraped = page.evaluate("""() => {
            const items = [];
            const cards = document.querySelectorAll('div.job_seen_beacon, td.resultContent, div.cardOutline, div.jobContainer, [data-jk]');
            
            cards.forEach(card => {
                const titleElem = card.querySelector('h2.jobTitle, a[id^="job_"], a.jxf');
                const companyElem = card.querySelector('[data-testid="company-name"], .companyName');
                const linkElem = card.querySelector('a[href*="/rc/clk"], a[href*="jk="], h2.jobTitle a');
                
                if (titleElem && linkElem) {
                    items.push({
                        title: titleElem.innerText.split('\\n')[0].trim(),
                        company: companyElem ? companyElem.innerText.trim() : 'N/A',
                        url: linkElem.href
                    });
                }
            });
            return items;
        }""")

        for item in scraped:
            if item["title"] and item["url"]:
                jobs.append({
                    "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                    "Company": item["company"],
                    "Role": item["title"],
                    "Location": city,
                    "URL": item["url"]
                })
    except Exception as e:
        print(f"    [Indeed Error] {e}")

    return jobs


def fetch_linkedin_jobs(keyword, location):
    """Fetch LinkedIn listings via public API."""
    jobs = []
    city = location.split(",")[0].strip()
    formatted_kw = keyword.replace(" ", "%20")
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={formatted_kw}&location={city}&f_TPR=r86400&start=0"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.find_all("li")
            for card in cards:
                title_elem = card.find("h3", class_="base-search-card__title")
                company_elem = card.find("h4", class_="base-search-card__subtitle")
                link_elem = card.find("a", class_="base-card__full-link")

                if title_elem and company_elem and link_elem:
                    jobs.append({
                        "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                        "Company": company_elem.text.strip(),
                        "Role": title_elem.text.strip(),
                        "Location": city,
                        "URL": link_elem["href"].split("?")[0]
                    })
    except Exception as e:
        print(f"    [LinkedIn Error] {e}")
    return jobs


def fetch_workindia_jobs(keyword, location):
    """Fetch WorkIndia listings via direct HTTP requests."""
    jobs = []
    city = location.split(",")[0].strip().lower()
    formatted_kw = keyword.lower().replace(" ", "%20")
    url = f"https://www.workindia.in/jobs-in-{city}/?q={formatted_kw}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.find_all("a", href=True)
            for card in cards:
                href = card.get("href", "")
                if "/job/" in href or "/jobs/" in href:
                    title = card.text.strip().split("\n")[0]
                    if title and len(title) > 3:
                        full_url = "https://www.workindia.in" + href if href.startswith("/") else href
                        jobs.append({
                            "Date Applied": datetime.now().strftime("%Y-%m-%d"),
                            "Company": "Direct Employer",
                            "Role": title,
                            "Location": city.capitalize(),
                            "URL": full_url
                        })
    except Exception as e:
        print(f"    [WorkIndia Error] {e}")
    return jobs


def update_google_sheet(df):
    """Appends NEW top-matching jobs safely and generates AI email subjects, cold emails & resume bullets."""
    if not GSPREAD_AVAILABLE:
        print("\n[Google Sheets] 'gspread' library not installed. Skipping Google Sheet sync.")
        return

    downloads_path = os.path.expanduser("~/Downloads")
    json_path = os.path.join(downloads_path, CREDENTIALS_FILE)

    if not os.path.exists(json_path) and not os.path.exists(CREDENTIALS_FILE):
        print(f"\n[Google Sheets] Credentials file '{CREDENTIALS_FILE}' not found. Skipping Google Sheet sync.")
        return

    creds_file = json_path if os.path.exists(json_path) else CREDENTIALS_FILE

    try:
        gc = gspread.service_account(filename=creds_file)

        try:
            sh = gc.open_by_url(SPREADSHEET_URL)
        except Exception:
            sh = gc.open(SPREADSHEET_NAME)

        worksheet = sh.sheet1
        existing_rows = worksheet.get_all_values()

        cleaned_df = df.fillna("").astype(str)

        # Updated headers with "Email Subject" placed right before "Tailored Cold Email"
        default_headers = [
            "Date Applied", "Company", "Role", "Location", "URL", 
            "Email Subject", "Tailored Cold Email", "Tailored Resume Bullets", "Status", "Follow-Up Date"
        ]

        # Case 1: Sheet is empty
        if not existing_rows:
            header = default_headers
            worksheet.update('A1', [header])
            existing_urls = set()
        else:
            header = existing_rows[0]
            try:
                url_col_idx = [h.strip().lower() for h in header].index("url")
                existing_urls = set(row[url_col_idx].strip() for row in existing_rows[1:] if len(row) > url_col_idx and row[url_col_idx].strip())
            except ValueError:
                existing_urls = set()

        # Filter out already saved URLs
        new_jobs_df = cleaned_df[~cleaned_df["URL"].astype(str).str.strip().isin(existing_urls)]

        if new_jobs_df.empty:
            print("\n[Google Sheets] No new unique jobs found today. Your sheet is up to date!")
            return

        # Cap to top 25 best-matching roles using AI evaluation
        new_jobs_df = select_top_jobs(new_jobs_df, max_jobs=25)

        print(f"\n[AI Content Generator] Generating email subjects, cold emails & resume bullets for {len(new_jobs_df)} top-matching jobs...")

        rows_to_append = []
        for idx, (_, job) in enumerate(new_jobs_df.iterrows(), 1):
            role = job.get("Role", "")
            company = job.get("Company", "")

            # Generate AI content for each selected listing
            subject_draft, email_draft, bullets_draft = generate_ai_content(role, company)

            job_dict = job.to_dict()
            job_dict["Status"] = "New"
            job_dict["Email Subject"] = subject_draft
            job_dict["Tailored Cold Email"] = email_draft
            job_dict["Tailored Resume Bullets"] = bullets_draft
            job_dict["Follow-Up Date"] = "Pending"

            new_row = [str(job_dict.get(col_name, "")) for col_name in header]
            rows_to_append.append(new_row)

            if idx % 5 == 0:
                print(f"    Processed AI content for {idx}/{len(new_jobs_df)} jobs...")
                time.sleep(1)  # Prevent rate limits

        worksheet.append_rows(rows_to_append)
        print(f"\n[Google Sheets] Successfully appended {len(rows_to_append)} top-matching jobs with AI-generated content!")

    except Exception as e:
        print(f"\n[Google Sheets Error] Failed to update: {e}")
        print("Detailed traceback:")
        traceback.print_exc()


def main():
    all_jobs = []
    print(f"Starting Multi-Platform Job Fetcher for {LOCATION}...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for kw in SEARCH_KEYWORDS:
            print(f"\n--- Searching: {kw} ---")

            # 1. Naukri
            naukri_res = fetch_naukri_jobs(page, kw, LOCATION)
            print(f"  [Naukri.com] {len(naukri_res)} jobs")
            all_jobs.extend(naukri_res)

            # 2. Indeed
            indeed_res = fetch_indeed_jobs(page, kw, LOCATION)
            print(f"  [Indeed] {len(indeed_res)} jobs")
            all_jobs.extend(indeed_res)

            # 3. LinkedIn
            linkedin_res = fetch_linkedin_jobs(kw, LOCATION)
            print(f"  [LinkedIn] {len(linkedin_res)} jobs")
            all_jobs.extend(linkedin_res)

            # 4. WorkIndia
            workindia_res = fetch_workindia_jobs(kw, LOCATION)
            print(f"  [WorkIndia] {len(workindia_res)} jobs")
            all_jobs.extend(workindia_res)

            time.sleep(1)

        browser.close()

    if all_jobs:
        df = pd.DataFrame(all_jobs)
        df = df.drop_duplicates(subset=["URL"])

        # Save local CSV backup
        today_str = datetime.now().strftime("%Y%m%d")
        downloads_path = os.path.expanduser("~/Downloads")
        output_file = os.path.join(downloads_path, f"jobs_{today_str}.csv")
        df.to_csv(output_file, index=False)
        print(f"\nSuccessfully scraped {len(df)} total unique jobs!")
        print(f"CSV saved to: {output_file}")

        # Sync with Google Sheets & generate AI drafts for top matches
        update_google_sheet(df)
    else:
        print("\nNo jobs scraped across platforms.")


if __name__ == "__main__":
    main()