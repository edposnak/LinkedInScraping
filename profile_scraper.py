import sys
import time
import traceback
from threading import Thread

from pyvirtualdisplay import Display
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement

from utils import is_url_valid, HumanCheckException, message_to_user

from models import Employee, ContactInfo, Skills, Company, Position, Job, JobHistory, Recommendations, Recommendation


class JobSummaryNotFoundException(Exception): pass

class ScrapingResult:
    def __init__(self, employee_or_message):
        if isinstance(employee_or_message, Employee):
            self.employee, self.message = employee_or_message, None
        else:
            self.employee, self.message = None, employee_or_message

    def is_error(self):
        return self.employee is None


class ProfileScraper(Thread):
    def __init__(self, identifier, urls_to_scrape, linkedin_credentials, headless_option=False):
        Thread.__init__(self)

        self._id = identifier
        self.entries = urls_to_scrape
        self.linkedin_credentials = linkedin_credentials

        self.headless_option = headless_option

        self.results = []
        self.company_cache = {}

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

    def load_page(self, page_url):
        page_url = page_url.strip()
        self.browser.get(page_url)
        current_url = str(self.browser.current_url).strip()

        if not current_url == page_url:
            print(f"load_page tried to load {page_url} but ended up at {current_url}")
            if current_url == 'https://www.linkedin.com/in/unavailable/':
                return ScrapingResult('ProfileUnavailable')
            else:
                pass
                # TODO: figure out what the exact URL is that should raise the HumanCheckException
                # raise HumanCheckException


    def scrape_profile(self, linkedin_profile_url):
        if not is_url_valid(linkedin_profile_url): return ScrapingResult('BadFormattedLink')

        self.load_page(linkedin_profile_url)
        profile_name = self.browser.find_element_by_class_name('pv-top-card--list').find_element_by_tag_name('li').text.strip()
        employee = Employee(profile_name, linkedin_profile_url)

        employee.contact_info = self.scrape_contact_info()

        self.scroll_to_bottom_to_load_all_content()
        print(f"scraping skills for {employee.name}")
        employee.skills = self.scrape_skills()
        print(f"{employee.name} skills={employee.skills}")

        print(f"scraping job_history for {employee.name}")
        self.click_on_show_more_jobs()
        employee.job_history = self.scrape_job_history()
        print(f"{employee.name} job_history={employee.job_history}")

        print(f"scraping recommendations for {employee.name}")
        employee.recommendations = self.scrape_recommendations()
        print(f"{employee.name} recommendations={employee.recommendations}")

        # the below will navigate to other pages
        print(f"scraping companies for {employee.name}")
        for job in employee.job_history:
            print(f"scraping {job.company.name}")
            self.scrape_company(job.company) # updates company in place
            # self.scrape_employees(job.company)

        return ScrapingResult(employee)


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

    def click_on_show_more_jobs(self, num_clicks=2, wait_for_jobs_load_seconds=1):
        try:
            for _ in range(num_clicks):
                self.browser.execute_script("document.getElementsByClassName('pv-profile-section__see-more-inline')[0].click()")
                time.sleep(wait_for_jobs_load_seconds)
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

            position.date_range = self.scrape_date_range(position_element)
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

    def scrape_recommendations(self, wait_for_recommendations_load_seconds=1):
        recommendations = Recommendations()

        try:
            # Find the recommendations section if it exists
            # <section class="pv-recommendations-section">
            recommendations_element = self.browser.find_element_by_class_name('pv-recommendations-section')

            # Make sure you're under "Received" tab (not "Given" tab)
            # First button is the received tab
            # <button tabindex="-1" ...       Received (0) </button>

            received_tab_element = recommendations_element.find_element_by_css_selector("button.artdeco-tab")
            print(f"FOUND Received (x) tab")
            if received_tab_element.text.strip() == 'Received (0)': return recommendations
            # if there are no recommendations you might see this
            # <p class="description t-16 t-black--light t-normal mt5"> Jerry hasn’t received any recommendations yet. </p>

            # if the Received tab is hidden (i.e. tabindex="-1") click it, which will set tabindex="0" and load the received recommendations
            if received_tab_element.get_attribute('tabindex') == '-1':
                print(f"Clicking Received (x) tab ...")
                received_tab_element.click()
                time.sleep(wait_for_recommendations_load_seconds)

            # Click Show more if exists
            # If there are more than 2 recommendations there will be a third button "Show more"
            # <button class="pv-profile-section__see-more-inline pv-profile-section__text-truncate-toggle link link-without-hover-state"
            # aria-controls="recommendation-list" aria-expanded="false" type="button">Show more
            try:
                more_button = recommendations_element.find_element_by_class_name('pv-profile-section__see-more-inline')
                print(f"Clicking show more recommendations button ...")
                more_button.click()
                time.sleep(wait_for_recommendations_load_seconds)
            except NoSuchElementException as e:
                pass # this button is often not found

            # recommendations are a series of <li class="pv-recommendation-entity"> elements
            print(f"Looking for pv-recommendation-entity elements ...")
            print(f"found {len(recommendations_element.find_elements_by_class_name('pv-recommendation-entity'))} recommendations")
            for rec_element in recommendations_element.find_elements_by_class_name('pv-recommendation-entity'):
                recommendation = Recommendation()

                # <a data-control-name="recommendation_details_profile" href=linkedin_profile_url_of_recommender
                a_tag = rec_element.find_element_by_tag_name('a')
                recommendation.linkedin_url = a_tag.get_attribute('href')
                print(f"FOUND recommendation by {recommendation.linkedin_url}")

                # <div class="pv-recommendation-entity__detail">
                detail_element = a_tag.find_element_by_class_name('pv-recommendation-entity__detail')

                #      <h3 class="t-16 t-black t-bold">Mike P Lewis</h3>
                recommendation.name = detail_element.find_element_by_tag_name('h3').text.strip()

                p_tags = detail_element.find_elements_by_tag_name('p')
                #      <p class="pv-recommendation-entity__headline t-14 t-black t-normal pb1">CEO &amp; Co-founder of Onward</p>
                recommendation.title_co = p_tags[0].text.strip()

                #      <p class="t-12 t-black--light t-normal"> November 5, 2013, Mike P managed Jennifer directly </p>
                rec_date_relationship = p_tags[1].text.strip()
                parts = rec_date_relationship.split(',')
                recommendation.date =  ','.join(parts[0:2]).strip()
                recommendation.relationship = ''.join(parts[2:]).strip()

                # only add Received recommendations (hidden recommendations have blank name, etc.)
                if recommendation.name:
                    recommendations.add(recommendation)
                else: # if recommendation given matches any received mark them as reciprocal
                    for r in recommendations:
                        if r.linkedin_url == recommendation.linkedin_url: r.reciprocal = True


        except Exception as e:
            print(f"scrape_recommendations() raised {e}")

        return recommendations

    def scrape_company(self, company):
        if 'linkedin.com/company/' not in company.linkedin_url:
            print(f"not scraping {company.name} because the url does not contain '/linkedin.com/company/'")
            return

        about_page = company.linkedin_url.strip('/') + '/about/'
        try:
            self.load_page(about_page)
            print(f"loaded {about_page}")

            # This top card is redundant, but could be a good fallback
            # top_card_element = self.browser.find_element_by_class_name('org-top-card-primary-content__content')
            #
            # # <h1 class="org-top-card-summary__title t-24 t-black truncate" title="Power Pro Leasing">
            # name = top_card_element.find_element_by_class_name('org-top-card-summary__title').get_attribute('title').strip()
            # if name != company.name:
            #     print(f"WARNING: job on profile page listed company name as {company.name} by company page has {name}")
            #
            # # <div class="org-top-card-summary-info-list t-14 t-black--light">
            # #     <div class="org-top-card-summary-info-list__info-item"> Real Estate </div>
            # #       <div class="org-top-card-summary-info-list__info-item"> Greenwood Village, CO </div>
            # #       <div class="org-top-card-summary-info-list__info-item"> 339 followers </div>
            # divs = top_card_element.find_elements_by_class_name('org-top-card-summary-info-list__info-item')
            # company.industry = divs[0].text.strip()
            # company.headquarters = divs[1].text.strip()

            # <div class="org-grid__core-rail--no-margin-left">
            overview_element = self.browser.find_element_by_class_name('org-grid__core-rail--no-margin-left')

            # <dl class="overflow-hidden">
            dl_element = overview_element.find_element_by_tag_name('dl')

            #     <dt class="org-page-details__definition-term t-14 t-black t-bold"> Website </dt>
            #     <dd class="org-page-details__definition-text t-14 t-black--light t-normal">
            #         <a tabindex="0" data-control-name="page_details_module_website_external_link" rel="noopener noreferrer" target="_blank" href="http://powerproleasing.com"
            dd_elements = dl_element.find_elements_by_class_name('org-page-details__definition-text')
            company.website = dd_elements[0].find_element_by_tag_name('a').get_attribute('href')
            # company.website = dd_elements[0].find_element_by_css_selector("a[data-control-name='page_details_module_website_external_link']").get_attribute('href')

            offset = 0
            # If phone is present then offset == 1
            # <a tabindex="0" data-control-name="page_details_module_phone_external_link" rel="noopener noreferrer" target="_blank" href="tel:+1 (303) 492-1411"
            try:
                a_tag = dl_element.find_element_by_css_selector("a[data-control-name='page_details_module_phone_external_link']")
                company.phone = a_tag.get_attribute('href').strip()[4:]
                offset += 1
            except NoSuchElementException:
                pass # phone is not usually there

            # company.phone = dl_element.find_element_by_class_name('org-about-company-module__company-size-definition-text').text.strip()

            #     <dt class="org-page-details__definition-term t-14 t-black t-bold"> Industry </dt>
            #     <dd class="org-page-details__definition-text t-14 t-black--light t-normal"> Real Estate </dd>
            company.industry = dd_elements[offset+1].text.strip()

            #     <dt class="org-page-details__definition-term t-14 t-black t-bold"> Company size </dt>
            #     <dd class="org-about-company-module__company-size-definition-text t-14 t-black--light mb1 fl"> 2-10 employees </dd>
            company.size = dl_element.find_element_by_class_name('org-about-company-module__company-size-definition-text').text.strip()
            #     <dd class="org-page-details__employees-on-linkedin-count t-14 t-black--light mb5"> 11 on LinkedIn <span ...> ... </div></div></span></dd>
            company.current_linkedin_employees = int(dl_element.find_element_by_class_name('org-page-details__employees-on-linkedin-count').text.strip().split()[0].replace(',',''))

            #     <dt class="org-page-details__definition-term t-14 t-black t-bold"> Headquarters </dt>
            #     <dd class="org-page-details__definition-text t-14 t-black--light t-normal"> Greenwood Village, CO </dd>
            company.headquarters = dd_elements[offset+2].text.strip()

            #     <dt class="org-page-details__definition-term t-14 t-black t-bold"> Type </dt>
            #     <dd class="org-page-details__definition-text t-14 t-black--light t-normal"> Privately Held </dd>
            company.shareholder_type = dd_elements[offset+3].text.strip()

            #     <dt class="org-page-details__definition-term t-14 t-black t-bold"> Founded </dt>
            #     <dd class="org-page-details__definition-text t-14 t-black--light t-normal"> 2010 </dd>
            company.founded = dd_elements[4].text.strip()
        except Exception as e:
            print(f"scrape_company scraping {about_page} raised {e}")

    def scrape_employees(self, company):
        # AVOID scraping a page like https://www.linkedin.com/search/results/all/?keywords=Self-Employed
        if 'Self-Employed' in company.linkedin_url: return

        try:
            self.load_page(company.linkedin_url)

            # There are two types of pages that company.linkedin_url will load:
            # 1. company (home or about) page - https://www.linkedin.com/company/...
            # 2. search page - https://www.linkedin.com/search/results/all/?keywords=Recontek%20Systems%20Inc

            company_page_results = '/linkedin.com/company/' in self.browser.current_url
            if company_page_results:  # 1. Company (home or about) page

                # If there are employees, there will be an <a data-control-name="topcard_see_all_employees">
                see_employees_link = self.browser.find_element_by_css_selector("a[data-control-name='topcard_see_all_employees']").get_attribute('href')
                # <a data-control-name="topcard_see_all_employees" href="/search/results/people/?facetCurrentCompany=%5B%223768740%22%5D">
                self.load_page(see_employees_link)

                # The number of search results is in <h3 class="search-results__total">254 results</h3>
                company.num_linkedin_employees = int(self.browser.find_element_by_class_name('search-results__total').text.split()[0])

            # Now we have a search results page that can be scraped the same way regardless of whether or not it came from a company page
            # though when we don't come from a company page we get fuzzier data:
            # a. people may not have worked at the company (worked for a company with the same name e.g. XeteX)
            # b. may get company profiles that match the search string (e.g. XeteX)
            #    people are found in <div data-test-search-result="PROFILE" class="search-entity search-result search-result--person>
            #    company pages matching the name (e.g. XeteX) are found in <div data-test-search-result="COMPANY">

            # The page will contain 10 results. For more results scroll-down and click the "Next" button
            # <button aria-label="Next" id="ember591" class="artdeco-pagination__button artdeco-pagination__button--next >
            search_results_element = self.browser.find_element_by_css_selector('ul.search-results__list')

            # Everything about the employee is in a <div class="search-result__info">
            # <div class="search-result__info pt3 pb4 ph0">
            for result_element in search_results_element.find_elements_by_class_name('search-result__info'):
                # Their linkedin profile URL is in the first nested <a> tag
                #<a data-control-name="search_srp_result" href="/in/jennifergunther/"
                a_tag = result_element.find_element_by_css_selector("a[data-control-name='search_srp_result']")

                # If they are a reachable person, their name will be under a span e.g.
                # <span class="name actor-name">Jennifer Gunther</span>
                name = a_tag.find_element_by_class_name('actor-name').text.strip()
                # If they are unreachable it will be <span class="actor-name">LinkedIn Member</span>
                if 'LinkedIn Member' == name: continue
                linkedin_url = a_tag.get_attribute('href')
                # If that href is not a profile (e.g. # or https://www.linkedin.com/search/results/all/?keywords=SLKS%2C%20Inc) they are probably unreachable
                # TODO: make sure 'LinkedIn Member' catches all non-reachables and non-employees
                employee = Employee(name, linkedin_url)

                p_elements = a_tag.find_element_by_tag_name('p')
                # The first <p> has the employee's current title and sometimes company
                # <p class="subline-level-1 t-14 t-black t-normal search-result__truncate"> Founder at Frontside Creative </p>
                if company_page_results and p_elements:
                    title_co = p_elements[0].text.strip()
                    print(f"raw title_co ({company.name} company page) = {title_co}")
                    # title_co often endswith " at XXX Inc." which may be similar to, but not match exactly the company name e.g.
                    # "Co-founder & CEO - Omniex", "Co-Founder & CTO at Omniex, Inc.", "Head of Operations at Omniex Holdings, Inc."
                    if ' at ' in title_co: title_co = ' '.join(title_co.split(' at ')[0:-1]) # ' at ' works pretty well, though some use ' @ '
                    employee.job_history = JobHistory.from_single_position_title(company, title_co)

                # second <p> has their current location
                #    <p class="subline-level-2 t-12 t-black--light t-normal search-result__truncate"> Greater Denver Area </p>

                # The third <p> >could tell their role at the company if its text begins with "Past:" e.g. "Past: Software Engineer / Consultant at Xetex Inc."
                if not company_page_results and len(p_elements) > 2:
                    title_co = p_elements[2].text.strip()
                    print(f"raw title_co ({company.name} results page) = {title_co}")
                    title_co = title_co.strip('Past: ').strip('Current: ')
                    if ' at ' in title_co: title_co = ' '.join(title_co.split(' at ')[0:-1]) # ' at ' works pretty well, though some use ' @ '
                    employee.job_history = JobHistory.from_single_position_title(company, title_co)

                company.add_employee(employee)

        except Exception as e:
            print(f"scrape_employees({company.linkedin_url}) raised {e}")


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

