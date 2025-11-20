# job_finder.py
# Enhanced job finder:
# - filters for India (or marks Remote)
# - filters for entry-level jobs
# - attempts to find HR/contact email in description or on job page
# - formats a nicer HTML email with company name and HR contact

import os
import re
import requests
from bs4 import BeautifulSoup
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse, urljoin

# ---------- Config ----------
MAX_JOBS = int(os.getenv("MAX_JOBS", "30"))  # how many jobs to gather (cap)
KEYWORDS = ["data", "java", "frontend", "frontend developer", "java developer", "data scientist"]
ENTRY_LEVEL_KEYWORDS = ["fresher", "fresher", "fresh", "intern", "internship", "junior", "entry", "associate", "trainee", "graduate"]
INDIA_KEYS = ["india", "india,", "india.", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune", "kolkata", "noida", "gurgaon", "gurugram", "ahmedabad", "kerala", "karnataka", "tamil nadu", "telangana", "uttar pradesh", "maharashtra", "goa", "rajasthan", "odisha", "bihar", "assam", "punjab", "haryana", "manipur", "nagaland", "goa"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobFinderBot/1.0; +https://example.com/bot)"
}

email_rx = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# ---------- Utilities ----------

def is_entry_level(text):
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in ENTRY_LEVEL_KEYWORDS)

def matches_topic(text):
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in KEYWORDS)

def normalize_location(loc):
    if not loc:
        return "Remote"
    l = loc.lower()
    # If it mentions India or common Indian cities/regions → keep original
    if any(k in l for k in INDIA_KEYS):
        # return title-cased trimmed location
        return loc.strip()
    # If location explicitly says remote
    if "remote" in l or "anywhere" in l or "work from home" in l:
        return "Remote"
    # If other country mention, convert to "Remote"
    # (You can adjust this logic to keep country-specific if you want)
    return "Remote"

def find_email_in_text(text):
    if not text:
        return None
    m = email_rx.search(text)
    return m.group(0) if m else None

def crawl_for_hr_email(job_url, max_depth=1):
    """
    Try to find a contact email on the job URL page or its main domain / contact page.
    Keep requests small and polite.
    """
    try:
        # fetch job page
        r = requests.get(job_url, headers=HEADERS, timeout=8)
        r.raise_for_status()
        body = r.text
        e = find_email_in_text(body)
        if e:
            return e

        # If none found, try looking at the site's contact page: /contact or /careers
        parsed = urlparse(job_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in ["/contact", "/contact-us", "/careers", "/about", "/company/contact", "/careers/contact"]:
            try:
                url = urljoin(base, path)
                rr = requests.get(url, headers=HEADERS, timeout=6)
                if rr.status_code == 200:
                    e = find_email_in_text(rr.text)
                    if e:
                        return e
            except Exception:
                continue
    except Exception:
        return None
    return None

# ---------- Job collectors ----------

def jobs_from_remotive():
    out = []
    try:
        res = requests.get("https://remotive.com/api/remote-jobs", headers=HEADERS, timeout=10)
        data = res.json()
        for job in data.get("jobs", []):
            title = job.get("title", "")
            if not matches_topic(title) and not matches_topic(job.get("category", "")):
                continue
            # match entry-level by title or description
            combined_text = f"{title}\n{job.get('description','')}"
            if not is_entry_level(combined_text):
                continue
            loc = job.get("candidate_required_location", "") or job.get("location", "")
            loc_norm = normalize_location(loc)
            out.append({
                "title": title,
                "company": job.get("company_name", ""),
                "location": loc_norm,
                "link": job.get("url", job.get("job_url", "")),
                "summary": BeautifulSoup(job.get("description", "")[:300], "html.parser").get_text().strip(),
                "raw_description": job.get("description", ""),
            })
            if len(out) >= MAX_JOBS:
                break
    except Exception:
        pass
    return out

def jobs_from_remoteok():
    out = []
    try:
        ro = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=10).json()
        for job in ro:
            # the JSON includes some meta dict entries; filter dicts with 'position' or 'company'
            if not isinstance(job, dict):
                continue
            title = job.get("position") or job.get("title") or job.get("position_title", "")
            if not title or not matches_topic(title):
                continue
            desc = job.get("description", "") or job.get("tags", "")
            if not is_entry_level(title + " " + desc):
                continue
            loc = job.get("location") or job.get("location_name") or job.get("city", "")
            loc_norm = normalize_location(loc)
            out.append({
                "title": title,
                "company": job.get("company", ""),
                "location": loc_norm,
                "link": job.get("url") or job.get("link") or job.get("apply_link") or job.get("slug"),
                "summary": BeautifulSoup(job.get("description", "")[:300], "html.parser").get_text().strip(),
                "raw_description": job.get("description", ""),
            })
            if len(out) >= MAX_JOBS:
                break
    except Exception:
        pass
    return out

