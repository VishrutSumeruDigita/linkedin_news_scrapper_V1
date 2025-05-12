import os
import time
import random
import logging
import json
import shutil
import glob
import requests
import re
import asyncio
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from validate_email import validate_email
import tldextract
import dns.resolver

from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from dotenv import load_dotenv

# Import Proxycurl
try:
    from proxycurl.asyncio import Proxycurl
    PROXYCURL_AVAILABLE = True
except ImportError:
    PROXYCURL_AVAILABLE = False
    print("Proxycurl not available. Install with: pip install 'proxycurl-py[asyncio]'")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Proxycurl API client if available
proxycurl_client = None
PROXYCURL_API_KEY = os.getenv("PROXYCURL_API_KEY")

if PROXYCURL_API_KEY and PROXYCURL_AVAILABLE:
    # Set the API key in the environment
    os.environ["PROXYCURL_API_KEY"] = PROXYCURL_API_KEY
    try:
        proxycurl_client = Proxycurl()
        logger.info("Proxycurl client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Proxycurl client: {str(e)}")
        proxycurl_client = None
elif PROXYCURL_AVAILABLE:
    logger.warning("PROXYCURL_API_KEY not found in environment variables")
    
# Verify environment variables are loading correctly
logger.info(f"LinkedIn email exists: {bool(os.getenv('LINKEDIN_EMAIL'))}")
logger.info(f"LinkedIn password exists: {bool(os.getenv('LINKEDIN_PASSWORD'))}")
logger.info(f"Proxycurl API key exists: {bool(os.getenv('PROXYCURL_API_KEY'))}")

# Define constants for cookie management
COOKIE_FILE = "linkedin_cookies.json"
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")

def save_cookies(driver, filename=COOKIE_FILE):
    """Save browser cookies to a file"""
    try:
        cookies = driver.get_cookies()
        with open(filename, 'w') as f:
            json.dump(cookies, f)
        logger.info(f"Saved {len(cookies)} cookies to {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save cookies: {str(e)}")
        return False

def load_cookies(driver, filename=COOKIE_FILE):
    """Load cookies from file into browser session"""
    try:
        if not os.path.exists(filename):
            logger.warning(f"Cookie file {filename} not found")
            return False
            
        with open(filename, 'r') as f:
            cookies = json.load(f)
            
        # First access the domain
        driver.get("https://www.linkedin.com")
        time.sleep(2)
        
        # Add the cookies
        for cookie in cookies:
            # Some cookies can't be loaded, so we use try-except
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.debug(f"Couldn't add cookie {cookie.get('name')}: {str(e)}")
                
        logger.info(f"Loaded {len(cookies)} cookies from {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to load cookies: {str(e)}")
        return False

def find_chrome_user_data_dir():
    """Find Chrome user data directory based on OS"""
    home = Path.home()
    
    # Common locations for different OSes
    if os.name == 'nt':  # Windows
        paths = [
            home / "AppData/Local/Google/Chrome/User Data",
            home / "AppData/Local/Chromium/User Data",
        ]
    elif os.name == 'posix':  # Linux/Mac
        if os.path.exists('/Applications'):  # macOS
            paths = [
                home / "Library/Application Support/Google/Chrome",
                home / "Library/Application Support/Chromium",
            ]
        else:  # Linux
            paths = [
                home / ".config/google-chrome",
                home / ".config/chromium",
            ]
    else:
        return None
        
    # Return the first path that exists
    for path in paths:
        if path.exists():
            return str(path)
    
    return None

def configure_chrome_options(use_profile=False):
    """Configure Chrome options for Selenium with enhanced anti-detection measures"""
    options = Options()
    
    # Basic Docker-specific settings
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Enhanced stealth settings
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # More advanced anti-bot detection
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features")
    options.add_argument("--incognito")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    # Window size variations to appear more natural
    window_heights = [900, 1000, 1080]
    window_widths = [1400, 1600, 1920]
    random_height = random.choice(window_heights)
    random_width = random.choice(window_widths)
    options.add_argument(f"--window-size={random_width},{random_height}")
    
    # More modern and varied user agents (updated for 2025)
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Additional headers
    options.add_argument("--lang=en-US,en;q=0.9")
    options.add_argument("--accept-language=en-US,en;q=0.9")
    
    # Additional performance settings
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    
    # Use browser profile if specified
    if use_profile:
        user_data_dir = find_chrome_user_data_dir()
        if user_data_dir:
            # Create a temporary copy of the Chrome profile to avoid file locking issues
            temp_profile = os.path.join(os.getcwd(), "temp_chrome_profile")
            # Use Default profile
            source_profile = os.path.join(user_data_dir, "Default")
            
            # Check if source profile exists
            if os.path.exists(source_profile):
                # Remove old temp profile if it exists
                if os.path.exists(temp_profile):
                    try:
                        shutil.rmtree(temp_profile)
                    except:
                        pass
                
                # Copy only essential files to avoid Chrome lockfile issues
                os.makedirs(temp_profile, exist_ok=True)
                essential_files = ["Cookies", "Login Data", "Web Data", "Preferences"]
                for file in essential_files:
                    source_file = os.path.join(source_profile, file)
                    if os.path.exists(source_file):
                        try:
                            shutil.copy2(source_file, os.path.join(temp_profile, file))
                        except Exception as e:
                            logger.warning(f"Couldn't copy {file}: {str(e)}")
                
                options.add_argument(f"--user-data-dir={temp_profile}")
                logger.info(f"Using temporary Chrome profile at {temp_profile}")
            else:
                logger.warning(f"Chrome profile not found at {source_profile}")
    
    # Specify Chrome binary location
    if os.name == 'posix':  # Linux/Mac
        options.binary_location = '/usr/bin/google-chrome'
    else:  # Windows
        options.binary_location = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    
    return options

def simulate_human_behavior(driver):
    """Simulate random mouse movements and scrolling to mimic human behavior"""
    try:
        # More natural scrolling behavior
        for _ in range(random.randint(1, 3)):
            scroll_amount = random.randint(100, 500)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.7, 2.3))
        
        # Add random pauses with natural timing
        time.sleep(random.uniform(1.2, 3.5))
        
        # Back to top sometimes (not always)
        if random.random() > 0.3:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(0.5, 2.0))
        
        # Move mouse to random locations (simulated)
        for _ in range(random.randint(1, 4)):
            x = random.randint(100, 700)
            y = random.randint(100, 500)
            driver.execute_script(f"document.elementFromPoint({x}, {y}).dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}));")
            time.sleep(random.uniform(0.3, 1.2))
        
        # Random wait to simulate reading
        time.sleep(random.uniform(2.5, 6.0))
    except Exception as e:
        logger.warning(f"Error during human simulation: {str(e)}")

def check_login_status(driver):
    """Check if already logged in"""
    # Look for elements that indicate we're logged in
    try:
        # Check for feed URL
        if "feed" in driver.current_url.lower():
            return True
            
        # Check for navigation menu that only appears when logged in
        nav_menu = driver.find_elements(By.ID, "global-nav")
        if nav_menu:
            return True
            
        # Check for profile button
        profile_button = driver.find_elements(By.CSS_SELECTOR, "button[data-control-name='nav.settings']")
        if profile_button:
            return True
            
        return False
    except Exception as e:
        logger.warning(f"Error checking login status: {str(e)}")
        return False

