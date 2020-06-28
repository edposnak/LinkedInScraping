import time


from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement

from linkedin_scraper import LinkedinScraper, ScrapingResult
from models import Employee, ContactInfo, Skills, Company, Position, Job, JobHistory, Recommendations, Recommendation


class JobSummaryNotFoundException(Exception): pass

class LinkedinPersonScraper(LinkedinScraper):
    def __init__(self, *args):
        super(LinkedinPersonScraper, self).__init__(*args)

    def scrape(self, linkedin_profile_url):
        profile_name = self.browser.find_element_by_class_name('pv-top-card--list').find_element_by_tag_name('li').text.strip()
        employee = Employee(profile_name, linkedin_profile_url)

        print(f"contact info for {employee.name}")
        employee.contact_info = self.scrape_contact_info()
        print(f"{employee.name} {employee.contact_info}")

        self.scroll_to_bottom_to_load_all_content()
        print(f"scraping skills for {employee.name}")
        employee.skills = self.scrape_skills()
        print(f"{employee.name} {employee.skills}")

        print(f"scraping job_history for {employee.name}")
        self.click_on_show_more_jobs()
        employee.job_history = self.scrape_job_history()
        print(f"{employee.name} {employee.job_history}")

        print(f"scraping recommendations for {employee.name}")
        employee.recommendations = self.scrape_recommendations()
        print(f"{employee.name} recommendations={employee.recommendations}")

        return ScrapingResult(employee, url=linkedin_profile_url)

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
                print(f"WARNING: No company linkedin_url a_tag was found under {job_element.tag_name} class={job_element.get_attribute('class')} for job {n+1}")

            try:
                self.scrape_single_position_job(job, job_element)
            except JobSummaryNotFoundException as e:
                # print(f"scrape_single_position_job({job_element.tag_name} class={job_element.get_attribute('class')}) raised {e} for job {n+1}")
                try:
                    self.scrape_multi_position_job(job, job_element)
                except Exception as e:
                    # print(f"scrape_multi_position_job({job_element.tag_name} class={job_element.get_attribute('class')}) raised {e} for job {n+1}")
                    print(f"Could not scrape job {n+1} as either single-position or multi-position job")
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

        position = Position()
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
            pass # location is often not present

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
            if received_tab_element.text.strip() == 'Received (0)': return recommendations
            # if there are no recommendations you might see this
            # <p class="description t-16 t-black--light t-normal mt5"> Jerry hasn’t received any recommendations yet. </p>

            # if the Received tab is hidden (i.e. tabindex="-1") click it, which will set tabindex="0" and load the received recommendations
            if received_tab_element.get_attribute('tabindex') == '-1':
                received_tab_element.click()
                time.sleep(wait_for_recommendations_load_seconds)

            # Click Show more if exists
            # If there are more than 2 recommendations there will be a third button "Show more"
            # <button class="pv-profile-section__see-more-inline pv-profile-section__text-truncate-toggle link link-without-hover-state"
            # aria-controls="recommendation-list" aria-expanded="false" type="button">Show more
            try:
                more_button = recommendations_element.find_element_by_class_name('pv-profile-section__see-more-inline')
                more_button.click()
                time.sleep(wait_for_recommendations_load_seconds)
            except NoSuchElementException as e:
                pass # this button is often not found

            # recommendations are a series of <li class="pv-recommendation-entity"> elements
            print(f"found {len(recommendations_element.find_elements_by_class_name('pv-recommendation-entity'))} recommendations")
            for rec_element in recommendations_element.find_elements_by_class_name('pv-recommendation-entity'):
                recommendation = Recommendation()

                # <a data-control-name="recommendation_details_profile" href=linkedin_profile_url_of_recommender
                a_tag = rec_element.find_element_by_tag_name('a')
                recommendation.linkedin_url = a_tag.get_attribute('href')

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

