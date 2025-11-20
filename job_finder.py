import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_jobs():
    jobs = [
        {
            "title": "Data Science Intern",
            "company": "ABC Corp",
            "location": "Bangalore",
            "link": "https://example.com/job1",
            "summary": "Entry-level role working with ML models."
        },
        {
            "title": "Java Developer Fresher",
            "company": "XYZ Tech",
            "location": "Hyderabad",
            "link": "https://example.com/job2",
            "summary": "Work on backend Java services."
        }
    ]
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