def linkedin_login():
    """Login to LinkedIn with robust error handling and retry logic"""
    # First, try using cookies if available
    try:
        cookie_login_successful = False
        if os.path.exists(COOKIE_FILE):
            logger.info("Attempting login with saved cookies")
            options = configure_chrome_options()
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Add stealth scripts
            apply_stealth_scripts(driver)
            
            # Load cookies
            if load_cookies(driver, COOKIE_FILE):
                # Verify login status
                driver.get("https://www.linkedin.com")
                time.sleep(5)
                
                if check_login_status(driver):
                    logger.info("Successfully logged in with cookies")
                    simulate_human_behavior(driver)
                    return driver
                else:
                    logger.warning("Cookie login failed, will try with credentials")
                    driver.quit()
            else:
                logger.warning("Failed to load cookies, will try with credentials")
                driver.quit()
    except Exception as e:
        logger.warning(f"Cookie login attempt failed: {str(e)}")
        if 'driver' in locals():
            driver.quit()
    
    # Now try with user profile if cookie login failed
    try:
        logger.info("Attempting login with browser profile")
        options = configure_chrome_options(use_profile=True)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Add stealth scripts
        apply_stealth_scripts(driver)
        
        # Navigate to LinkedIn and check if already logged in
        driver.get("https://www.linkedin.com")
        time.sleep(5)
        
        if check_login_status(driver):
            logger.info("Successfully logged in with browser profile")
            # Save cookies for future use
            save_cookies(driver, COOKIE_FILE)
            simulate_human_behavior(driver)
            return driver
        else:
            logger.warning("Profile login failed, will try with credentials")
            driver.quit()
    except Exception as e:
        logger.warning(f"Profile login attempt failed: {str(e)}")
        if 'driver' in locals():
            driver.quit()
    
    # If all above failed, try with regular login
    options = configure_chrome_options()
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Initialize WebDriver with explicit error handling
            try:
                # Use webdriver-manager to automatically get the correct ChromeDriver version
                logger.info("Using ChromeDriverManager to get ChromeDriver matching current Chrome version")
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                
                # Apply stealth script
                apply_stealth_scripts(driver)
                
                logger.info("WebDriver initialized successfully")
            except Exception as e:
                raise Exception(f"Failed to initialize WebDriver: {str(e)}")

            # Set page load timeout and script timeout
            driver.set_page_load_timeout(60)
            driver.set_script_timeout(60)
            
            try:
                # First visit a common site before LinkedIn to establish a realistic browsing pattern
                initial_sites = ["https://www.google.com", "https://www.bing.com", "https://www.yahoo.com"]
                driver.get(random.choice(initial_sites))
                time.sleep(random.uniform(3.0, 5.0))
                simulate_human_behavior(driver)
                
                # Now navigate to LinkedIn homepage (not directly to login)
                driver.get("https://www.linkedin.com")
                logger.info("Loaded LinkedIn homepage")
                time.sleep(random.uniform(3.0, 6.0))
                
                # Random mouse movements and scrolling
                simulate_human_behavior(driver)
                
                # Clear cookies before login (sometimes helps with detection)
                if random.random() > 0.5:
                    driver.delete_all_cookies()
                    time.sleep(random.uniform(1.0, 2.0))
                
                # Now navigate to login page via UI instead of direct URL
                try:
                    login_button = driver.find_element(By.CSS_SELECTOR, "a[data-tracking-control-name='guest_homepage-basic_nav-header-signin']")
                    login_button.click()
                except:
                    # Fallback to direct URL if button not found
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
                try:
                    driver.save_screenshot("before_login.png")
                except Exception as ss_err:
                    logger.warning(f"Screenshot failed, but continuing: {str(ss_err)}")
                
                # Enter credentials with more human-like typing (variable speed)
                email_field = driver.find_element(By.ID, "username")
                email_field.clear()
                for char in username:
                    email_field.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.25))
                    # Occasional longer pause while typing
                    if random.random() > 0.9:
                        time.sleep(random.uniform(0.3, 0.7))
                
                time.sleep(random.uniform(0.8, 2.5))
                
                password_field = driver.find_element(By.ID, "password")
                password_field.clear()
                for char in password:
                    password_field.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.25))
                    # Occasional longer pause while typing
                    if random.random() > 0.9:
                        time.sleep(random.uniform(0.3, 0.7))
                
                time.sleep(random.uniform(0.8, 2.5))
                
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
                    try:
                        driver.save_screenshot("after_login.png")
                    except Exception as ss_err:
                        logger.warning(f"Screenshot failed, but continuing: {str(ss_err)}")
                    
                    # Check for login issues
                    current_url = driver.current_url.lower()
                    
                    if any(x in current_url for x in ["checkpoint", "challenge"]):
                        logger.warning("LinkedIn security checkpoint detected")
                        try:
                            driver.save_screenshot("linkedin_checkpoint.png")
                        except Exception:
                            pass
                        raise Exception("LinkedIn security checkpoint detected - manual verification required")
                    
                    if "login-submit" in current_url:
                        error_msg = driver.find_elements(By.ID, "error-for-password")
                        if error_msg:
                            raise Exception(f"Login failed: {error_msg[0].text}")
                        else:
                            raise Exception("Login failed - incorrect credentials or LinkedIn has detected automation")
                    
                    if "feed" in current_url:
                        logger.info("LinkedIn login successful!")
                        # Save cookies for future use
                        save_cookies(driver, COOKIE_FILE)
                        # Successful login, but simulate normal browsing behavior before proceeding
                        simulate_human_behavior(driver)
                        return driver
                    
                    # Unknown redirect
                    try:
                        driver.save_screenshot("unknown_redirect.png")
                    except Exception:
                        pass
                    raise Exception(f"Unknown redirect after login: {current_url}")
                    
                except TimeoutException:
                    try:
                        driver.save_screenshot("login_timeout.png")
                    except Exception:
                        pass
                    logger.warning(f"Login timeout on attempt {retry_count + 1} of {max_retries}")
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        time.sleep(random.uniform(10, 20))  # Wait longer between retries
                        continue
                    else:
                        raise Exception("Login timeout - LinkedIn may be blocking automated logins")
                    
            except NoSuchElementException as e:
                try:
                    driver.save_screenshot("missing_element.png")
                except Exception:
                    pass
                raise Exception(f"Could not find login page elements: {str(e)}")
                
        except WebDriverException as e:
            if 'driver' in locals():
                try:
                    driver.save_screenshot(f"webdriver_error_{retry_count}.png")
                except Exception:
                    pass
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
                try:
                    driver.save_screenshot(f"login_error_{retry_count}.png")
                except Exception:
                    pass
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

