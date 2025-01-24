import os
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import gspread
from google.oauth2.service_account import Credentials

# Path to your service_account.json
SERVICE_ACCOUNT_FILE = "service_account.json"

# Define the scope
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Authenticate and connect to Google Sheets
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# Open the Google Sheet
SPREADSHEET_NAME = "Talent Info"
sheet = client.open(SPREADSHEET_NAME).sheet1

# Define column indices based on your sheet layout
COL_TALENT_NAME = 1  # A: Talent Name
COL_HEADSHOT = 2     # B: Headshot
COL_RECENT_CREDITS = 3  # C: Recent Credits
COL_PROJECT = 4      # D: Project ("DB01", "DB22," etc.)
COL_SOCIAL_HANDLE = 5  # E: Social Handle
COL_PHONE = 6        # F: Phone
COL_EMAIL = 7        # G: Email
COL_REP_INFO = 8     # H: Rep Info
COL_COMMENT = 9      # I: Comment
COL_IMDB_LINK = 10   # J: IMDB Link
COL_TIMESTAMP = 11   # K: Timestamp

def scrape_imdb_actor(imdb_url):
    """
    Uses Selenium to scrape:
      - Talent name
      - Headshot URL
      - Top 3 'recent' credits
    Returns (talent_name, headshot_url, credits_str).
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")  # Necessary for some environments
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.5735.198 Safari/537.36"
    )

    # Initialize WebDriver
    service = Service("chromedriver")  # Ensure chromedriver is in PATH
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(imdb_url)
        wait = WebDriverWait(driver, 15)
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='Filmography']"))
        )

        # Expand all "recent" sections if they are collapsible
        toggles = driver.find_elements(By.CSS_SELECTOR, "label[role='button'][aria-label*='Expand']")
        for tg in toggles:
            tg.click()
            time.sleep(1)

        # Scroll to load dynamic content
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Extract Talent Name
        name_tag = soup.find("h1")
        talent_name = name_tag.get_text(strip=True) if name_tag else "Unknown Name"

        # Extract Headshot URL
        img_tag = soup.find("img", class_="ipc-image")
        headshot_url = img_tag["src"] if img_tag else "https://via.placeholder.com/200"

        # Extract Top 3 Recent Credits
        credits_list = []
        filmography_div = soup.find("div", data-testid="Filmography")
        if filmography_div:
            # Assuming 'Recent' is labeled as such; adjust selectors as needed
            recent_section = filmography_div.find("div", string="Recent")
            if recent_section:
                recent_projects = recent_section.find_next_sibling("ul").find_all("li", limit=3)
                for project in recent_projects:
                    title_tag = project.find("a")
                    if title_tag:
                        credits_list.append(title_tag.get_text(strip=True))
        else:
            credits_list = ["No recent credits found."]

        credits_str = ", ".join(credits_list)
        return talent_name, headshot_url, credits_str

    finally:
        driver.quit()

def main():
    all_values = sheet.get_all_values()

    # Iterate through each row starting from row 2 (skip headers)
    for row_idx, row_data in enumerate(all_values[1:], start=2):
        # Get existing talent name from column A
        existing_name = row_data[COL_TALENT_NAME - 1].strip() if len(row_data) >= COL_TALENT_NAME else ""
        # Get IMDb link from column J
        imdb_link = row_data[COL_IMDB_LINK - 1].strip() if len(row_data) >= COL_IMDB_LINK else ""

        # If IMDb link is present and talent name is empty, proceed to scrape
        if imdb_link and not existing_name:
            print(f"Row {row_idx}: Scraping IMDb for link: {imdb_link}")
            try:
                talent_name, headshot_url, credits_str = scrape_imdb_actor(imdb_link)

                # Use =IMAGE("URL") to embed the image in column B
                image_formula = f'=IMAGE("{headshot_url}")'

                # Update the Google Sheet
                sheet.update_cell(row_idx, COL_TALENT_NAME, talent_name)
                sheet.update_cell(row_idx, COL_HEADSHOT, image_formula)
                sheet.update_cell(row_idx, COL_RECENT_CREDITS, credits_str)

                print(f"Row {row_idx} updated with Name: {talent_name}, Headshot: [Image], Credits: {credits_str}")
            except Exception as e:
                print(f"Error scraping row {row_idx}: {e}")

    print("\nAll eligible rows have been processed.")

if __name__ == "__main__":
    main()
