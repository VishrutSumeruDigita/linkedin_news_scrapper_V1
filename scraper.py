import os
import time
import tempfile
from playwright.sync_api import sync_playwright
from validate_email import validate_email
import tldextract
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def linkedin_login():
    """Login to LinkedIn using Selenium with Chrome"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    try:
        # Use ChromeDriverManager for automatic driver installation
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Navigate to LinkedIn login page
        driver.get("https://www.linkedin.com/login")
        
        # Fill login form
        driver.find_element(By.ID, "username").send_keys(os.getenv("LINKEDIN_EMAIL"))
        driver.find_element(By.ID, "password").send_keys(os.getenv("LINKEDIN_PASSWORD"))
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # Wait for navigation to complete (feed page)
        WebDriverWait(driver, 30).until(
            EC.url_contains("/feed/")
        )
        
        return driver
    except Exception as e:
        print(f"Error logging in to LinkedIn: {str(e)}")
        raise


def search_profiles(driver, keyword, limit=20):
    """Search for profiles on LinkedIn"""
    query = keyword.replace(" ", "%20")
    url = f"https://www.linkedin.com/search/results/people/?keywords={query}"
    
    driver.get(url)
    time.sleep(3)  # Wait for page to load
    
    profiles = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while len(profiles) < limit:
        # Get all profile cards
        cards = driver.find_elements(By.CSS_SELECTOR, "div.entity-result__item")
        
        for card in cards:
            try:
                link = card.find_element(By.CSS_SELECTOR, "a.app-aware-link")
                if link:
                    name = link.text.strip()
                    profile_url = link.get_attribute("href")
                    profile = {"name": name, "url": profile_url}
                    if profile not in profiles:
                        profiles.append(profile)
                        if len(profiles) >= limit:
                            break
            except:
                continue
        
        # Scroll down to load more results
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Wait for content to load
        
        # Check if we've reached the end of the page
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break  # No more content loaded
        last_height = new_height
    
    return profiles[:limit]


def extract_company_domain(driver, profile_url):
    """Extract company domain from LinkedIn profile"""
    # Navigate to profile page
    driver.get(profile_url)
    time.sleep(3)  # Wait for page to load
    
    try:
        # Find and click on the company link
        company_link = None
        try:
            company_link = driver.find_element(By.CSS_SELECTOR, "a[data-control-name*='company']")
        except:
            try:
                company_link = driver.find_element(By.CSS_SELECTOR, "a[href*='/company/']")
            except:
                return None
        
        if company_link:
            comp_url = company_link.get_attribute("href")
            driver.get(comp_url)
            time.sleep(3)  # Wait for page to load
            
            # Find website link
            website_link = None
            try:
                website_link = driver.find_element(By.CSS_SELECTOR, "a[data-control-name*='website']")
            except:
                try:
                    website_link = driver.find_element(By.CSS_SELECTOR, "a[href^='http']:not([href*='linkedin.com'])")
                except:
                    return None
            
            if website_link:
                website = website_link.get_attribute("href")
                ext = tldextract.extract(website)
                return f"{ext.domain}.{ext.suffix}"
    
    except Exception as e:
        print(f"Error extracting company domain: {str(e)}")
    
    return None


def get_valid_email(first, last, domain):
    """Generate and validate email addresses"""
    if not domain:
        return None
        
    patterns = [
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}@{domain}"
    ]
    
    for email in patterns:
        try:
            if validate_email(email, verify=True):
                return email
        except:
            pass
    
    return None


def close_browser(driver_data):
    """Close the browser and stop playwright"""
    if driver_data and "browser" in driver_data:
        driver_data["browser"].close()
    
    if driver_data and "playwright" in driver_data:
        driver_data["playwright"].stop()

