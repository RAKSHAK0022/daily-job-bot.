import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup

def get_jobs():

    jobs = []

    # 1. RemoteOK API (Real jobs)
    try:
        ro = requests.get("https://remoteok.com/api").json()
        for job in ro:
            if isinstance(job, dict):
                title = job.get("position", "")
                if any(k.lower() in title.lower() for k in ["java", "frontend", "data"]):
                    jobs.append({
                        "title": job.get("position", "No title"),
                        "company": job.get("company", "Unknown"),
                        "location": job.get("location", "Remote"),
                        "link": job.get("url", "#"),
                        "summary": job.get("description", "")[:150] + "..."
                    })
    except:
        pass

    # 2. Remotive API (Good for software/dev roles)
    try:
        rem = requests.get("https://remotive.com/api/remote-jobs").json()
        for job in rem["jobs"]:
            title = job["title"]
            if any(k.lower() in title.lower() for k in ["java", "frontend", "data"]):
                jobs.append({
                    "title": job["title"],
                    "company": job["company_name"],
                    "location": job["candidate_required_location"],
                    "link": job["url"],
                    "summary": job["description"][:150] + "..."
                })
    except:
        pass

    # 3. Wellfound (AngelList) Startup Jobs (RSS)
    try:
        feed_url = "https://wellfound.com/feed"
        feed = requests.get(feed_url).text
        soup = BeautifulSoup(feed, "xml")
        for item in soup.find_all("item"):
            title = item.title.text
            if any(k.lower() in title.lower() for k in ["java", "frontend", "data"]):
                jobs.append({
                    "title": title,
                    "company": "Startup (Wellfound)",
                    "location": "Unknown",
                    "link": item.link.text,
                    "summary": item.description.text[:150] + "..."
                })
    except:
        pass

    return jobs


def send_email(from_email, password, to_email, jobs):
    message = MIMEMultipart("alternative")
    message["Subject"] = "Daily Job Update"
    message["From"] = from_email
    message["To"] = to_email

    html_content = "<h2>Daily Job List</h2>"
    for job in jobs:
        html_content += f"""
        <p>
        <b>{job['title']}</b><br>
        Company: {job['company']}<br>
        Location: {job['location']}<br>
        <a href="{job['link']}">Apply Here</a><br>
        {job['summary']}
        </p>
        <hr>
        """

    message.attach(MIMEText(html_content, "html"))

    smtp_server = "smtp.gmail.com"
    port = 465

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(from_email, password)
        server.sendmail(from_email, to_email, message.as_string())


if __name__ == "__main__":
    import os
    FROM_EMAIL = os.getenv("EMAIL_FROM")
    TO_EMAIL = os.getenv("EMAIL_TO")
    SMTP_USER = os.getenv("SMTP_USERNAME")
    SMTP_PASS = os.getenv("SMTP_PASSWORD")

    jobs = get_jobs()
    send_email(SMTP_USER, SMTP_PASS, TO_EMAIL, jobs)