def apply_stealth_scripts(driver):
    """Apply advanced stealth scripts to the driver"""
    # Advanced stealth settings via CDP
    stealth_js = """
    () => {
        // Overwrite the navigator properties
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Add fake plugins array
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                return [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: 'Portable Document Format' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                ];
            }
        });
        
        // Add fake languages array
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'fr']
        });
        
        // Add fake permissions
        Object.defineProperty(navigator, 'permissions', {
            get: () => {
                return {
                    query: () => Promise.resolve({ state: 'granted' })
                };
            }
        });
        
        // Add fake chrome
        window.chrome = {
            runtime: {
                connect: () => {},
                sendMessage: () => {}
            }
        };
        
        // Fake hardware concurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });
        
        // Fake device memory
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });
        
        // Fake user agent platform
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32'
        });
        
        // Navigator override from cloudflare detection
        const newProto = navigator.__proto__;
        delete newProto.webdriver;
        
        // Remove broken image features
        ['height', 'width'].forEach(property => {
            // Store the original property descriptor
            const imageDescriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, property);
            // Redefine the property with a modified descriptor
            Object.defineProperty(HTMLImageElement.prototype, property, {
                ...imageDescriptor,
                get: function() {
                    // Return this[property] if the image is complete
                    if (this.complete) {
                        return imageDescriptor.get.apply(this);
                    }
                    // Return default values if the image isn't loaded
                    return property === 'height' ? 24 : 24;
                }
            });
        });
        
        // Spoof timezone
        const _Date = Date;
        const mockedDate = function(args) {
            return new _Date(args);
        };
        mockedDate.UTC = _Date.UTC;
        mockedDate.parse = _Date.parse;
        mockedDate.now = _Date.now;
        
        // Apply the modified date
        window.Date = mockedDate;
    }
    """
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": stealth_js
        })
    except Exception as e:
        logger.warning(f"CDP command failed, but continuing: {str(e)}")

def search_profiles(driver, keyword, limit=20):
    """Search for LinkedIn profiles with improved traversal and deduplication"""
    try:
        logger.info(f"Starting search for '{keyword}' with limit of {limit} profiles")
        query = keyword.replace(" ", "%20")
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={query}"
        logger.info(f"Navigating to search URL: {search_url}")
        driver.get(search_url)
        time.sleep(5)  # Increased initial wait time
        
        # Take screenshot of search page for debugging
        try:
            driver.save_screenshot("search_page.png")
            logger.info("Saved screenshot of search page")
        except Exception as e:
            logger.warning(f"Failed to save search page screenshot: {str(e)}")
        
        # Check if we need to handle any captcha or verification
        if "checkpoint" in driver.current_url.lower() or "challenge" in driver.current_url.lower():
            logger.error("LinkedIn security checkpoint detected during search")
            driver.save_screenshot("search_checkpoint.png")
            raise Exception("LinkedIn security checkpoint detected during search")
        
        # Use a set to track profile URLs and avoid duplicates
        processed_urls = set()
        profiles = []
        scroll_attempts = 0
        max_scroll_attempts = 10
        consecutive_no_new_profiles = 0
        max_consecutive_no_new = 3  # Max times to scroll with no new profiles
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        logger.info("Starting scroll and extract loop")
        
        # Main extraction loop - continue until we have enough profiles or hit limits
        while len(profiles) < limit and scroll_attempts < max_scroll_attempts and consecutive_no_new_profiles < max_consecutive_no_new:
            # Log current page source length for debugging
            page_source_length = len(driver.page_source)
            logger.info(f"Current page source length: {page_source_length} bytes")
            
            # Track how many new profiles we find in this iteration
            profiles_count_before = len(profiles)
            
            # Extract profiles with multiple approaches
            extract_profiles_from_page(driver, profiles, processed_urls, limit)
            
            # Calculate how many new profiles we found
            new_profiles_count = len(profiles) - profiles_count_before
            logger.info(f"Found {new_profiles_count} new profiles in this scroll")
            
            # If we found enough profiles, break
            if len(profiles) >= limit:
                break
                
            # Update consecutive no new profiles counter
            if new_profiles_count == 0:
                consecutive_no_new_profiles += 1
                logger.info(f"No new profiles found. Consecutive count: {consecutive_no_new_profiles}")
            else:
                consecutive_no_new_profiles = 0  # Reset counter when we find new profiles
            
            # Scroll down
            logger.info(f"Scrolling down (attempt {scroll_attempts + 1}/{max_scroll_attempts})")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2.0, 4.0))  # Increased wait time
            
            # Check if we've scrolled
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logger.info("No change in page height after scrolling")
                scroll_attempts += 1
                
                # Try to click "Show more results" button if available
                try:
                    show_more_buttons = driver.find_elements(By.CSS_SELECTOR, 
                        "button.artdeco-pagination__button--next, button.more-pagination, button[data-control-name='pagination-next']")
                    
                    # Also try to find "Next" button
                    if not show_more_buttons:
                        show_more_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')]")
                        
                    # Also try to find pagination by aria-label
                    if not show_more_buttons:
                        show_more_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Next']")
                    
                    if show_more_buttons and show_more_buttons[0].is_displayed() and show_more_buttons[0].is_enabled():
                        logger.info("Clicking 'Show more' or 'Next' button")
                        show_more_buttons[0].click()
                        time.sleep(3)
                        # Reset scroll attempts when pagination succeeds
                        scroll_attempts = 0
                        consecutive_no_new_profiles = 0
                except Exception as e:
                    logger.warning(f"Error clicking pagination button: {str(e)}")
            else:
                logger.info(f"Page height changed: {last_height} -> {new_height}")
                last_height = new_height
                scroll_attempts = 0  # Reset scroll attempts when successful
            
            # Add random delays to appear more human-like
            time.sleep(random.uniform(1.0, 3.0))
        
        logger.info(f"Search completed. Found {len(profiles)} profiles out of requested {limit}")
        return profiles[:limit]
    except Exception as e:
        logger.error(f"Profile search failed: {str(e)}")
        # Take error screenshot
        try:
            driver.save_screenshot("search_error.png")
        except:
            pass
        raise Exception(f"Profile search failed: {str(e)}")

