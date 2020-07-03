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

class HumanCheckException(Exception): pass


# Abstract class. Subclasses must implement a scrape(self, url) method that returns a ScrapingResult
class LinkedinScraper(Thread):
    def __init__(self, identifier, urls_to_scrape, linkedin_credentials, headless=False):
        super(LinkedinScraper, self).__init__()

        self._id = identifier

        # use linkedin convention of trailing '/' to prevent duplication of users/companies
        self.urls_to_scrape = [ canonize_linkedin_url(u) for u in urls_to_scrape ]

        self.linkedin_credentials = linkedin_credentials

        self.headless = headless # used to decide whether to bail when a human check occurs

        self.results = []
        self.company_cache = {}

        self.browser = self.launch_chromedriver()

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
                return ScrapingResult(error=f"Attempted to load a page that was unavailable", url=expected_page_url)
            # https://www.linkedin.com/checkpoint/challengesV2/... is a human check
            if 'linkedin.com/checkpoint/' in current_url:
                raise HumanCheckException


    def scroll_to_bottom_to_load_all_content(self, loading_scroll_time=1):
        # Loading the entire page (LinkedIn loads content asynchronously based on your scrolling)

        window_height = self.browser.execute_script("return window.innerHeight")
        scrolls = 1
        while scrolls * window_height < self.browser.execute_script("return document.body.offsetHeight"):
            self.browser.execute_script(f"window.scrollTo(0, {window_height * scrolls});")
            time.sleep(loading_scroll_time)
            scrolls += 1

    def print_time_left(self, count, start_time, url):
        '''Print predicted ending time of the script'''
        if count > 1:
            time_left = ((time.time() - start_time) / count) * (len(self.urls_to_scrape) - count + 1)
            ending_in = time.strftime("%H:%M:%S", time.gmtime(time_left))
        else:
            ending_in = "Unknown time"
        print(f"Scraper #{self._id}: Scraping URL {url} {count} / {len(self.urls_to_scrape)} - {ending_in} left")

    def message_to_user(message, speak=True):
        print(message)

        if speak:
            engine = pyttsx3.init()
            engine.say(message)
            engine.runAndWait()

    def run(self):
        self.login()

        start_time, count = time.time(), 0

        for url in self.urls_to_scrape:
            count += 1
            self.print_time_left(count, start_time, url)
            try:
                self.load_page(url)
                scraping_result = self.scrape(url)
                if not scraping_result.url: scraping_result.url = url

            except HumanCheckException:
                scraping_result = ScrapingResult(error='Manual human check encountered in headless mode', url=url)
                if self.headless:
                    break # no point in continuing

                else: # Prompt the user to execute the human check in the browser
                    self.login(logout_first=True)
                    for pester in range(3):
                        if self.browser.current_url != 'https://www.linkedin.com/feed/':
                            self.message_to_user('Please execute human check manually')
                            time.sleep(30)

            except Exception as e:
                with open(f"linkedin_scraper_errors.txt", "a") as errlog: traceback.print_exc(file=errlog)
                scraping_result = ScrapingResult(error=f"{type(e)}{e.args}", url=url)
                # keep going and appending to errlog as exceptions occur

            self.results.append(scraping_result)


        self.browser.quit()
        end_time = time.time()
        elapsed_time = time.strftime('%H:%M:%S', time.gmtime(end_time - start_time))
        print(f"Scraper #{self._id}: Scraped {count} / {len(self.urls_to_scrape)} URLs in {elapsed_time}")

