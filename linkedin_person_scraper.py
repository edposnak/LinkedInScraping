import time


from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains


from linkedin_scraper import LinkedinScraper, ScrapingResult
from models import Person, ContactInfo, Skills, Company, Position, Job, JobHistory, Recommendations, Recommendation


class JobSummaryNotFoundException(Exception): pass

class LinkedinPersonScraper(LinkedinScraper):
    def __init__(self, *args):
        super(LinkedinPersonScraper, self).__init__(*args)

    def scrape(self, linkedin_profile_url):
        person = Person(None, linkedin_profile_url)

        try:
            print(f"scraping name, location, and summary {person.linkedin_url}")
            self.scrape_top_card(person)  # gets name, summary, location

            print(f"scraping contact_info for {person.name}")
            person.contact_info = self.scrape_contact_info()
            print(f"{person.name} {person.contact_info}")

            self.scroll_to_bottom_to_load_all_content()
            print(f"scraping skills for {person.name}")
            person.skills = self.scrape_skills()
            print(f"{person.name} {person.skills}")

            print(f"scraping job_history for {person.name}")
            self.click_on_show_more_jobs()
            person.job_history = self.scrape_job_history()
            print(f"{person.name} {person.job_history}")

            print(f"scraping recommendations for {person.name}")
            person.recommendations_given, person.recommendations_received = self.scrape_recommendations()
            print(f"{person.name} recommendations_given={person.recommendations_given}")
            print(f"{person.name} recommendations_received={person.recommendations_received}")

            return ScrapingResult(person)

        except Exception as e:
            if person.name: # partial result
                return ScrapingResult(person, error=e)
            else:
                return ScrapingResult(None, error=e)

    def scrape_top_card(self, person):
        # <section id="ember54" class="pv-top-card artdeco-card ember-view"><!---->
        top_card_section = self.browser.find_element_by_class_name('pv-top-card')
        # <ul class="pv-top-card--list inline-flex align-items-center">
        top_card_list_elements = top_card_section.find_elements_by_class_name('pv-top-card--list')
        #     <li class="inline t-24 t-black t-normal break-words"> Luther Knox </li>
        person.name = top_card_list_elements[0].find_element_by_tag_name('li').text.strip()
        # <h2 class="mt1 t-18 t-black t-normal break-words"> Creative Director at LiveIntent, Inc. </h2>
        person.summary = top_card_section.find_element_by_tag_name('h2').text.strip()
        # <li class="t-16 t-black t-normal inline-block"> New York, New York </li>
        person.location = top_card_list_elements[1].find_element_by_tag_name('li').text.strip()

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
        try:
            # Click on "Show More" once (should bring up all skills)
            # self.browser.execute_script("document.getElementsByClassName('pv-skills-section__additional-skills')[0].click()")

            more_skills_button = self.browser.find_element_by_class_name('pv-skills-section__additional-skills')
            ActionChains(self.browser).move_to_element(more_skills_button).click(more_skills_button).perform()

            time.sleep(wait_for_skills_load_seconds)

            skills_list_element = self.browser.find_element_by_class_name('pv-skill-category-list__skills_list')
            skills_list = [ e.text.strip() for e in skills_list_element.find_elements_by_class_name('pv-skill-category-entity__name-text') ]

            return Skills(skills_list)
        except NoSuchElementException as e:
            return Skills([]) # some people ain't got no skills

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
                job.company.linkedin_url = a_tag.get_attribute('href')

            except NoSuchElementException as e:
                print(f"WARNING: No company linkedin_url a_tag was found under {job_element.tag_name} class={job_element.get_attribute('class')} for job {n+1}")

            try:
                self.scrape_single_position_job(job, job_element)
            except JobSummaryNotFoundException as e:
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
        summary_element = None
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
        recommendations_given, recommendations_received = Recommendations(), Recommendations()
        try:
            # Find the recommendations section if it exists
            # <section class="pv-recommendations-section">
            recommendations_element = self.browser.find_element_by_class_name('pv-recommendations-section')

            # First button is the Received tab, second button is the Given tab
            received_tab_button, given_tab_button = recommendations_element.find_elements_by_css_selector("button.artdeco-tab")

            print(f"RECOMMENDATIONS TO SCRAPE: {given_tab_button.text.strip()} {received_tab_button.text.strip()}")

            # if the Received tab is visible (i.e. aria-selected="selected") scrape it, then click the given_button to switch tabs and scrape Given
            if received_tab_button.get_attribute('aria-selected') == 'true':
                recommendations_received = self.scrape_reco_list(received_tab_button)

                # Now switch tabs to the Given recommendations
                ActionChains(self.browser).move_to_element(given_tab_button).click(given_tab_button).perform()
                time.sleep(wait_for_recommendations_load_seconds)
                recommendations_given = self.scrape_reco_list(given_tab_button)
            else: # if the Received tab is hidden (i.e. aria-selected="false") assume none received, and just get given
                recommendations_given = self.scrape_reco_list(given_tab_button)

                # Now switch tabs to the Received recommendations
                ActionChains(self.browser).move_to_element(received_tab_button).click(received_tab_button).perform()
                time.sleep(wait_for_recommendations_load_seconds)
                recommendations_received = self.scrape_reco_list(received_tab_button)


            # mark recommendations as reciprocal if linkedin_url matches
            for rg in recommendations_given:
                for rr in recommendations_received:
                    if rg.linkedin_url == rr.linkedin_url:
                        rg.reciprocal = rr.reciprocal = True

        except Exception as e:
            print(f"scrape_recommendations() raised {e}")

        return recommendations_given, recommendations_received


    def scrape_reco_list(self, tab_button, wait_for_recommendations_load_seconds=1):
        recommendations = Recommendations()
        # recommendations_element = self.browser.find_element_by_class_name('pv-recommendations-section')

        # button text tells how many recommendations there are, e.g. 'Received (0)':
        num_recommendations = tab_button.text.strip()
        print(f"   searching for {num_recommendations} recommendations")
        if num_recommendations.endswith('(0)'): return recommendations

        id_to_scrape = tab_button.get_attribute('aria-controls')
        controlled_div_element = self.browser.find_element_by_id(id_to_scrape)

        # Click Show more if the button exists
        # If there are more than 2 recommendations there will be a third button "Show more"
        # <button class="pv-profile-section__see-more-inline pv-profile-section__text-truncate-toggle link link-without-hover-state"
        # aria-controls="recommendation-list" aria-expanded="false" type="button">Show more
        showed_more = False # used to determine whether to click "show less" button
        while True:
            try:
                more_inline_button = controlled_div_element.find_element_by_class_name('pv-profile-section__see-more-inline')
                ActionChains(self.browser).move_to_element(more_inline_button).click(more_inline_button).perform()
                showed_more = True
                time.sleep(wait_for_recommendations_load_seconds)
            except NoSuchElementException as e:
                break # keep clicking until the button is not found


        # recommendations are a series of <li class="pv-recommendation-entity"> elements found underneath the div controlled by the button
        print(f"   found {len(controlled_div_element.find_elements_by_class_name('pv-recommendation-entity'))} recommendations")
        for rec_element in controlled_div_element.find_elements_by_class_name('pv-recommendation-entity'):
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
            #                  OR 'reported directly to Jennfier'
            rec_date_relationship = p_tags[1].text.strip()
            parts = rec_date_relationship.split(',')
            recommendation.date = ','.join(parts[0:2]).strip()
            recommendation.relationship = ''.join(parts[2:]).strip()

            if recommendation.relationship and 'managed' in recommendation.relationship: recommendation.managed = True
            if recommendation.relationship and 'reported directly' in recommendation.relationship: recommendation.reported_to = True

            # only add recommendations with a name (hidden recommendations have blank name, etc.)
            # TODO this doesn't happen anymore because we search the div controlled by the button
            if recommendation.name:  # received recommendation
                print(f"   ADDING recommendation {recommendation}")
                recommendations.add(recommendation)
            else:  # given recommendation
                print(f"   SKIPPING recommendation with blank name")

        # if showed_more:
        #     print(f"   CLICKING show less button")
        #     controlled_div_element.find_element_by_class_name('pv-profile-section__see-less-inline').click()
        #     time.sleep(wait_for_recommendations_load_seconds)

        return recommendations