def extract_profiles_from_page(driver, profiles, processed_urls, limit):
    """Extract profiles from the current page using multiple methods"""
    # Look for both older and newer LinkedIn profile card selectors
    cards = []
    selectors = [
        "div[data-chameleon-result-urn]",  # Current LinkedIn
        "div.entity-result__item",  # Recent LinkedIn
        "li.reusable-search__result-container",  # Also recent
        "li.search-result",  # Older LinkedIn
        "div.search-entity"  # Even older
    ]
    
    for selector in selectors:
        found_cards = driver.find_elements(By.CSS_SELECTOR, selector)
        if found_cards:
            logger.info(f"Found {len(found_cards)} cards with selector: {selector}")
            cards.extend(found_cards)
    
    if not cards:
        logger.warning("No profile cards found with any selector")
        # Take screenshot for debugging
        driver.save_screenshot(f"no_cards.png")
    
    # Direct approach: find all profile links on the page
    logger.info("Trying direct link extraction approach")
    try:
        # This approach finds all links with '/in/' pattern directly
        all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
        if all_links:
            logger.info(f"Found {len(all_links)} direct profile links")
            for link in all_links:
                try:
                    profile_url = link.get_attribute("href")
                    if profile_url:
                        # Clean the URL to remove query params
                        profile_url = profile_url.split('?')[0]
                        
                        # Only process LinkedIn profile URLs
                        if profile_url.startswith("https://www.linkedin.com/in/"):
                            # Skip if we've already processed this URL
                            if profile_url in processed_urls:
                                continue
                                
                            processed_urls.add(profile_url)
                            
                            # Try to get name from the link or its parent elements
                            name = link.text.strip()
                            
                            # If name is empty, try to find it from parent elements
                            if not name:
                                parent = link.find_element(By.XPATH, "./..")
                                name_elements = parent.find_elements(By.CSS_SELECTOR, 
                                    "span.entity-result__title-text, span.actor-name, span.name")
                                if name_elements:
                                    name = name_elements[0].text.strip()
                            
                            # If name is still empty, try finding it from search result structure
                            if not name:
                                # Try to navigate up a few levels to find name
                                for _ in range(3):
                                    try:
                                        parent = link.find_element(By.XPATH, "./..")
                                        name_elements = parent.find_elements(By.TAG_NAME, "span")
                                        for element in name_elements:
                                            potential_name = element.text.strip()
                                            if potential_name and len(potential_name) > 3 and " " in potential_name:
                                                name = potential_name
                                                break
                                        if name:
                                            break
                                        link = parent  # Move up one level
                                    except:
                                        break
                            
                            # If still no name found, extract from URL as last resort
                            if not name:
                                url_parts = profile_url.split("/in/")[1].split("/")
                                if url_parts:
                                    # Convert URL slug to name (e.g., john-doe becomes John Doe)
                                    name_from_url = url_parts[0].replace("-", " ").title()
                                    name = name_from_url
                            
                            if name:
                                profile = {"name": name, "url": profile_url}
                                if profile not in profiles:
                                    logger.info(f"Found profile: {name} at {profile_url}")
                                    profiles.append(profile)
                                    if len(profiles) >= limit:
                                        return
                except Exception as e:
                    logger.warning(f"Error processing direct link: {str(e)}")
    except Exception as e:
        logger.warning(f"Direct link extraction failed: {str(e)}")
    
    # Process cards only if we still need more profiles
    if len(profiles) < limit:
        logger.info("Processing individual cards")
        for card in cards:
            try:
                # Try to extract data from card
                card_html = card.get_attribute('outerHTML')
                # Find name and link within the card
                link_element = None
                
                # Try multiple link selectors
                link_selectors = [
                    "a[href*='/in/']",  # Direct profile links
                    "a.app-aware-link",  # Recent LinkedIn
                    "a[data-test-app-aware-link]"  # Another variant
                ]
                
                for selector in link_selectors:
                    links = card.find_elements(By.CSS_SELECTOR, selector)
                    if links:
                        for link in links:
                            href = link.get_attribute("href")
                            if href and "/in/" in href:
                                link_element = link
                                break
                        if link_element:
                            break
                
                if not link_element:
                    logger.debug("No valid profile link found in card")
                    continue
                
                # Get profile URL
                profile_url = link_element.get_attribute("href").split('?')[0]
                
                # Skip if we've already processed this URL
                if profile_url in processed_urls:
                    continue
                    
                processed_urls.add(profile_url)
                
                # Try to get name
                name = None
                
                # Try different name selectors depending on LinkedIn's structure
                name_selectors = [
                    "span.entity-result__title-text",
                    "span.actor-name",
                    "span.artdeco-entity-lockup__title",
                    "span.artdeco-entity-lockup__subtitle",
                    "span[data-test-result-lockup-name]"
                ]
                
                for selector in name_selectors:
                    try:
                        elements = card.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            name = elements[0].text.strip()
                            if name:
                                break
                    except:
                        pass
                
                # If still no name, try text from link
                if not name:
                    name = link_element.text.strip()
                
                # Last resort: extract from URL
                if not name and profile_url:
                    url_parts = profile_url.split("/in/")[1].split("/")
                    if url_parts:
                        name = url_parts[0].replace("-", " ").title()
                
                if name and profile_url and profile_url.startswith("https://www.linkedin.com/in/"):
                    profile = {"name": name, "url": profile_url}
                    if profile not in profiles:
                        logger.info(f"Found profile from card: {name} at {profile_url}")
                        profiles.append(profile)
                        if len(profiles) >= limit:
                            return
                else:
                    logger.debug(f"Invalid profile data - Name: '{name}', URL: '{profile_url}'")
            except Exception as e:
                logger.warning(f"Error processing card: {str(e)}")
                continue

