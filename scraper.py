import os
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from validate_email import validate_email
import tldextract

from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Verify environment variables are loading correctly
logger.info(f"LinkedIn email exists: {bool(os.getenv('LINKEDIN_EMAIL'))}")
logger.info(f"LinkedIn password exists: {bool(os.getenv('LINKEDIN_PASSWORD'))}")

def configure_chrome_options():
    """Configure Chrome options for Selenium with enhanced anti-detection measures"""
    options = Options()
    
    # Basic Docker-specific settings
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Try non-headless mode in Docker with Xvfb
    options.add_argument("--disable-gpu")
    
    # Enhanced anti-detection measures
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Randomized user agent (use a recent Chrome version)
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Additional headers
    options.add_argument("--lang=en-US,en;q=0.9")
    options.add_argument("--accept-language=en-US,en;q=0.9")
    
    # Additional performance settings
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    
    # Specify Chrome binary location
    if os.name == 'posix':  # Linux/Mac
        options.binary_location = '/usr/bin/google-chrome'
    else:  # Windows
        options.binary_location = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    
    return options

def simulate_human_behavior(driver):
    """Simulate random mouse movements and scrolling to mimic human behavior"""
    try:
        # Random scrolling
        scroll_amount = random.randint(100, 800)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 2.0))
        
        # Back to top
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(random.uniform(0.5, 1.5))
        
        # Random wait
        time.sleep(random.uniform(1.0, 3.0))
    except Exception as e:
        logger.warning(f"Error during human simulation: {str(e)}")

def linkedin_login():
    """Login to LinkedIn with robust error handling and retry logic"""
    options = configure_chrome_options()
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Initialize WebDriver with explicit error handling
            try:
                # For Docker environment, use direct ChromeDriver path
                if os.path.exists('/usr/local/bin/chromedriver'):
                    driver = webdriver.Chrome(options=options)
                else:
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                
                # Stealth settings via CDP
                stealth_js = """
                () => {
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en', 'es']
                    });
                    window.chrome = {
                        runtime: {}
                    };
                }
                """
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": stealth_js
                })
                
                logger.info("WebDriver initialized successfully")
            except Exception as e:
                raise Exception(f"Failed to initialize WebDriver: {str(e)}")

            # Set page load timeout and script timeout
            driver.set_page_load_timeout(60)
            driver.set_script_timeout(60)
            
            try:
                # Navigate to LinkedIn homepage first (to set cookies)
                driver.get("https://www.linkedin.com")
                logger.info("Loaded LinkedIn homepage")
                time.sleep(random.uniform(2.0, 4.0))
                
                # Random mouse movements and scrolling
                simulate_human_behavior(driver)
                
                # Now navigate to login page
                driver.get("https://www.linkedin.com/login")
                logger.info("Loaded LinkedIn login page")
                
                # Random delay to mimic human behavior
                time.sleep(random.uniform(2.0, 5.0))
                
                # Wait for critical elements
                WebDriverWait(driver, 40).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                WebDriverWait(driver, 40).until(
                    EC.presence_of_element_located((By.ID, "password"))
                )
                
                # Get credentials from environment
                username = os.getenv("LINKEDIN_EMAIL")
                password = os.getenv("LINKEDIN_PASSWORD")
                
                if not username or not password:
                    raise Exception("LinkedIn credentials not found in environment variables")
                
                # Take screenshot before login attempt (for debugging)
                driver.save_screenshot("before_login.png")
                
                # Enter credentials with human-like typing
                email_field = driver.find_element(By.ID, "username")
                email_field.clear()
                for char in username:
                    email_field.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.2))
                
                time.sleep(random.uniform(0.8, 2.0))
                
                password_field = driver.find_element(By.ID, "password")
                password_field.clear()
                for char in password:
                    password_field.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.2))
                
                time.sleep(random.uniform(0.8, 2.0))
                
                # Submit form by clicking the button (more human-like than Enter key)
                try:
                    submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    submit_button.click()
                except NoSuchElementException:
                    # Fallback to Enter key if button not found
                    password_field.send_keys(Keys.RETURN)
                
                logger.info("Login form submitted")
                
                # Verify login success with increased patience
                try:
                    logger.info("Waiting for LinkedIn login to complete...")
                    WebDriverWait(driver, 90).until(
                        lambda d: any(x in d.current_url.lower() for x in 
                                      ["feed", "checkpoint", "login-submit", "challenge"])
                    )
                    
                    # Take screenshot after login (for debugging)
                    driver.save_screenshot("after_login.png")
                    
                    # Check for login issues
                    current_url = driver.current_url.lower()
                    
                    if any(x in current_url for x in ["checkpoint", "challenge"]):
                        logger.warning("LinkedIn security checkpoint detected")
                        driver.save_screenshot("linkedin_checkpoint.png")
                        raise Exception("LinkedIn security checkpoint detected - manual verification required")
                    
                    if "login-submit" in current_url:
                        error_msg = driver.find_elements(By.ID, "error-for-password")
                        if error_msg:
                            raise Exception(f"Login failed: {error_msg[0].text}")
                        else:
                            raise Exception("Login failed - incorrect credentials or LinkedIn has detected automation")
                    
                    if "feed" in current_url:
                        logger.info("LinkedIn login successful!")
                        # Successful login, but simulate normal browsing behavior before proceeding
                        simulate_human_behavior(driver)
                        return driver
                    
                    # Unknown redirect
                    driver.save_screenshot("unknown_redirect.png")
                    raise Exception(f"Unknown redirect after login: {current_url}")
                    
                except TimeoutException:
                    driver.save_screenshot("login_timeout.png")
                    logger.warning(f"Login timeout on attempt {retry_count + 1} of {max_retries}")
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        time.sleep(random.uniform(10, 20))  # Wait longer between retries
                        continue
                    else:
                        raise Exception("Login timeout - LinkedIn may be blocking automated logins")
                    
            except NoSuchElementException as e:
                driver.save_screenshot("missing_element.png")
                raise Exception(f"Could not find login page elements: {str(e)}")
                
        except WebDriverException as e:
            if 'driver' in locals():
                driver.save_screenshot(f"webdriver_error_{retry_count}.png")
                driver.quit()
            
            logger.warning(f"WebDriver error on attempt {retry_count + 1}: {str(e)}")
            if retry_count < max_retries - 1:
                retry_count += 1
                time.sleep(random.uniform(10, 20))  # Wait between retries
                continue
            else:
                raise Exception(f"LinkedIn login failed after {max_retries} attempts: {str(e)}")
                
        except Exception as e:
            if 'driver' in locals():
                driver.save_screenshot(f"login_error_{retry_count}.png")
                driver.quit()
            
            logger.warning(f"Error on attempt {retry_count + 1}: {str(e)}")
            if retry_count < max_retries - 1:
                retry_count += 1
                time.sleep(random.uniform(10, 20))  # Wait between retries
                continue
            else:
                raise Exception(f"LinkedIn login failed after {max_retries} attempts: {str(e)}")
        
        # If we reach here, all retries failed
        retry_count += 1
    
    raise Exception(f"LinkedIn login failed after {max_retries} attempts")

