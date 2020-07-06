import sys
import time
import traceback
from threading import Thread

import pyttsx3
from selenium import webdriver
from pyvirtualdisplay import Display

# Encapsulates some result, may be data or some error message
from models import canonize_linkedin_url


class ScrapingResult:
    def __init__(self, data=None, error=None, url=None):
        self.data, self.error, self.url = data, error, url

class CaptchaEncounteredException(Exception): pass
class ScrapingException(Exception): pass


# Abstract class. Subclasses must implement a scrape(self, url) method that returns a ScrapingResult
class LinkedinScraper:
    def __init__(self, p_args):
        self.linkedin_credentials = (p_args.user, p_args.password)
        self.headless = p_args.headless # used to decide whether to bail when a human check occurs

        self.blocked_by_captcha = False

        self.browser = self.launch_chromedriver()
        self.login()


    def login(self, logout_first=False):
        if logout_first: self.browser.get('https://www.linkedin.com/m/logout')

        username, password = self.linkedin_credentials
        self.load_page('https://www.linkedin.com/uas/login')

        username_input = self.browser.find_element_by_id('username')
        username_input.send_keys(username)
        password_input = self.browser.find_element_by_id('password')
        password_input.send_keys(password)
        try:
            password_input.submit()
        except Exception as e:
            print(f"Login failed raised {e}")

    def launch_chromedriver(self):
        # Linux-specific code needed to open a new window of Chrome
        sys_platform = sys.platform.lower()
        if sys_platform == 'linux':
            chromedriver_path = 'Linux/chromedriver'
            self.display = Display(visible=0, size=(800, 800)).start()
        elif sys_platform == "darwin":
            chromedriver_path = 'MacOS/chromedriver'
        elif sys_platform == "windows":
            chromedriver_path = 'Windows/chromedriver.exe'
        else:
            raise SystemError(f"cannot determine a chromedriver to use sys_platform={sys_platform}")
        chromedriver_options = webdriver.ChromeOptions()
        chromedriver_options.add_argument('--no-sandbox')
        if self.headless: chromedriver_options.add_argument('--headless')
        chromedriver_options.add_argument('--disable-dev-shm-usage')
        # chromedriver_options.binary_location = r"" + chromedriver_path
        return webdriver.Chrome(executable_path=chromedriver_path, options=chromedriver_options)

    def reload_page(self):
        page_url = self.browser.current_url
        self.browser.get(page_url)
        self.check_loaded_page(page_url)

    def load_page(self, page_url):
        page_url = page_url.strip()
        if self.browser.current_url == page_url:
            print(f"load_page already on {page_url}")
            return

        self.browser.get(page_url)
        self.check_loaded_page(page_url)

    def check_loaded_page(self, expected_page_url):
        current_url = self.browser.current_url.strip()
        if not current_url == expected_page_url:
            # print(f"load_page tried to load {page_url} but ended up at {current_url}")
            if current_url == 'https://www.linkedin.com/in/unavailable/':
                raise ScrapingException(f"Attempted to load a page that was unavailable url={expected_page_url}")
            # https://www.linkedin.com/checkpoint/challengesV2/... is a human check
            if 'linkedin.com/checkpoint/' in current_url:
                raise CaptchaEncounteredException


    def scroll_to_bottom_to_load_all_content(self, loading_scroll_time=1):
        # Loading the entire page (LinkedIn loads content asynchronously based on your scrolling)

        window_height = self.browser.execute_script("return window.innerHeight")
        scrolls = 1
        while scrolls * window_height < self.browser.execute_script("return document.body.offsetHeight"):
            self.browser.execute_script(f"window.scrollTo(0, {window_height * scrolls});")
            time.sleep(loading_scroll_time)
            scrolls += 1

    def notify_user(self, message, speak=True):
        print(message)
        if speak:
            engine = pyttsx3.init()
            engine.say(message)
            engine.runAndWait()

    def clear_captcha(self):
        '''Prompt the user to manually clear the captcha in the browser'''
        back_to_normal_url = 'https://www.linkedin.com/feed/'

        self.login(logout_first=True)

        # Prompt the user to manually clear the captcha and check if successful
        for pester in range(3):
            self.notify_user('Please manually clear the captcha')
            time.sleep(30)
            if self.browser.current_url == back_to_normal_url:
                self.blocked_by_captcha = False
                break


    def run(self, url_to_scrape):
        # use linkedin convention of trailing '/' to prevent duplication of users/companies
        url = canonize_linkedin_url(url_to_scrape)

        if self.blocked_by_captcha:
            if self.headless: # no point in continuing
                return ScrapingResult(error='Captcha encountered in headless mode', url=url)
            else:
                self.clear_captcha()

        try:
            if self.blocked_by_captcha: raise CaptchaEncounteredException
            self.load_page(url)
            scraping_result = self.scrape(url)
            scraping_result.url = url

        except CaptchaEncounteredException:
            return ScrapingResult(error='Captcha encountered but not cleared manually', url=url)
            self.blocked_by_captcha = True

        except Exception as e:
            with open(f"linkedin_scraper_errors.txt", "a") as errlog: traceback.print_exc(file=errlog)
            scraping_result = ScrapingResult(error=f"{type(e)}{e.args}", url=url)
            # keep going and appending to errlog as exceptions occur

        return scraping_result


    def shutdown(self):
        self.browser.quit()

