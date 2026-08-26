import os
import sys
import time
import json
import traceback
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import requests
import gspread
from google import genai

# ==============================================================================
# 1. DIRECTORY & CONFIGURATION
# ==============================================================================
BASE_DIR = r"LOCATION_OF_DIRECTORY"
CREDENTIALS_FILE = os.path.join(BASE_DIR, "service_account.json")
SPREADSHEET_NAME = "GOOGLE_SHEET_NAME"
SPREADSHEET_URL = "GOOGLE_SHEET_URL"

GEMINI_API_KEY = "GEMINI_API_KEY"
MODEL_NAME = "gemma-4-26b-a4b-it"
MAX_JOBS_PER_RUN = 15
LOCATION = "Ahmedabad, Gujarat"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SEARCH_KEYWORDS = [
    "IT Technical Support", "Systems Administrator", "Network Engineer",
    "Cybersecurity Analyst", "Cloud Operations", "L2 Support"
]

CANDIDATE_PROFILE = """
Kishan Panchal - IT Professional & Systems Administrator
- Experience: 2+ years in IT, Systems Admin, Networking, Cloud Infrastructure.
- Key Metrics: 95% CSAT, 90% First Call Resolution.
- Technical Skills: Networking (OSPF, BGP, VLANs, DNS), OS (Windows, Linux), Cloud (Azure, AWS, GCP).
- Preferences: Open to fully remote roles and willing to relocate for the right opportunity.
"""