def search_profiles(driver, keyword, limit=20):
    """Search for LinkedIn profiles"""
    try:
        query = keyword.replace(" ", "%20")
        url = f"https://www.linkedin.com/search/results/people/?keywords={query}"
        driver.get(url)
        time.sleep(3)
        
        profiles = []
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while len(profiles) < limit:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.entity-result__item")
            
            for card in cards:
                try:
                    link = card.find_element(By.CSS_SELECTOR, "a.app-aware-link")
                    name = link.text.strip()
                    profile_url = link.get_attribute("href").split('?')[0]
                    
                    if name and profile_url and profile_url.startswith("https://www.linkedin.com/in/"):
                        profile = {"name": name, "url": profile_url}
                        if profile not in profiles:
                            profiles.append(profile)
                            if len(profiles) >= limit:
                                break
                except:
                    continue
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        return profiles[:limit]
    except Exception as e:
        raise Exception(f"Profile search failed: {str(e)}")

def extract_company_domain(driver, profile_url):
    """Extract company domain from profile"""
    try:
        driver.get(profile_url)
        time.sleep(3)
        
        # Try to find current position section
        try:
            company_section = driver.find_element(
                By.XPATH, 
                "//section[contains(@class, 'experience')]//li[contains(@class, 'experience-item')][1]"
            )
            company_link = company_section.find_element(
                By.XPATH, 
                ".//a[contains(@href, '/company/') or contains(@data-field, 'experience_company')]"
            )
            company_url = company_link.get_attribute("href")
        except:
            return None
        
        if not company_url:
            return None
            
        driver.get(company_url)
        time.sleep(3)
        
        # Try to find company website
        try:
            website_link = driver.find_element(
                By.XPATH,
                "//a[contains(@data-control-name, 'website') or contains(@href, 'http')]"
            )
            website = website_link.get_attribute("href")
        except:
            return None
            
        if not website:
            return None
            
        ext = tldextract.extract(website)
        return f"{ext.domain}.{ext.suffix}"
    except Exception as e:
        print(f"Error extracting company domain: {str(e)}")
        return None

def get_valid_email(first, last, domain):
    """Generate and validate email patterns"""
    if not domain:
        return None
        
    patterns = [
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}@{domain}",
        f"{last}.{first}@{domain}",
        f"{last}{first}@{domain}",
        f"{last}{first[0]}@{domain}"
    ]
    
    for email in patterns:
        try:
            if validate_email(email, verify=True):
                return email
        except:
            continue
    
    return None