def extract_company_domain(driver, profile_url):
    """Extract company domain from profile with enhanced extraction"""
    try:
        logger.info(f"Extracting company domain from profile: {profile_url}")
        driver.get(profile_url)
        time.sleep(5)  # Increased wait time for profile page to load
        
        # Take screenshot for debugging
        try:
            driver.save_screenshot(f"profile_{profile_url.split('/in/')[1].split('/')[0]}.png")
        except Exception as e:
            logger.warning(f"Failed to save profile screenshot: {str(e)}")
        
        company_url = None
        company_name = None
        domains = []
        
        # Approach 0: First try to extract clean company name from headline or current position
        headline_selectors = [
            "//div[contains(@class, 'pv-text-details__left-panel')]//h2",
            "//div[contains(@class, 'ph5')]//h2",
            "//div[contains(@class, 'profile-info')]//h2",
            "//div[contains(@class, 'ph5')]//div[contains(@class, 'mt2')]/div",
            "//div[contains(@class, 'mt2')]//span[contains(@class, 't-semibold')]"
        ]
        
        headline_text = None
        for selector in headline_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    headline_text = elements[0].text.strip()
                    if headline_text:
                        logger.info(f"Found headline text: {headline_text}")
                        break
            except Exception as e:
                logger.debug(f"Failed to find headline with selector {selector}: {str(e)}")
        
        # Extract company name from headline
        if headline_text:
            # Look for common patterns in headlines
            company_indicators = ["at ", "@ ", "with ", "for ", "- "]
            for indicator in company_indicators:
                if indicator in headline_text.lower():
                    parts = headline_text.split(indicator, 1)
                    if len(parts) > 1:
                        # Get the part after the indicator
                        potential_company = parts[1].strip()
                        # Clean up any trailing text after the company name
                        for separator in [" • ", " | ", " - ", " at ", ","]:
                            if separator in potential_company:
                                potential_company = potential_company.split(separator, 1)[0].strip()
                        
                        logger.info(f"Extracted potential company from headline: {potential_company}")
                        if potential_company and len(potential_company) > 1:
                            company_name = potential_company
                            break
        
        # Try different approaches to find company information
        
        # Approach 1: Look for experience section with multiple selectors
        experience_selectors = [
            "//section[contains(@class, 'experience')]//li[contains(@class, 'experience-item')][1]",
            "//section[contains(@id, 'experience-section')]//li[1]",
            "//div[contains(@class, 'experience-section')]//li[1]",
            "//section[@id='experience']//li[1]",
            "//div[contains(@class, 'pvs-list')]//li[contains(@class, 'artdeco-list__item')][1]"  # New LinkedIn
        ]
        
        for selector in experience_selectors:
            try:
                company_section = driver.find_element(By.XPATH, selector)
                logger.info(f"Found experience section with selector: {selector}")
                
                # Now look for company link within this section
                company_link_selectors = [
                    ".//a[contains(@href, '/company/') or contains(@data-field, 'experience_company')]",
                    ".//a[contains(@href, '/company/')]",
                    ".//a[contains(@data-control-name, 'background_details_company')]",
                    ".//a[contains(@class, 'optional-action-target-wrapper')]",
                    ".//span[contains(@class, 'enterprise-profile')]/a"
                ]
                
                for link_selector in company_link_selectors:
                    try:
                        company_links = company_section.find_elements(By.XPATH, link_selector)
                        if company_links:
                            company_url = company_links[0].get_attribute("href")
                            extracted_company_name = company_links[0].text.strip()
                            if extracted_company_name:
                                logger.info(f"Found company link: {company_url}, name: {extracted_company_name}")
                                company_name = extracted_company_name
                                break
                    except Exception as e:
                        logger.debug(f"Failed to find company link with selector {link_selector}: {str(e)}")
                
                if company_url:
                    break
            except Exception as e:
                logger.debug(f"Failed to find experience section with selector {selector}: {str(e)}")
        
        # Approach 2: If we still don't have a company URL, try to find it directly in the page
        if not company_url:
            logger.info("Trying alternative company extraction approach")
            try:
                # Find all links on the page
                all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/company/']")
                # Filter to only company links in the main content
                for link in all_links:
                    href = link.get_attribute("href")
                    if href and "/company/" in href:
                        company_url = href
                        extracted_company_name = link.text.strip()
                        if extracted_company_name:
                            logger.info(f"Found company via direct link approach: {company_url}, name: {extracted_company_name}")
                            if not company_name:  # Only update if we don't have a name yet
                                company_name = extracted_company_name
                            break
            except Exception as e:
                logger.warning(f"Alternative company extraction failed: {str(e)}")
        
        # If still no company URL, try to at least get company name
        if not company_name:
            logger.info("Searching for company name without URL")
            company_name_selectors = [
                "//div[contains(@class, 'experience-item__subtitle')]",
                "//span[contains(@class, 'experience-item-company')]",
                "//span[contains(@class, 'pv-entity__secondary-title')]",
                "//div[contains(@class, 'inline-show-more-text')]",
                "//span[contains(@class, 'hoverable-link-text')]"
            ]
            
            for selector in company_name_selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    if elements:
                        for element in elements:
                            text = element.text.strip()
                            if text and len(text) > 1 and not text.isdigit():
                                company_name = text
                                logger.info(f"Found company name without URL: {company_name}")
                                break
                    if company_name:
                        break
                except Exception as e:
                    logger.debug(f"Failed to find company name with selector {selector}: {str(e)}")
        
        # Clean up the company name before using it
        if company_name:
            # Remove common suffixes and prefixes
            for suffix in [' Inc', ' LLC', ' Ltd', ' Limited', ' Corp', ' Corporation', ' GmbH', ' Co', ' Pvt']:
                if company_name.endswith(suffix):
                    company_name = company_name.rsplit(suffix, 1)[0].strip()
            
            # Remove any non-company text like "full-time", "present", etc.
            noise_terms = ['full-time', 'part-time', 'present', '·', 'fulltime', 'area', 'india', 
                          'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                          '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014',
                          '2013', '2012', '2011', '2010', 'connection', 'profile', 'view', 'degree', 
                          'chieftechnology', 'officer', 'cto', 'ceo', 'present', 'yrs', 'mos', 'to']
            
            clean_name = company_name.lower()
            # Extract words from company name
            name_words = []
            for word in clean_name.split():
                word = ''.join(c for c in word if c.isalnum())  # Remove non-alphanumeric chars
                if word and word not in noise_terms and len(word) > 1:
                    name_words.append(word)
            
            # Reconstruct company name from clean words
            if name_words:
                clean_company_name = ' '.join(name_words)
                logger.info(f"Cleaned company name: {clean_company_name}")
                company_name = clean_company_name
        
        # If we have a company URL, visit it to get the website
        if company_url:
            logger.info(f"Visiting company page: {company_url}")
            driver.get(company_url)
            time.sleep(5)
            
            # Try to find company website link
            website_selectors = [
                "a[data-control-name='website']",
                "a[data-control-name='org_about_module_website_link']",
                "a[data-test-about-company-website-link]",
                "a[href*='http']:not([href*='linkedin.com'])"
            ]
            
            for selector in website_selectors:
                try:
                    website_links = driver.find_elements(By.CSS_SELECTOR, selector)
                    for website_link in website_links:
                        website = website_link.get_attribute("href")
                        if website and not "linkedin.com" in website.lower():
                            ext = tldextract.extract(website)
                            domain = f"{ext.domain}.{ext.suffix}"
                            # Make sure domain is valid
                            if ext.suffix and len(ext.domain) >= 2:
                                logger.info(f"Found website {website}, extracted domain: {domain}")
                                domains.append(domain)
                except Exception as e:
                    logger.debug(f"Failed to find website with selector {selector}: {str(e)}")
            
            # Take screenshot of company page for debugging
            try:
                driver.save_screenshot(f"company_page.png")
            except Exception:
                pass
        
        # If we have a company name but no domain yet, try to guess the domain
        if company_name and not domains:
            logger.info(f"Trying to guess domain from company name: {company_name}")
            # Clean company name and try common domain patterns
            clean_name = company_name.lower()
            # Remove any remaining non-alphanumeric characters
            clean_name = ''.join(c for c in clean_name if c.isalnum() or c.isspace())
            # Create a single word version (no spaces)
            single_word = clean_name.replace(' ', '')
            
            # Check for company names that are actually common known domains
            known_companies = {
                'google': 'google.com',
                'microsoft': 'microsoft.com',
                'apple': 'apple.com',
                'amazon': 'amazon.com',
                'facebook': 'facebook.com',
                'meta': 'meta.com',
                'netflix': 'netflix.com',
                'uber': 'uber.com',
                'linkedin': 'linkedin.com',
                'twitter': 'twitter.com',
                'tesla': 'tesla.com',
                'intel': 'intel.com',
                'amd': 'amd.com',
                'nvidia': 'nvidia.com',
                'ibm': 'ibm.com',
                'oracle': 'oracle.com',
                'salesforce': 'salesforce.com',
                'paypal': 'paypal.com',
                'adobe': 'adobe.com',
                'cisco': 'cisco.com',
                'ethereum': 'ethereum.org',
                'bitcoin': 'bitcoin.org',
                'perforce': 'perforce.com'
            }
            
            # Check if the company name or single word version is a known company
            if clean_name in known_companies:
                domains.append(known_companies[clean_name])
            elif single_word in known_companies:
                domains.append(known_companies[single_word])
            else:
                # Try some common domain patterns
                potential_domains = [
                    f"{single_word}.com",
                    f"{single_word}.io",
                    f"{single_word}.co",
                    f"{single_word}.org",
                    f"{single_word}.net"
                ]
                
                # Try additional variations if name is multiple words
                if ' ' in clean_name:
                    name_parts = clean_name.split()
                    if len(name_parts) >= 2:
                        # First letter of each word
                        acronym = ''.join(part[0] for part in name_parts)
                        potential_domains.append(f"{acronym}.com")
                        
                        # First word only
                        potential_domains.append(f"{name_parts[0]}.com")
                        
                        # First two words with hyphen
                        if len(name_parts) >= 2:
                            potential_domains.append(f"{name_parts[0]}-{name_parts[1]}.com")
                    
                logger.info(f"Guessing these potential domains: {potential_domains}")
                domains.extend(potential_domains)
        
        # Return the first domain we found or first potential domain
        if domains:
            # Clean the domain to ensure it's properly formatted
            cleaned_domain = clean_text_data(domains[0], is_domain=True)
            return cleaned_domain
        else:
            # If no domain found, use a placeholder based on company name if available
            if company_name:
                # Try to create a domain from the company name
                clean_name = ''.join(c for c in company_name.lower() if c.isalnum() or c.isspace())
                domain = clean_name.replace(' ', '') + '.com'
                logger.warning(f"No domain found, using placeholder: {domain}")
                return domain
            else:
                logger.warning(f"No company domain found for profile: {profile_url}")
                return "example.com"  # Default fallback domain
    except Exception as e:
        logger.error(f"Error extracting company domain: {str(e)}")
        return "example.com"  # Default fallback domain

