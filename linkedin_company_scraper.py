import traceback

from linkedin_scraper import LinkedinScraper, ScrapingResult

from selenium.common.exceptions import NoSuchElementException

from models import Person, JobHistory, Company

class LinkedinCompanyScraper(LinkedinScraper):
    def __init__(self, *args):
        super(LinkedinCompanyScraper, self).__init__(*args)

    def scrape(self, linkedin_company_url):
        print(f"LinkedinCompanyScraper scraping {linkedin_company_url}")
        company = Company()
        company.linkedin_url = linkedin_company_url

        try:
            self.scrape_overview(company)
            self.scrape_employees(company)
            print(f"FOUND {len(company.employees) if company.employees else 0} employees for {company.name or company.linkedin_url}")
            return ScrapingResult(company)

        except Exception as e:
            traceback.print_exc()
            print(f"LinkedinCompanyScraper raised {e}")
            if company.name: # partial result
                return ScrapingResult(company, error=e)
            else:
                return ScrapingResult(None, error=e)


    def is_company_page(self, url):
        return 'linkedin.com/company/' in url or 'linkedin.com/school/' in url

    def scrape_overview(self, company):
        if not self.is_company_page(company.linkedin_url):
            print(f"cannot scrape overview of {company.linkedin_url} because it is not a linkedin company page'")
            return

        about_page = company.linkedin_url if company.linkedin_url.endswith('about/') else company.linkedin_url.strip('/') + '/about/'
        self.load_page(about_page)

        # 1. Scrape top card section

        # This top card has the company name, industry, and headquarters (some of which is redundant with the overview)
        top_card_element = self.browser.find_element_by_class_name('org-top-card-primary-content__content')

        # <h1 class="org-top-card-summary__title t-24 t-black truncate" title="Power Pro Leasing">
        company.name = top_card_element.find_element_by_class_name('org-top-card-summary__title').get_attribute('title').strip()
        print(f"FOUND Company Name = {company.name}")

        # Don't bother trying to figure out industry / headquarters from top card, if it exists we'll get it from Overview below
        # <div class="org-top-card-summary-info-list t-14 t-black--light">
        #     <div class="org-top-card-summary-info-list__info-item"> Real Estate </div>
        # info_list_element = top_card_element.find_element_by_class_name('org-top-card-summary-info-list')
        # try:
        #     industry_div = info_list_element.find_element_by_xpath("div[@class='org-top-card-summary-info-list__info-item']")
        #     company.industry = industry_div.text.strip()
        # except NoSuchElementException as e:
        #     pass # industry/headquarters are not always there
        #
        # #     <div class="inline-block">
        # #         <div class="org-top-card-summary-info-list__info-item"> Greenwood Village, CO </div>
        # #         <div class="org-top-card-summary-info-list__info-item"> 362 followers </div>
        # headquarters_followers_div = info_list_element.find_element_by_xpath("div[@class='inline-block']") # appears to always be there
        # headquarters_or_followers = headquarters_followers_div.find_elements_by_class_name('org-top-card-summary-info-list__info-item')[0].text.strip()
        # company.headquarters = headquarters_or_followers if 'followers' not in headquarters_or_followers else None

        # 2. Scrape overview section

        # <div class="org-grid__core-rail--no-margin-left">
        overview_element = self.browser.find_element_by_class_name('org-grid__core-rail--no-margin-left')

        # <dl class="overflow-hidden">
        dl_element = overview_element.find_element_by_tag_name('dl')

        dds_and_dts = dl_element.find_elements_by_xpath('*')
        next_field = None
        for el in dds_and_dts:
            if el.tag_name == 'dt':
                next_field = el.text.strip()
            elif el.tag_name == 'dd':
                info = el.text.strip()
                if next_field == 'Website':
                    company.website = el.find_element_by_tag_name('a').get_attribute('href')
                elif next_field == 'Phone':
                    company.phone = el.find_element_by_tag_name('a').get_attribute('href').strip()[4:]  # remove 'tel:'
                elif next_field == 'Industry':
                    company.industry = info
                elif next_field == 'Company size':
                    #     <dd class="org-about-company-module__company-size-definition-text t-14 t-black--light mb1 fl"> 2-10 employees </dd>
                    if 'org-about-company-module__company-size-definition-text' in el.get_attribute("class"):
                        company.size = info
                    #     <dd class="org-page-details__employees-on-linkedin-count t-14 t-black--light mb5"> 11 on LinkedIn <span ...> ... </div></div></span></dd>
                    elif 'org-page-details__employees-on-linkedin-count' in el.get_attribute("class"):
                        company.current_linkedin_employees = int(info.split()[0].replace(',', ''))
                    else:
                        print(f"WTF next_field == 'Company size' but didn't find size or current_linkedin_employees")
                elif next_field == 'Headquarters':
                    company.headquarters = info
                elif next_field == 'Type':
                    company.shareholder_type = info
                elif next_field == 'Founded':
                    company.founded = info
                elif next_field == 'Specialties':
                    pass # don't care about scraping specialties yet
                else:
                    print(f"WTF next_field == {next_field}")


    def scrape_employees(self, company):
        # AVOID scraping a page like https://www.linkedin.com/search/results/all/?keywords=Self-Employed
        if 'Self-Employed' in company.linkedin_url:
            print(f"cannot scrape employees of {company.linkedin_url} because it is a search on Self-Employed'")
            return

        self.load_page(company.linkedin_url)

        # There are two types of pages that company.linkedin_url will load:
        # 1. company (home or about) page - https://www.linkedin.com/company/... or  https://www.linkedin.com/school/...
        # 2. search page - https://www.linkedin.com/search/results/all/?keywords=Recontek%20Systems%20Inc

        company_page_results = self.is_company_page(self.browser.current_url)

        if not company_page_results and 'linkedin.com/search/results' not in self.browser.current_url:
            print(f"WTF: not a company page and not a results page url={self.browser.current_url}")

        if company_page_results:  # we're on a Company (home or about) page
            # If there are employees, there should be an <a> to click
            # <a data-control-name="topcard_see_all_employees" href="/search/results/people/?facetCurrentCompany=%5B%223768740%22%5D">
            see_employees_link = self.browser.find_element_by_css_selector("a[data-control-name='topcard_see_all_employees']").get_attribute('href')
            print(f"calling load_page('{see_employees_link}') ...")
            self.load_page(see_employees_link)

            # The number of search results is in <h3 class="search-results__total">254 results</h3>
            # for large numbers it may look like this 'About 13,000 results'
            results_str = self.browser.find_element_by_class_name('search-results__total').text.replace(',', '').strip('About ')
            company.num_linkedin_results = int(results_str.split()[0])

        # Now we have a search results page that can be scraped the same way regardless of whether or not it came from a company page
        # though when we don't come from a company page we get fuzzier data:
        # a. people may not have worked at the company (worked for a company with the same name e.g. XeteX)
        # b. may get company profiles that match the search string (e.g. XeteX)
        #    people are found in <div data-test-search-result="PROFILE" class="search-entity search-result search-result--person>
        #    company pages matching the name (e.g. XeteX) are found in <div data-test-search-result="COMPANY">

        # The page will contain 10 results. For more results scroll-down and click the "Next" button
        # <button aria-label="Next" id="ember591" class="artdeco-pagination__button artdeco-pagination__button--next >
        search_results_element = self.browser.find_element_by_css_selector('ul.search-results__list')

        # Everything about the person is in a <div class="search-result__info">
        # <div class="search-result__info pt3 pb4 ph0">
        for result_element in search_results_element.find_elements_by_class_name('search-result__info'):
            # Their linkedin profile URL is in the first nested <a> tag
            #<a data-control-name="search_srp_result" href="/in/jennifergunther/"
            a_tag = result_element.find_element_by_css_selector("a[data-control-name='search_srp_result']")

            # If they are a reachable person, their name will be under a span e.g.
            # <span class="name actor-name">Jennifer Gunther</span>
            try:
                name = a_tag.find_element_by_class_name('actor-name').text.strip()
                # If they are unreachable it will be <span class="actor-name">LinkedIn Member</span>
                if 'LinkedIn Member' == name:
                    print(f"BOO can't scrape out-of-network person named LinkedIn Member")
                    continue
                linkedin_url = a_tag.get_attribute('href')
                # If that href is not a profile (e.g. # or https://www.linkedin.com/search/results/all/?keywords=SLKS%2C%20Inc) they are probably unreachable
                # TODO: make sure 'LinkedIn Member' catches all non-reachables and non-employees
                person = Person(name, linkedin_url)
            except Exception as e:
                print(f"scrape employee moving on because result raised {e}")
                continue

            p_elements = result_element.find_elements_by_tag_name('p')
            # The first <p> has the person's summary
            # <p class="subline-level-1 t-14 t-black t-normal search-result__truncate"> Founder at Frontside Creative </p>
            if company_page_results and p_elements:
                person.summary = p_elements[0].text.strip()
                self.add_job(person, company) # position.title is not knwon

            # second <p> has their current location
            #    <p class="subline-level-2 t-12 t-black--light t-normal search-result__truncate"> Greater Denver Area </p>
            person.location = p_elements[1].text.strip()

            # The third <p> >could tell their role at the company if its text begins with "Past:" e.g. "Past: Software Engineer / Consultant at Xetex Inc."
            if not company_page_results and len(p_elements) > 2:
                title_co = p_elements[2].text.strip()
                if title_co.startswith('Past:'):  # we know this job was at company, otherwise job was at another (indeterminable) company
                    self.add_job(person, company, title_co.strip('Past: ').strip('Current: '))

            company.add_employee(person)


    def add_job(self, employee, company, position_title=None):
        '''creates a job from company and title_co and updates employee.job_history, creating it if necessary'''

        title = None
        if position_title:
            # position_title is something like "Past: Vice President, Client Services at SLKS, Inc"
            # We already know the company and we just want the title
            # separating title and company by ' at ' works pretty well
            title = ' '.join(position_title.split(' at ')[0:-1]) if ' at ' in position_title else position_title


        jh = JobHistory.from_single_position_title(company, title)
        if employee.job_history and employee.job_history.jobs:
            # Only add jh in the rare (impossible?) event that the employee's job history does not already include job with the company
            if not any([ job.company.is_same(company) for job in employee.job_history ]):
                employee.job_history.add_job(jh.jobs[0])
        else:
            employee.job_history = jh