def jobs_from_wellfound_rss():
    out = []
    try:
        feed_url = "https://wellfound.com/feed"
        r = requests.get(feed_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item"):
            title = (item.title.text or "").strip()
            link = item.link.text if item.link else "#"
            desc = (item.description.text or "")
            if not matches_topic(title) and not matches_topic(desc):
                continue
            if not is_entry_level(title + " " + desc):
                continue
            # location often not available in RSS; mark Remote
            loc_norm = normalize_location(item.find("location").text if item.find("location") else "")
            out.append({
                "title": title,
                "company": item.find("company").text if item.find("company") else "Startup (Wellfound)",
                "location": loc_norm,
                "link": link,
                "summary": BeautifulSoup(desc[:300], "html.parser").get_text().strip(),
                "raw_description": desc,
            })
            if len(out) >= MAX_JOBS:
                break
    except Exception:
        pass
    return out

# Add more collectors here (e.g., other APIs or RSS). Keep each safe & small.

# ---------- Main aggregator ----------

def get_jobs():
    jobs = []
    seen = set()

    collectors = [
        jobs_from_remoteok,
        jobs_from_remotive,
        jobs_from_wellfound_rss,
    ]

    for collect in collectors:
        try:
            for j in collect():
                # unify link
                link = j.get("link") or ""
                key = (j.get("title","").strip().lower(), j.get("company","").strip().lower(), link)
                if key in seen:
                    continue
                seen.add(key)

                # ensure location normalization and level detection (already partly done)
                j["location"] = normalize_location(j.get("location"))
                # Try to find HR email in description first
                hr = find_email_in_text(j.get("raw_description","") or j.get("summary",""))
                if not hr and link and link.startswith("http"):
                    hr = crawl_for_hr_email(link)
                j["hr_email"] = hr or None

                # Add level: 'Entry' if entry-level else 'Other' (should be all entry due to filter)
                j["level"] = "Entry" if is_entry_level((j.get("title","") + " " + (j.get("raw_description","") or ""))) else "Other"

                jobs.append(j)
                if len(jobs) >= MAX_JOBS:
                    break
        except Exception:
            continue
        if len(jobs) >= MAX_JOBS:
            break

    # optional: sort by company then title
    jobs = sorted(jobs, key=lambda x: (x.get("company","").lower(), x.get("title","").lower()))
    return jobs

# ---------- Email formatting & sending ----------

def build_html_email(jobs):
    html = """
    <html>
    <body>
      <h2>Daily Job Update — Entry-level (Filtered)</h2>
      <p>Jobs filtered for: Data / Java / Frontend — India-first (others marked Remote)</p>
      <table style="width:100%; border-collapse: collapse;">
        <thead>
          <tr>
            <th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">Job Title</th>
            <th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">Company</th>
            <th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">Location</th>
            <th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">Level</th>
            <th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">HR Contact</th>
          </tr>
        </thead>
        <tbody>
    """
    for j in jobs:
        title = j.get("title","")
        comp = j.get("company","")
        loc = j.get("location","")
        level = j.get("level","")
        hr = j.get("hr_email") or ""
        link = j.get("link") or "#"
        summary = j.get("summary","")
        html += f"""
          <tr>
            <td style="padding:8px; vertical-align:top;"><b><a href="{link}">{title}</a></b><br><small>{summary}</small></td>
            <td style="padding:8px; vertical-align:top;">{comp}</td>
            <td style="padding:8px; vertical-align:top;">{loc}</td>
            <td style="padding:8px; vertical-align:top;">{level}</td>
            <td style="padding:8px; vertical-align:top;">{hr}</td>
          </tr>
        """
    html += """
        </tbody>
      </table>
      <p style="font-size:12px; color:#666;">If a job has no HR contact found, the <i>Apply</i> link is the primary way to apply.</p>
    </body>
    </html>
    """
    return html

def send_email(from_email, password, to_email, jobs):
    message = MIMEMultipart("alternative")
    message["Subject"] = "Daily Job Update — Entry-level (Data / Java / Frontend)"
    message["From"] = from_email
    message["To"] = to_email

    html_content = build_html_email(jobs)
    message.attach(MIMEText(html_content, "html"))

    smtp_server = "smtp.gmail.com"
    port = 465

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(from_email, password)
        server.sendmail(from_email, to_email, message.as_string())

# ---------- Main ----------

if __name__ == "__main__":
    FROM_EMAIL = os.getenv("EMAIL_FROM")
    TO_EMAIL = os.getenv("EMAIL_TO")
    SMTP_USER = os.getenv("SMTP_USERNAME")
    SMTP_PASS = os.getenv("SMTP_PASSWORD")

    print("DEBUG: loading jobs...")
    jobs = get_jobs()
    print(f"DEBUG: found {len(jobs)} jobs")

    if not jobs:
        # fallback: include at least the placeholder so email is never empty
        jobs = [
            {
                "title": "No entry-level jobs found right now — check again later",
                "company": "",
                "location": "Remote",
                "link": "#",
                "summary": "No fresh entry-level jobs matched the filters at the time of the run.",
                "hr_email": None,
                "level": "None"
            }
        ]

    try:
        send_email(SMTP_USER, SMTP_PASS, TO_EMAIL, jobs)
        print("DEBUG: email sent (attempted)")
    except Exception as e:
        print("ERROR sending email:", str(e))
        raise
