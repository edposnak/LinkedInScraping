from linkedin_scraper import LinkedinScraper, ScrapingResult

from selenium.common.exceptions import NoSuchElementException

from models import Employee, JobHistory, Company


class LinkedinCompanyScraper(LinkedinScraper):
    def __init__(self, *args):
        super(LinkedinCompanyScraper, self).__init__(*args)

    def scrape(self, linkedin_company_url):
        company = Company()
        company.linkedin_url = linkedin_company_url

        self.scrape_overview(company)
        self.scrape_employees(company)

        return ScrapingResult(company, url=linkedin_company_url)

    def is_company_page(self, url):
        return 'linkedin.com/company/' in url or 'linkedin.com/school/' in url

    def scrape_overview(self, company):
        if not self.is_company_page(company.linkedin_url):
            print(f"cannot scrape overview of {company.linkedin_url} because it is not a linkedin company page'")
            return

        about_page = company.linkedin_url.strip('/') + '/about/'
        try:
            self.load_page(about_page)

            # This top card has the company name, industry, and headquarters (some of which is redundant with the overview)
            top_card_element = self.browser.find_element_by_class_name('org-top-card-primary-content__content')

            # <h1 class="org-top-card-summary__title t-24 t-black truncate" title="Power Pro Leasing">
            company.name = top_card_element.find_element_by_class_name('org-top-card-summary__title').get_attribute('title').strip()

            # <div class="org-top-card-summary-info-list t-14 t-black--light">
            #     <div class="org-top-card-summary-info-list__info-item"> Real Estate </div>
            #       <div class="org-top-card-summary-info-list__info-item"> Greenwood Village, CO </div>
            #       <div class="org-top-card-summary-info-list__info-item"> 339 followers </div>
            divs = top_card_element.find_elements_by_class_name('org-top-card-summary-info-list__info-item')
            company.industry = divs[0].text.strip()
            company.headquarters = divs[1].text.strip()

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

            offset = 0 # used to deal with different overview formats # TODO use the text of the dt to decide what the dd is
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
            company.founded = dd_elements[offset+4].text.strip()
        except Exception as e:
            print(f"scrape_company scraping {about_page} raised {e}")

    def scrape_employees(self, company):
        # AVOID scraping a page like https://www.linkedin.com/search/results/all/?keywords=Self-Employed
        if 'Self-Employed' in company.linkedin_url:
            print(f"cannot scrape employees of {company.linkedin_url} because it is a search on Self-Employed'")
            return

        try:
            self.load_page(company.linkedin_url)

            # There are two types of pages that company.linkedin_url will load:
            # 1. company (home or about) page - https://www.linkedin.com/company/... or  https://www.linkedin.com/school/...
            # 2. search page - https://www.linkedin.com/search/results/all/?keywords=Recontek%20Systems%20Inc

            company_page_results = self.is_company_page(self.browser.current_url)
            if company_page_results:  # we're on a Company (home or about) page
                # If there are employees, there will be an <a> to click
                # <a data-control-name="topcard_see_all_employees" href="/search/results/people/?facetCurrentCompany=%5B%223768740%22%5D">
                see_employees_link = self.browser.find_element_by_css_selector("a[data-control-name='topcard_see_all_employees']").get_attribute('href')
                print(f"calling load_page('{see_employees_link}') ...")
                self.load_page(see_employees_link)

                # The number of search results is in <h3 class="search-results__total">254 results</h3>
                company.num_linkedin_results = int(self.browser.find_element_by_class_name('search-results__total').text.split()[0])

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
                if 'LinkedIn Member' == name:
                    print(f"BOO can't scrape out-of-network employee named LinkedIn Member")
                    continue
                linkedin_url = a_tag.get_attribute('href')
                # If that href is not a profile (e.g. # or https://www.linkedin.com/search/results/all/?keywords=SLKS%2C%20Inc) they are probably unreachable
                # TODO: make sure 'LinkedIn Member' catches all non-reachables and non-employees
                employee = Employee(name, linkedin_url)

                p_elements = result_element.find_elements_by_tag_name('p')
                # The first <p> has the employee's current title and sometimes company
                # <p class="subline-level-1 t-14 t-black t-normal search-result__truncate"> Founder at Frontside Creative </p>
                if company_page_results and p_elements:
                    title_co = p_elements[0].text.strip()
                    self.add_job(employee, company, title_co)

                # second <p> has their current location
                #    <p class="subline-level-2 t-12 t-black--light t-normal search-result__truncate"> Greater Denver Area </p>

                # The third <p> >could tell their role at the company if its text begins with "Past:" e.g. "Past: Software Engineer / Consultant at Xetex Inc."
                if not company_page_results and len(p_elements) > 2:
                    title_co = p_elements[2].text.strip()
                    if title_co.startswith('Past:'):  # we know this job was at company, otherwise job was at another (indeterminable) company
                        self.add_job(employee, company, title_co.strip('Past: ').strip('Current: '))

                company.add_employee(employee)


        except Exception as e:
            print(f"scrape_employees({company.linkedin_url}) raised {e}")

        print(f"FOUND {len(company.employees) if company.employees else 0} employees for {company.name}")


    def add_job(self, employee, company, title_co):
        '''creates a job from company and title_co and updates employee.job_history, creating it if necessary'''

        # title_co often endswith " at XXX Inc." where XXX may be similar to, but not match exactly the company name e.g.
        # "Co-founder & CEO - Omniex", "Co-Founder & CTO at Omniex, Inc.", "Head of Operations at Omniex Holdings, Inc."
        # In any case, we already know the company and we just want the title
        # separating title and company by ' at ' works pretty well, though some use ' @ '
        title = ' '.join(title_co.split(' at ')[0:-1]) if ' at ' in title_co else title_co

        jh = JobHistory.from_single_position_title(company, title)
        if employee.job_history and employee.job_history.jobs:
            employee.job_history.add_job(jh.jobs[0])
        else:
            employee.job_history = jh


