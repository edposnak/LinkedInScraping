import sys
import time
import traceback
from threading import Thread
from datetime import datetime

from pyvirtualdisplay import Display
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement

from utils import is_url_valid, HumanCheckException, message_to_user


class JobSummaryNotFoundException(Exception): pass

class Profile:
    # Profile(linkedin_profile_url, contact_info, skills, job_history)
    def __init__(self, linkedin_url, contact_info, skills, job_history):
        self.linkedin_url = linkedin_url
        self.contact_info = contact_info
        self.skills = skills
        self.job_history = job_history

    def __str__(self):
        return f"Profile for {self.contact_info.name}\n   {self.contact_info}\n   {self.skills}\n   {self.job_history}"

class ContactInfo:
    def __init__(self, name):
        self.name = name
        self.attrs = 'websites phones emails twitter_urls'.split()
        for key in self.attrs: setattr(self, key, [])

    def __str__(self):
        return "\n   ".join([f"{attr}: {getattr(self, attr)}" for attr in self.attrs if getattr(self, attr)])

class Skills:
    def __init__(self, skills_list):
        self.skills_list = skills_list

    def __str__(self):
        return f"skills: {', '.join(self.skills_list)}"

class Company:
    def __init__(self):
        self.name = None
        self.linkedin_url = None
        self.industry = None
        self.employees = []

    def __str__(self):
        return f"{self.name} ({self.linkedin_url})"


class Position:
    def __init__(self):
        self.date_range = None
        self.duration = None
        self.title = None
        self.location = None

    def __str__(self):
        return f"{self.date_range or self.duration} {self.title} {self.location}"

    def get_start_and_end_dates(self):
        if not self.date_range: return None, None

        dates = self.date_range.split(' – ')
        if len(dates) > 1:
            begin = self.parse_date(dates[0])
            if dates[1] == 'less than a year':
                end = begin
            else:
                end = self.parse_date(dates[1])
                end = datetime.fromtimestamp(datetime.timestamp(end) + 24 * 60 * 60 * 31) # TODO 31 days is too long, also -1 second to get 12:59pm
        else:
            # TODO is this date_range string really a parsable date?
            print(f"split_date_range: '{self.date_range}' is not a range")
            end = begin = self.parse_date(self.date_range.strip())

        return begin, end

    # private
    def parse_date(self, date_str):
        if date_str == 'Present':
            return datetime.today()
        try:
            date = datetime.strptime(date_str, '%b %Y')
            return date
        except ValueError:
            try:
                date = datetime.strptime(date_str, '%Y')
                return date
            except ValueError:
                return None

class Job:
    def __init__(self):
        self.company = Company()
        self.positions = []
        self.total_duration = None

    def __str__(self):
        duration, location = self.positions[0].date_range, self.positions[0].location
        if len(self.positions) > 1:
            duration = self.total_duration
        return f"{self.company} {duration if duration else ''}"

    def add_position(self, position):
        self.positions.append(position)


class JobHistory:
    def __init__(self):
        self.jobs = []

    def __str__(self):
        result = 'job_history:'
        for job in self.jobs:
            result += f"\n      {job}"
            for position in job.positions:
                result += f"\n         {position}"
        return result

    def add(self, job: Job):
        self.jobs.append(job)



class ScrapingResult:
    def __init__(self, profile_or_message):
        if isinstance(profile_or_message, Profile):
            self.profile, self.message = profile_or_message, None
        else:
            self.profile, self.message = None, profile_or_message

    def is_error(self):
        return self.profile is None


