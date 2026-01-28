import gspread
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
from google.oauth2.service_account import Credentials

# ---------- AUTH ----------
creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)
client = gspread.authorize(creds)

# ---------- SHEET ----------
SPREADSHEET_NAME = "Job Tracker 2025"
sheet = client.open(SPREADSHEET_NAME)

def ensure_tab(name, headers=None):
    if name not in [ws.title for ws in sheet.worksheets()]:
        ws = sheet.add_worksheet(title=name, rows=2000, cols=10)
        if headers:
            ws.append_row(headers)
        return ws
    return sheet.worksheet(name)

data_sheet = ensure_tab(
    "Daily Job Flags",
    ["Date Found", "Company", "Role", "Source", "Link"]
)
config_sheet = ensure_tab("Config", ["Companies", "Roles"])
system_sheet = ensure_tab("System", ["Key", "Value"])

# ---------- LOAD CONFIG ----------
companies = [c for c in config_sheet.col_values(1)[1:] if c]
roles = [r for r in config_sheet.col_values(2)[1:] if r]

if not companies or not roles:
    print("No companies or roles configured.")
    exit()

# ---------- DAILY LOCK ----------
today = datetime.today().strftime("%Y-%m-%d")
system_data = dict(zip(system_sheet.col_values(1), system_sheet.col_values(2)))

if system_data.get("last_run") == today:
    print("Already ran today.")
    exit()

# ---------- SEARCH ----------
SEARCH_SITES = {
    "LinkedIn": "https://www.linkedin.com/jobs/search/?keywords=",
    "ZipRecruiter": "https://www.ziprecruiter.com/jobs-search?search=",
    "Glassdoor": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword="
}

HEADERS = {"User-Agent": "Mozilla/5.0"}
existing_links = set(data_sheet.col_values(5))
rows = []

for role in roles:
    for company in companies:
        for source, base_url in SEARCH_SITES.items():
            url = base_url + f"{role} {company}".replace(" ", "+")
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")

                for a in soup.find_all("a", href=True)[:25]:
                    link = a["href"]
                    if company.lower() in link.lower():
                        full = link if link.startswith("http") else base_url + link
                        if full not in existing_links:
                            rows.append([today, company, role, source, full])
                            existing_links.add(full)
                time.sleep(1)
            except:
                pass

if rows:
    data_sheet.append_rows(rows)
    system_sheet.append_row(["last_run", today])

print(f"Added {len(rows)} jobs.")