# ==============================================================================
# 2. SCRAPERS (Naukri, Indeed, LinkedIn, WorkIndia)
# ==============================================================================
def fetch_naukri_jobs(page, keyword, location):
    jobs = []
    url = f"https://www.naukri.com/{keyword.lower().replace(' ', '-')}-jobs-in-{location.split(',')[0].strip().lower()}?freshness=1"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
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
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(3000)
        scraped = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('div.cardOutline, .job_seen_beacon')).map(card => {
                const titleElem = card.querySelector('h2.jobTitle span, [class*="jobTitle"]');
                const compElem = card.querySelector('[data-testid="company-name"], .companyName');
                const linkElem = card.querySelector('a.jcs-JobTitle, h2.jobTitle a');
                return titleElem && linkElem ? {
                    title: titleElem.innerText.trim(), 
                    company: compElem ? compElem.innerText.trim() : 'N/A', 
                    url: linkElem.href
                } : null;
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
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(3000)
        scraped = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.job-card, [class*="JobCard"]')).map(card => {
                const titleElem = card.querySelector('h3, [class*="title"]');
                const compElem = card.querySelector('.company-name, [class*="company"]');
                const linkElem = card.querySelector('a');
                return titleElem && linkElem ? {
                    title: titleElem.innerText.trim(), 
                    company: compElem ? compElem.innerText.trim() : 'N/A', 
                    url: linkElem.href.startsWith('http') ? linkElem.href : 'https://www.workindia.in' + linkElem.href
                } : null;
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
        res = requests.get(url, headers=HEADERS, timeout=10)
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
    """Visits the job URL and extracts the actual job description text."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        
        if "linkedin.com" in url:
            desc_div = soup.find("div", class_="show-more-less-html__markup")
            if desc_div: return desc_div.get_text(separator=" ", strip=True)
        elif "naukri.com" in url:
            desc_div = soup.find("div", class_="job-desc")
            if desc_div: return desc_div.get_text(separator=" ", strip=True)
            
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text(strip=True) for p in paragraphs])
        return text[:3000] if text else "Description not available."
    except Exception as e:
        return "Description not available."

# ==============================================================================
# 3. AI PROCESSING & GOOGLE SHEETS SYNC (WITH SMART DEDUPLICATION)
# ==============================================================================
def process_and_sync(df):
    if not os.path.exists(CREDENTIALS_FILE):
        return print("[System] service_account.json missing. Skipping sheet sync.")
    
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    worksheet = gc.open_by_url(SPREADSHEET_URL).sheet1
    
    # Grab existing data from the sheet to prevent re-processing
    all_sheet_rows = worksheet.get_all_values()
    existing_urls = set()
    existing_jobs_set = set()
    
    if len(all_sheet_rows) > 1:
        for row in all_sheet_rows[1:]: # Skip header
            if len(row) >= 3:
                url_val = row[4].strip().lower() if len(row) > 4 else ""
                comp_val = row[1].strip().lower() if len(row) > 1 else ""
                role_val = row[2].strip().lower() if len(row) > 2 else ""
                
                if url_val:
                    existing_urls.add(url_val)
                if comp_val and role_val:
                    existing_jobs_set.add((comp_val, role_val))

    # Clean incoming dataframe
    df = df.drop_duplicates(subset=['URL'])
    df['temp_comp'] = df['Company'].str.lower().str.strip()
    df['temp_role'] = df['Role'].str.lower().str.strip()
    df['temp_url'] = df['URL'].str.lower().str.strip()

    # Filter out jobs that match existing URLs OR existing Company+Role pairs
    filtered_jobs = []
    for _, row in df.iterrows():
        is_url_dup = row['temp_url'] in existing_urls
        is_job_dup = (row['temp_comp'], row['temp_role']) in existing_jobs_set
        
        if not is_url_dup and not is_job_dup:
            filtered_jobs.append(row)

    if not filtered_jobs:
        return print("[System] No new unique jobs found today. Everything is already tracked!")

    new_df = pd.DataFrame(filtered_jobs).drop_duplicates(subset=['temp_comp', 'temp_role']).head(MAX_JOBS_PER_RUN)
    
    if new_df.empty:
        return print("[System] No new unique jobs found after cleanup.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    rows_to_append = []
    
    print(f"\n[AI] Tailoring {len(new_df)} genuinely new IT jobs...")
    for _, job in new_df.iterrows():
        try:
            print(f"  Fetching details for: {job['Company']} - {job['Role']}...")
            job_description = scrape_job_description(job['URL'])
            
            prompt = f"""
            You are an expert technical resume writer. I am applying for the {job['Role']} position at {job['Company']}.
            
            Candidate Background: {CANDIDATE_PROFILE}
            
            Here is the actual Job Description:
            {job_description}
            
            First, identify the top 3 core technical requirements from the Job Description. 
            Then, write exactly 3 tailored resume bullet points mapping my background to those specific requirements.
            
            CRITICAL RULES:
            1. DO NOT use generic introductory templates like "Resolved complex hardware/software issues".
            2. Vary the sentence structure of every single bullet point.
            3. Use the exact keywords found in the Job Description text provided above.
            
            Return JSON strictly formatted: {{"email_subject": "...", "cold_email": "100-word email highlighting Cloud/Networking and 95% CSAT", "resume_bullets": "• Bullet 1\\n• Bullet 2\\n• Bullet 3"}}
            """
            
            res = json.loads(client.models.generate_content(model=MODEL_NAME, contents=prompt).text.replace("```json", "").replace("```", "").strip())
            
            rows_to_append.append([
                job["Date Applied"], job["Company"], job["Role"], job["Location"], job["URL"],
                res.get("email_subject", ""), res.get("cold_email", ""), res.get("resume_bullets", ""), "New", "Pending"
            ])
            time.sleep(1.5)
        except Exception as e:
            print(f"  [AI Warn] Failed to process {job['Company']}: {e}")
            continue
    
    if rows_to_append:
        worksheet.append_rows(rows_to_append)
        print(f"[Success] Appended {len(rows_to_append)} tailored jobs to Master Sheet.")

def main():
    all_jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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
        df.to_csv(os.path.join(BASE_DIR, f"it_jobs_{datetime.now().strftime('%Y%m%d')}.csv"), index=False)
        process_and_sync(df)
    else:
        print("[System] No jobs found across any platform.")

if __name__ == "__main__":
    main()