class ProfileScraper(Thread):
    def __init__(self, identifier, urls_to_scrape, linkedin_credentials, headless_option=False):
        Thread.__init__(self)

        self._id = identifier
        self.entries = urls_to_scrape
        self.linkedin_credentials = linkedin_credentials

        self.headless_option = headless_option

        self.results = []
        self.industries_cache = {}

        self.wait_for_page_load_seconds = 2

        self.browser = self.launch_chromedriver(headless_option)

    def launch_chromedriver(self, headless_option):
        # Linux-specific code needed to open a new window of Chrome
        sys_platform = sys.platform.lower()
        if sys_platform == 'linux':
            chromedriver_path = 'Linux/chromedriver'
            self.display = Display(visible=0, size=(800, 800)).start()
        elif sys_platform == "darwin":
            chromedriver_path = 'MacOS/chromedriver'
        elif sys_platform == "windows":
            chromedriver_path = 'Windows/chromedriver.exe'
        chromedriver_options = webdriver.ChromeOptions()
        chromedriver_options.add_argument('--no-sandbox')
        if headless_option:
            chromedriver_options.add_argument('--headless')
        chromedriver_options.add_argument('--disable-dev-shm-usage')
        # chromedriver_options.binary_location = r"" + chromedriver_path
        return webdriver.Chrome(executable_path=chromedriver_path, options=chromedriver_options)

    def scrape_profile(self, linkedin_profile_url):
        if not is_url_valid(linkedin_profile_url): return ScrapingResult('BadFormattedLink')

        self.load_profile_page(linkedin_profile_url)

        # TODO, remove if redundant with contact_info
        # profile_name = self.browser.find_element_by_class_name('pv-top-card--list').find_element_by_tag_name('li').text.strip()
        # if not result['name']: return ScrapingResult(f"Could not extract name for {linkedin_profile_url}")

        contact_info = self.scrape_contact_info()

        self.scroll_to_bottom_to_load_all_content()
        print(f"scraping skills for {contact_info.name}")
        skills = self.scrape_skills()
        print(f"{contact_info.name} skills={skills}")

        print(f"scraping job_history for {contact_info.name}")
        self.click_on_show_more_jobs()
        job_history = self.scrape_job_history()
        print(f"{contact_info.name} job_history={job_history}")

        profile = Profile(linkedin_profile_url, contact_info, skills, job_history)
        return ScrapingResult(profile)

    def load_profile_page(self, profile_linkedin_url):
        self.browser.get(profile_linkedin_url)

        if not str(self.browser.current_url).strip() == profile_linkedin_url.strip():
            if self.browser.current_url == 'https://www.linkedin.com/in/unavailable/':
                return ScrapingResult('ProfileUnavailable')
            else:
                raise HumanCheckException

    def scroll_to_bottom_to_load_all_content(self):
        # Loading the entire page (LinkedIn loads content asynchronously based on your scrolling)
        loading_scroll_time = 1
        window_height = self.browser.execute_script("return window.innerHeight")
        scrolls = 1
        while scrolls * window_height < self.browser.execute_script("return document.body.offsetHeight"):
            self.browser.execute_script(f"window.scrollTo(0, {window_height * scrolls});")
            time.sleep(loading_scroll_time)
            scrolls += 1

    def scrape_contact_info(self, wait_for_modal_load_seconds=2):
        # click on 'Contact info' link to open up the modal
        self.browser.execute_script(
            "(function(){try{for(i in document.getElementsByTagName('a')){let el = document.getElementsByTagName('a')[i]; "
            "if(el.innerHTML.includes('Contact info')){el.click();}}}catch(e){}})()")
        time.sleep(wait_for_modal_load_seconds)

        name = self.browser.find_element_by_id('pv-contact-info').text.strip()
        result = ContactInfo(name)

        for contact_info_element in self.browser.find_elements_by_class_name('pv-contact-info__contact-type'):
            if 'ci-websites' in contact_info_element.get_attribute('class'):
                result.websites = [ a.get_attribute('href') for a in (contact_info_element.find_elements_by_tag_name('a')) ]
            elif 'ci-phone' in contact_info_element.get_attribute('class'):
                result.phones = []
                for phone_item in contact_info_element.find_elements_by_tag_name('li'):
                    phone_spans = phone_item.find_elements_by_tag_name('span')
                    result.phones.append({phone_spans[1].text.strip().strip("()"): phone_spans[0].text.strip()})
            elif 'ci-email' in contact_info_element.get_attribute('class'):
                result.emails = [ a.text for a in (contact_info_element.find_elements_by_tag_name('a')) ]
            elif 'ci-twitter' in contact_info_element.get_attribute('class'):
                result.twitter_urls = [ a.get_attribute('href') for a in (contact_info_element.find_elements_by_tag_name('a')) ]
            else:
                print(f"IGNORING contact info element with class={contact_info_element.get_attribute('class')}")


        # dismiss the Contact Info modal
        self.browser.execute_script("document.getElementsByClassName('artdeco-modal__dismiss')[0].click()")

        return result

    def scrape_skills(self, wait_for_skills_load_seconds=1):
        # Click on "Show More" once (should bring up all skills)
        self.browser.execute_script("document.getElementsByClassName('pv-skills-section__additional-skills')[0].click()")
        time.sleep(wait_for_skills_load_seconds)

        skills_list_element = self.browser.find_element_by_class_name('pv-skill-category-list__skills_list')
        skills_list = [ e.text.strip() for e in skills_list_element.find_elements_by_class_name('pv-skill-category-entity__name-text') ]

        return Skills(skills_list)

    def click_on_show_more_jobs(self, num_clicks=2):
        try:
            for _ in range(num_clicks):
                self.browser.execute_script("document.getElementsByClassName('pv-profile-section__see-more-inline')[0].click()")
                time.sleep(self.wait_for_page_load_seconds)
        except:
            # throws an exception if there aren't that many "see more" links to click
            pass

    def scrape_job_history(self):
        '''Returns a JobHistory containing multiple Jobs, which contain a Company and multiple Positions'''
        job_history = JobHistory()

        for n, job_element in enumerate(self.browser.find_element_by_id('experience-section').find_elements_by_tag_name('li')):
            job = Job()
            try:
                # <a data-control-name="background_details_company" href="/company/cuboulder/"
                a_tag = job_element.find_element_by_tag_name('a')
                company_linkedin_url = a_tag.get_attribute('href')
                job.company.linkedin_url = company_linkedin_url
                # job.company.industry = self.scrape_industry(company_linkedin_url)

            except NoSuchElementException as e:
                print(f"No company linkedin_url a_tag under {job_element.tag_name} class={job_element.get_attribute('class')} for job {n+1}")

            try:
                self.scrape_single_position_job(job, job_element)
                print(f"SCRAPED single_position_job")
            except JobSummaryNotFoundException as e:
                print(f"scrape_single_position_job({job_element.tag_name} class={job_element.get_attribute('class')}) raised {e} for job {n+1}")
                try:
                    print(f"TRYING scrape_multi_position_job ...")
                    self.scrape_multi_position_job(job, job_element)
                except Exception as e:
                    print(f"scrape_multi_position_job({job_element.tag_name} class={job_element.get_attribute('class')}) raised {e} for job {n+1}")
                    if job.company.linkedin_url: print(f"WEIRD, we got the company linkedin_url but failed to get the job data")
                    continue # give up on this job as we can't get anything
            except Exception as e:
                print(f"caught {e} for job {n+ 1}")

            print(f"Adding job {n+1} at {job.company.name}")
            job_history.add(job)

        return job_history

    def scrape_industry(self, company_linkedin_url):
        if company_linkedin_url not in self.industries_cache:
            try:
                self.browser.get(company_linkedin_url)
                self.industries_cache[company_linkedin_url] = self.browser.execute_script(
                    "return document.getElementsByClassName("
                    "'org-top-card-summary-info-list__info-item')["
                    "0].innerText")
            except NoSuchElementException as e:
                print(f"NOT FOUND industry for {company_linkedin_url} {e}")
                self.industries_cache[company_linkedin_url] = 'N/A'

        return self.industries_cache.get(company_linkedin_url)

    def scrape_single_position_job(self, job: Job, job_element: WebElement):
        summary_element = self.find_summary_element(job_element, 'pv-entity__summary-info')

        job.company.name = summary_element.find_element_by_class_name('pv-entity__secondary-title').text.strip()

        print(f"scrape_single_position_job found summary and got company name = {job.company.name}")

        position = Position()

        # title_elements = summary_element.find_elements_by_tag_name('h3')
        position.title = summary_element.find_element_by_class_name('t-16').text.strip()
        position.date_range = self.scrape_date_range(job_element)
        position.location = self.scrape_location(job_element)

        job.add_position(position)

    def scrape_multi_position_job(self, job: Job, job_element: WebElement):
        summary_element = self.find_summary_element(job_element, 'pv-entity__company-summary-info')

        #     <h3 class="t-16 t-black t-bold">
        #       <span class="visually-hidden">Company Name</span>
        #       <span>University of Colorado Boulder</span>
        #     </h3>
        # company_element = summary_element.find_element_by_class_name('t-16')
        company_element = summary_element.find_element_by_tag_name('h3')
        company_spans = company_element.find_elements_by_tag_name('span')
        job.company.name = company_spans[1].text.replace('Full-time', '').replace('Part-time', '').strip()

        print(f"scrape_multi_position_job found summary and got company name = {job.company.name}")

        duration_element = summary_element.find_element_by_tag_name('h4')
        duration_spans = duration_element.find_elements_by_tag_name('span')
        job.total_duration = duration_spans[1].text.strip()

        # <ul class="pv-entity__position-group mt2">
        positions_element = job_element.find_element_by_class_name('pv-entity__position-group')
        #     <li class="pv-entity__position-group-role-item">
        positions_items = positions_element.find_elements_by_class_name('pv-entity__position-group-role-item')

        for position_item in positions_items:
            position = Position()

            # <div class="pv-entity__summary-info-v2 pv-entity__summary-info--background-section pv-entity__summary-info-margin-top mb2">
            position_element = position_item.find_element_by_class_name('pv-entity__summary-info--background-section')

            # <h3 class="t-14"> <span>Title</span> <span>Web Designer</span>
            title_element = position_element.find_element_by_tag_name('h3')
            title_spans = title_element.find_elements_by_tag_name('span')
            position.title = title_spans[1].text.strip()

            position.date_range = self.scrape_date_range(job_element)
            position.location = self.scrape_location(position_element)
            position.duration = self.scrape_duration(position_element)

            job.add_position(position)


    def find_summary_element(self, dom_element, summary_class_name):
        try:
            summary_element = dom_element.find_element_by_class_name(summary_class_name)
        except NoSuchElementException as e:
            if summary_class_name in str(e):
                raise JobSummaryNotFoundException(f"JobSummaryNotFoundException could not find element with class {summary_class_name}")
        return summary_element


    def scrape_date_range(self, dom_element):
        # <h4 class="pv-entity__date-range"> <span>Dates Employed</span> <span>May 2007 - Mar 2008</span>
        try:
            date_range_element = dom_element.find_element_by_class_name('pv-entity__date-range')
            date_range_spans = date_range_element.find_elements_by_tag_name('span')
            return date_range_spans[1].text.strip()
        except NoSuchElementException:
            print(f"Could not find date_range")

    def scrape_location(self, dom_element):
        # <h4 class="pv-entity__location t-14"> <span>Location</span> <span>Boulder, CO</span> </h4>
        try:
            location_element = dom_element.find_element_by_class_name('pv-entity__location')
            location_spans = location_element.find_elements_by_tag_name('span')
            return location_spans[1].text.strip()
        except NoSuchElementException:
            print(f"Could not find location")

    def scrape_duration(self, position_element):
        # <h4 class="t-14"> <span>Employment Duration</span> <span>11 mos</span>
        duration_element = position_element.find_elements_by_tag_name('h4')[1]  # TODO super-brittle
        duration_spans = duration_element.find_elements_by_tag_name('span')
        duration = duration_spans[1].text.strip()
        return duration


    def scrape_company(self, company_linkedin_url):
        self.browser.get(company_linkedin_url)


    def scrape_coworkers(self, company_linkedin_url):
        self.browser.get(company_linkedin_url)

        # There are two types of URLs
        # search page - https://www.linkedin.com/search/results/all/?keywords=Recontek%20Systems%20Inc
        # company page - https://www.linkedin.com/company/...

        # 1. Search page contains a list of people known to work there (or work at a company with the same name e.g. XeteX)
        # all the employees (and other shit) are in a <ul class="search-results__list">
        # actual people are found in <div data-test-search-result="PROFILE" class="search-entity search-result search-result--person
        # company pages matching the name (e.g. XeteX) are found in <div data-test-search-result="COMPANY"

        # AVOID scraping a page like https://www.linkedin.com/search/results/all/?keywords=Self-Employed

        # Everything about the employee is in a <div class="search-result__info">

        # Their linkedin profile URL is in the first nested <a> tag
        #    <a data-control-name="search_srp_result" href="/in/liang/"
        # If that href is not a profile (e.g. # or https://www.linkedin.com/search/results/all/?keywords=SLKS%2C%20Inc) they are probably unreachable
        # If they are a reachable person, their name will be under a <span class="name actor-name">Lance Smith</span>
        # If they are unreachable it will be <span class="actor-name">LinkedIn Member</span>

        # The first two nested <p>s are not that useful 1 has the employee's current title and company and 2 has their current location
        # The third nested P could tell their role at the company if its text begins with "Past:"
        # If they included this company in their profile the third <p> will have their position at the company e.g. "Past: Software Engineer / Consultant at"
        # If not, the third <p> will have their current position and say something like "Current: Founder & CEO at Omniex Holdings, "
        # Make sure at least one of the <strong> tags at the end contains the company name
        # <p>Past: Software Engineer / Consultant at <strong>Xetex</strong> <strong>Inc</strong>. </p>

        # 2. Company page

        # If there are employees, there will be an <a data-control-name="topcard_see_all_employees">
        # Click See all XXX employees on LinkedIn
        # <a data-control-name="topcard_see_all_employees" href="/search/results/people/?facetCurrentCompany=%5B%223768740%22%5D" id="ember73" class="ember-view link-without-visited-state inline-block">
        #       <span class="v-align-middle"> See all 252 employees on LinkedIn </span> ... </a>

        # The number of search results is in <h3 class="search-results__total">254 results</h3>
        # Everything about the employee is in a <div class="search-result__info"> as above


        pass

    def scrape_recommendations(self, dom_element):
        # Find the recommendations section class="pv-profile-section pv-recommendations-section"

        # Make sure you're under "Received" tab (not "Given" tab)
        # First button is the received tab, if tabindex="-1" click it, then tabindex="0"
        # <button tabindex="-1" ...       Received (0) </button>

        # if there are no recommendations you see this
        # <p class="description t-16 t-black--light t-normal mt5"> Jerry hasn’t received any recommendations yet. </p>

        # Click Show more if exists
        # If there are more than 2 recommendations there will be a third button "Show more"
        # <button class="pv-profile-section__see-more-inline pv-profile-section__text-truncate-toggle link link-without-hover-state" aria-controls="recommendation-list" aria-expanded="false" type="button">Show more

        # recommendations are a series of <li class="pv-recommendation-entity"> elements
        # everything is found under an <a> element within the <li>

        # Recommender linkedin_profile
        # <a data-control-name="recommendation_details_profile" href=linkedin_profile_url_of_recommender

        #    <div class="pv-recommendation-entity__detail">
        # Recommender Name
        #       <h3 class="t-16 t-black t-bold">Mike P Lewis</h3>
        # Recommender Title
        #       <p class="pv-recommendation-entity__headline t-14 t-black t-normal pb1">CEO &amp; Co-founder of Onward</p>
        # Recommender Relationship
        #         <p class="t-12 t-black--light t-normal">
        #           November 5, 2013, Mike P managed Jennifer directly
        #         </p>
        #     </div>

        pass

    def login(self, logout_first=False):
        if logout_first:
            self.browser.get('https://www.linkedin.com/m/logout')

        username, password = self.linkedin_credentials
        self.browser.get('https://www.linkedin.com/uas/login')
        username_input = self.browser.find_element_by_id('username')
        username_input.send_keys(username)
        password_input = self.browser.find_element_by_id('password')
        password_input.send_keys(password)
        try:
            password_input.submit()
        except Exception as e:
            print(f"Login failed raised {e}")

    def print_time_left(self, count, start_time):
        '''Print predicted ending time of the script'''
        if count > 1:
            time_left = ((time.time() - start_time) / count) * (len(self.entries) - count + 1)
            ending_in = time.strftime("%H:%M:%S", time.gmtime(time_left))
        else:
            ending_in = "Unknown time"
        print(f"Scraper #{self._id}: Scraping profile {count} / {len(self.entries)} - {ending_in} left")


    def run(self):
        self.login()

        start_time, count = time.time(), 0

        for entry in self.entries:
            count += 1
            self.print_time_left(count, start_time)

            try:
                scraping_result = self.scrape_profile(entry)

            except HumanCheckException:
                scraping_result = ScrapingResult('TerminatedDueToHumanCheckError')
                if self.headless_option:
                    break # no point in continuing

                else: # Prompt the user to execute the human check in the browser
                    self.login(logout_first=True)
                    for pester in range(3):
                        if self.browser.current_url != 'https://www.linkedin.com/feed/':
                            message_to_user('Please execute human check manually', self.config)
                            time.sleep(30)

            except Exception as e:
                with open(f"errlog.txt", "a") as errlog: traceback.print_exc(file=errlog)
                scraping_result = ScrapingResult(f"{type(e)}{e.args}")
                # keep going and appending to errlog

            self.results.append(scraping_result)


        # Closing the Chrome instance
        self.browser.quit()

        end_time = time.time()
        elapsed_time = time.strftime('%H:%M:%S', time.gmtime(end_time - start_time))

        print(f"Scraper #{self._id}: Parsed {count} / {len(self.entries)} profiles in {elapsed_time}")