def get_valid_email(first, last, domain):
    """Generate and validate email patterns with extended patterns and better validation"""
    if not domain:
        logger.warning("No domain provided for email generation")
        return None
        
    # Validate domain format first
    try:
        ext = tldextract.extract(domain)
        if not ext.domain or not ext.suffix or len(ext.domain) < 2:
            logger.warning(f"Invalid domain format: {domain}")
            return None
    except Exception as e:
        logger.warning(f"Error parsing domain {domain}: {str(e)}")
        return None
    
    logger.info(f"Generating email for {first} {last} at {domain}")
    
    # Remove non-alphanumeric characters from names
    first = ''.join(c for c in first if c.isalnum())
    last = ''.join(c for c in last if c.isalnum())
    
    # Proceed only if we have a valid first name
    if not first:
        logger.warning("No valid first name for email generation")
        return None
    
    # Use empty string for last name if it's missing
    if not last:
        last = ""
    
    # Generate list of email patterns to try
    patterns = []
    
    # Personal email patterns
    if last:  # Only add patterns with last name if it exists
        patterns.extend([
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{first[0]}{last}@{domain}",
            f"{last}.{first}@{domain}",
            f"{last}{first}@{domain}",
            f"{last}{first[0]}@{domain}",
            f"{first}-{last}@{domain}",
            f"{first}_{last}@{domain}",
            f"{first}.{last[0]}@{domain}",
            f"{first[0]}.{last}@{domain}"
        ])
    
    # Always add first name patterns
    patterns.append(f"{first}@{domain}")
    
    # Generic company email patterns
    generic_patterns = [
        f"info@{domain}",
        f"contact@{domain}",
        f"hello@{domain}",
        f"sales@{domain}",
        f"marketing@{domain}"
    ]
    
    # Try to validate each pattern
    for email in patterns:
        try:
            logger.info(f"Trying email: {email}")
            
            # First use a basic format check
            if "@" in email and "." in email.split("@")[1]:
                try:
                    # Then try domain validation
                    # Note: actual SMTP verification can trigger spam detection,
                    # so we just check if the domain has MX records
                    domain_part = email.split('@')[1]
                    if validate_email(email, check_mx=True, verify=False):
                        logger.info(f"Found valid email: {email}")
                        return email
                except Exception as e:
                    logger.debug(f"Email validation failed for {email}: {str(e)}")
                    # If verification fails but the email format is correct, we still consider it
                    if "@" in email and "." in email.split("@")[1]:
                        logger.info(f"Using unverified but well-formatted email: {email}")
                        return email
            
        except Exception as e:
            logger.debug(f"Error checking email {email}: {str(e)}")
            continue
    
    # If personal email patterns didn't work, try generic ones
    for email in generic_patterns:
        try:
            logger.info(f"Trying generic email: {email}")
            if validate_email(email, check_mx=True, verify=False):
                logger.info(f"Found valid generic email: {email}")
                return email
            elif "@" in email and "." in email.split("@")[1]:
                logger.info(f"Using unverified but well-formatted generic email: {email}")
                return email
        except Exception as e:
            logger.debug(f"Error checking generic email {email}: {str(e)}")
            continue
    
    # If all validations fail, return the most common pattern without validation
    if last:
        fallback_email = f"{first}.{last}@{domain}"
    else:
        fallback_email = f"{first}@{domain}"
        
    logger.warning(f"No valid email found, using fallback: {fallback_email}")
    return fallback_email

def fetch_email_from_apollo(profile_url, first_name=None, last_name=None, company_domain=None):
    """Use Apollo.io API to fetch email for a LinkedIn profile"""
    if not APOLLO_API_KEY:
        logger.warning("Apollo API key not found in environment variables")
        return None
    
    logger.info(f"Attempting to fetch email from Apollo.io for {profile_url}")
    
    try:
        # Extract LinkedIn ID from URL
        linkedin_id = None
        if '/in/' in profile_url:
            linkedin_id = profile_url.split('/in/')[1].split('/')[0].split('?')[0]
        
        if not linkedin_id:
            logger.warning("Could not extract LinkedIn ID from URL")
            return None
        
        logger.info(f"Extracted LinkedIn ID: {linkedin_id}")
        
        # API endpoint for Apollo.io
        api_url = "https://api.apollo.io/v1/people/match"
        
        payload = {
            "api_key": APOLLO_API_KEY,
            "reveal_personal_emails": True
        }
        
        # Add LinkedIn profile identifier
        payload["linkedin_url"] = f"linkedin.com/in/{linkedin_id}"
        
        # Add additional information if available to improve matching
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if company_domain:
            payload["domain"] = company_domain
        
        logger.info(f"Sending request to Apollo API: {json.dumps(payload, default=str)}")
        
        # Make the API call
        response = requests.post(api_url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Apollo API response: {json.dumps(data, default=str)}")
            
            # Check if person data exists
            if data and "person" in data and data["person"]:
                person = data["person"]
                
                # Check for email
                if "email" in person and person["email"]:
                    logger.info(f"Found email via Apollo: {person['email']}")
                    return person["email"]
                
                # Try work email if available
                if "work_email" in person and person["work_email"]:
                    logger.info(f"Found work email via Apollo: {person['work_email']}")
                    return person["work_email"]
                
                # Try personal email if available and allowed
                if "personal_email" in person and person["personal_email"]:
                    logger.info(f"Found personal email via Apollo: {person['personal_email']}")
                    return person["personal_email"]
                
                # Try normalized email fields
                email_fields = ["organization_email", "email_status", "emailer_campaign_emailer"]
                for field in email_fields:
                    if field in person and person[field]:
                        logger.info(f"Found email via Apollo field {field}: {person[field]}")
                        return person[field]
            
            logger.warning("No email found in Apollo response")
            return None
        else:
            logger.error(f"Apollo API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching email from Apollo: {str(e)}")
        return None

def fetch_email_free(profile_url, first_name=None, last_name=None, company_domain=None):
    """Use free methods to find an email for a LinkedIn profile without paid APIs"""
    logger.info(f"Attempting to find email for profile: {profile_url} using free methods")
    
    if not first_name or not company_domain:
        logger.warning("Missing required information (first name or company domain)")
        return None
    
    email_data = {
        "email": None,
        "source": None,
        "confidence": 0
    }
    
    # Method 1: DNS-based email verification for common patterns
    logger.info(f"Trying DNS-based email verification for {first_name} at {company_domain}")
    email_patterns = generate_email_patterns(first_name, last_name, company_domain)
    
    for pattern in email_patterns:
        if verify_email_exists_dns(pattern):
            email_data["email"] = pattern
            email_data["source"] = "dns_verification"
            email_data["confidence"] = 0.8
            logger.info(f"Found valid email via DNS verification: {pattern}")
            return email_data
    
    # Method 2: Use the email generation function we already have
    logger.info("Trying pattern-based email generation")
    email = get_valid_email(first_name.lower() if first_name else "", 
                          last_name.lower() if last_name else "", 
                          company_domain)
    
    if email:
        email_data["email"] = email
        email_data["source"] = "pattern_generation"
        email_data["confidence"] = 0.6
        return email_data
    
    # Method 3: Try to find email from GitHub if profile name is unique enough
    if first_name and last_name and len(first_name) > 2 and len(last_name) > 2:
        logger.info(f"Trying to find email from GitHub for {first_name} {last_name}")
        github_email = find_email_from_github(f"{first_name} {last_name}")
        if github_email and company_domain in github_email:
            email_data["email"] = github_email
            email_data["source"] = "github"
            email_data["confidence"] = 0.7
            return email_data
    
    # Method 4: Fallback to the most common pattern if nothing else worked
    if first_name and company_domain:
        fallback_email = f"{first_name.lower()}@{company_domain}"
        email_data["email"] = fallback_email
        email_data["source"] = "fallback"
        email_data["confidence"] = 0.4
        logger.info(f"Using fallback email pattern: {fallback_email}")
        return email_data
    
    logger.warning("Could not find email using free methods")
    return None

def generate_email_patterns(first_name, last_name, domain):
    """Generate common email patterns to test"""
    patterns = []
    
    # Convert names to lowercase and remove non-alphanumeric characters
    first = ''.join(c for c in first_name.lower() if c.isalnum())
    last = ''.join(c for c in last_name.lower() if c.isalnum()) if last_name else ""
    
    # Generate patterns in order of likelihood
    if first and last:
        patterns.extend([
            f"{first}@{domain}",
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{first[0]}{last}@{domain}",
            f"{first}_{last}@{domain}",
            f"{last}.{first}@{domain}",
            f"{first}-{last}@{domain}",
            f"{first[0]}.{last}@{domain}"
        ])
    else:
        patterns.append(f"{first}@{domain}")
    
    return patterns

def verify_email_exists_dns(email):
    """Verify if an email might exist by checking MX records"""
    try:
        domain = email.split('@')[1]
        # Try to get MX records for the domain
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            # If we found MX records, the domain can receive emails
            return True if mx_records else False
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            # No MX records, try A records as fallback
            try:
                a_records = dns.resolver.resolve(domain, 'A')
                return True if a_records else False
            except:
                return False
    except Exception as e:
        logger.debug(f"DNS verification error for {email}: {str(e)}")
        return False

def find_email_from_github(name):
    """Try to find a public email from GitHub profiles"""
    try:
        # Search GitHub for the user
        search_url = f"https://api.github.com/search/users?q={name.replace(' ', '+')}"
        response = requests.get(search_url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('items') and len(data['items']) > 0:
                # Check first 3 results at most
                for user in data['items'][:3]:
                    username = user.get('login')
                    if username:
                        # Get user details that may include email
                        user_url = f"https://api.github.com/users/{username}"
                        user_response = requests.get(user_url)
                        
                        if user_response.status_code == 200:
                            user_data = user_response.json()
                            if user_data.get('email'):
                                logger.info(f"Found GitHub email for {name}: {user_data['email']}")
                                return user_data['email']
                        
                        # If email not in profile, check public contributions
                        events_url = f"https://api.github.com/users/{username}/events/public"
                        events_response = requests.get(events_url)
                        
                        if events_response.status_code == 200:
                            events_data = events_response.json()
                            for event in events_data:
                                if event.get('type') == 'PushEvent' and event.get('payload', {}).get('commits'):
                                    for commit in event['payload']['commits']:
                                        if commit.get('author', {}).get('email'):
                                            email = commit['author']['email']
                                            # Filter out no-reply emails
                                            if not email.endswith('noreply.github.com'):
                                                logger.info(f"Found GitHub commit email for {name}: {email}")
                                                return email
        
        return None
    except Exception as e:
        logger.warning(f"Error searching GitHub for email: {str(e)}")
        return None

def clean_text_data(text, is_domain=False):
    """Clean text data by removing noise and irrelevant information"""
    if not text:
        return text
    
    logger.info(f"Cleaning text: {text}")
    
    # Convert to lowercase for better processing
    text = text.lower()
    
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    
    # Remove LinkedIn specific terminology
    linkedin_terms = [
        "view", "profile", "degree", "connection", "3rd", "2nd", "1st", "premium",
        "• 3rd+", "• 2nd", "• 1st", "'s profile", "view profile"
    ]
    
    for term in linkedin_terms:
        text = text.replace(term.lower(), "")
    
    # Remove suffixes related to job or connection status
    for suffix in ["'s profile", "view", "connection", "• 3rd+", "• 3rd", "• 2nd", "• 1st"]:
        if text.endswith(suffix.lower()):
            text = text[:-len(suffix)]
    
    # If this is a domain, apply more aggressive cleaning
    if is_domain:
        # Handle domain-specific cleaning
        
        # Don't return just ".com" or other TLDs
        if text == ".com" or text == ".org" or text == ".net" or text == ".io":
            return "example.com"  # Return a placeholder domain
            
        # If it's just a TLD, return a full placeholder domain
        if text.startswith("."):
            return "example" + text
        
        # Return proper domain if it matches a domain pattern
        domain_pattern = re.compile(r'([a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,})')
        domain_match = domain_pattern.search(text)
        if domain_match:
            return domain_match.group(1)
            
        # Remove common domain noise words
        domain_noise = [
            "chieftechnology", "chief", "technology", "officer", "cto", "ceo", "president",
            "founder", "co-founder", "cofounder", "erthaloka", "director", "manager",
            "lead", "head", "principal", "senior", "junior", "sr", "jr"
        ]
        
        for noise in domain_noise:
            # Remove repeated noise words
            while noise in text:
                text = text.replace(noise, "")
        
        # Use tldextract if the text looks like a domain
        if "." in text:
            try:
                ext = tldextract.extract(text)
                if ext.domain and ext.suffix:
                    return f"{ext.domain}.{ext.suffix}"
            except:
                pass
        
        # If we still don't have a proper domain, return a placeholder
        if text == "" or len(text) < 3 or "." not in text:
            return "example.com"
    
    # General cleaning for all text types
    # Remove special characters
    text = re.sub(r'[^\w\s.-]', '', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # If domain, ensure it doesn't have spaces
    if is_domain and " " in text:
        # Extract the first word that looks like a domain
        for word in text.split():
            if "." in word and len(word) > 3:
                return word
    
    logger.info(f"Cleaned text: {text}")
    return text

def clean_name(name):
    """Clean a name to extract just the person's name without LinkedIn additions"""
    if not name:
        return "", ""
    
    # Clean the raw name first
    cleaned_name = clean_text_data(name)
    
    # Remove any degree connection info
    cleaned_name = re.sub(r'\s*•\s*\d+(?:st|nd|rd|th).*$', '', cleaned_name)
    
    # Remove "View X's profile" patterns
    cleaned_name = re.sub(r'view\s+\w+\s+profile', '', cleaned_name)
    
    # Split into parts
    parts = cleaned_name.split()
    
    # Handle empty result
    if not parts:
        return "", ""
    
    # Extract first name
    first_name = parts[0].strip()
    
    # Extract last name (everything else)
    last_name = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    
    return first_name, last_name

def get_contact_details(linkedin_url, first_name=None, last_name=None, company_domain=None):
    """Comprehensive function to get all contact details for a profile using only free methods"""
    contact_data = {
        "email": None,
        "phone": None,
        "source": None
    }
    
    # Clean up the name and domain first
    if first_name:
        first_name = clean_text_data(first_name)
    
    if last_name:
        last_name = clean_text_data(last_name)
    
    if company_domain:
        company_domain = clean_text_data(company_domain, is_domain=True)
    
    # Use our free method for email finding
    email_result = fetch_email_free(linkedin_url, first_name, last_name, company_domain)
    
    if email_result and email_result["email"]:
        contact_data["email"] = email_result["email"]
        contact_data["source"] = email_result["source"]
    
    return contact_data

async def get_profile_data_from_proxycurl(linkedin_profile_url):
    """Get LinkedIn profile data using Proxycurl API"""
    if not proxycurl_client:
        logger.warning("Proxycurl client not available")
        return None
        
    try:
        logger.info(f"Fetching profile data from Proxycurl API: {linkedin_profile_url}")
        profile_data = await proxycurl_client.linkedin.person.get(
            linkedin_profile_url=linkedin_profile_url
        )
        
        if not profile_data:
            logger.warning(f"No data returned from Proxycurl for {linkedin_profile_url}")
            return None
            
        # Extract relevant data
        extracted_data = {
            "name": f"{profile_data.get('first_name', '')} {profile_data.get('last_name', '')}".strip(),
            "url": linkedin_profile_url,
            "first_name": profile_data.get("first_name", ""),
            "last_name": profile_data.get("last_name", ""),
            "headline": profile_data.get("headline", ""),
            "company_domain": None,
            "email": None
        }
        
        # Try to extract company domain
        if "experiences" in profile_data and profile_data["experiences"]:
            current_company = None
            # Find the current position (usually the first one)
            for exp in profile_data["experiences"]:
                if exp.get("ends_at") is None or not exp.get("ends_at").get("year"):
                    current_company = exp
                    break
                    
            if current_company:
                company_name = current_company.get("company", "")
                if company_name:
                    extracted_data["company_name"] = company_name
                    
                    # Try to get company domain from company data
                    company_linkedin_url = current_company.get("company_linkedin_url")
                    if company_linkedin_url and proxycurl_client:
                        try:
                            company_data = await proxycurl_client.linkedin.company.get(
                                url=company_linkedin_url
                            )
                            if company_data and company_data.get("website"):
                                website = company_data.get("website")
                                ext = tldextract.extract(website)
                                domain = f"{ext.domain}.{ext.suffix}"
                                extracted_data["company_domain"] = domain
                        except Exception as e:
                            logger.warning(f"Error getting company data from Proxycurl: {str(e)}")
        
        # Try to get email using Proxycurl's email finder if domain is available
        if extracted_data["company_domain"] and proxycurl_client:
            try:
                email_data = await proxycurl_client.linkedin.person.lookup_email(
                    first_name=extracted_data["first_name"],
                    last_name=extracted_data["last_name"],
                    company_domain=extracted_data["company_domain"]
                )
                
                if email_data and email_data.get("email"):
                    extracted_data["email"] = email_data.get("email")
                    extracted_data["email_source"] = "proxycurl"
            except Exception as e:
                logger.warning(f"Error looking up email from Proxycurl: {str(e)}")
                
        logger.info(f"Successfully extracted data from Proxycurl for {linkedin_profile_url}")
        return extracted_data
    except Exception as e:
        logger.error(f"Error fetching profile from Proxycurl: {str(e)}")
        return None

def get_company_domain_hybrid(driver, profile_url):
    """Get company domain using both Selenium and Proxycurl if available"""
    # First try with Proxycurl if available
    domain = None
    if proxycurl_client:
        try:
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            profile_data = loop.run_until_complete(get_profile_data_from_proxycurl(profile_url))
            loop.close()
            
            if profile_data and profile_data.get("company_domain"):
                domain = profile_data.get("company_domain")
                logger.info(f"Got company domain from Proxycurl: {domain}")
                return domain
        except Exception as e:
            logger.warning(f"Error getting company domain from Proxycurl: {str(e)}")
    
    # Fall back to Selenium-based extraction
    try:
        domain = extract_company_domain(driver, profile_url)
        if domain:
            logger.info(f"Got company domain from Selenium: {domain}")
        return domain
    except Exception as e:
        logger.error(f"Error in get_company_domain_hybrid: {str(e)}")
        return None

def get_profile_data_hybrid(driver, profile_url, use_selenium=True, use_proxycurl=True):
    """Get profile data using either Selenium, Proxycurl, or both"""
    profile_data = {"name": None, "url": profile_url, "first_name": None, "last_name": None, 
                    "company_domain": None, "email": None, "email_source": None}
    
    # Try Proxycurl first if available and enabled
    if proxycurl_client and use_proxycurl:
        try:
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            proxycurl_data = loop.run_until_complete(get_profile_data_from_proxycurl(profile_url))
            loop.close()
            
            if proxycurl_data:
                logger.info(f"Successfully got data from Proxycurl for {profile_url}")
                
                # Update our profile data with Proxycurl data
                for key in proxycurl_data:
                    if proxycurl_data[key]:
                        profile_data[key] = proxycurl_data[key]
                        
                # If we already have everything we need, return early
                if profile_data["name"] and profile_data["company_domain"] and profile_data["email"]:
                    return profile_data
        except Exception as e:
            logger.warning(f"Error getting data from Proxycurl: {str(e)}")
    
    # Fall back to Selenium if needed and enabled
    if use_selenium and driver:
        # If name is missing, extract it from URL or try to get it from the profile
        if not profile_data["name"]:
            try:
                # Extract from URL as a fallback
                url_parts = profile_url.split("/in/")[1].split("/")
                if url_parts:
                    name_from_url = url_parts[0].replace("-", " ").title()
                    profile_data["name"] = name_from_url
                    
                    # Try to split into first and last name
                    name_parts = name_from_url.split(" ", 1)
                    profile_data["first_name"] = name_parts[0]
                    profile_data["last_name"] = name_parts[1] if len(name_parts) > 1 else ""
                    
                # TODO: Add selenium-based name extraction if needed
            except Exception as e:
                logger.warning(f"Error extracting name: {str(e)}")
        
        # Clean up name parts if we have a name
        if profile_data["name"] and (not profile_data["first_name"] or not profile_data["last_name"]):
            try:
                first, last = clean_name(profile_data["name"])
                profile_data["first_name"] = first
                profile_data["last_name"] = last
            except Exception as e:
                logger.warning(f"Error cleaning name: {str(e)}")
        
        # If company domain is missing, try to extract it
        if not profile_data["company_domain"]:
            try:
                company_domain = extract_company_domain(driver, profile_url)
                if company_domain:
                    profile_data["company_domain"] = company_domain
            except Exception as e:
                logger.warning(f"Error extracting company domain: {str(e)}")
        
        # Clean up the company domain if we have one
        if profile_data["company_domain"]:
            profile_data["company_domain"] = clean_text_data(profile_data["company_domain"], is_domain=True)
    
    # Generate email if missing but we have the necessary data
    if not profile_data["email"] and profile_data["first_name"] and profile_data["company_domain"]:
        try:
            email_result = fetch_email_free(
                profile_url,
                profile_data["first_name"],
                profile_data["last_name"],
                profile_data["company_domain"]
            )
            
            if email_result and email_result["email"]:
                profile_data["email"] = email_result["email"]
                profile_data["email_source"] = email_result["source"]
        except Exception as e:
            logger.warning(f"Error generating email: {str(e)}")
    
    return profile_data