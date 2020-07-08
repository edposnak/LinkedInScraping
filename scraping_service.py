import argparse
import atexit
import time
import traceback
from models import Scrape, Person, Company

from linkedin_company_scraper import LinkedinCompanyScraper
from linkedin_person_scraper import LinkedinPersonScraper

DEFAULT_LINKEDIN_USER, DEFAULT_LINKEDIN_PASSWORD = 'ed.posnak@gmail.com', 'scrapers1'


stopped = False

def scrape_gen(db_polling_sleep_seconds=10):
    '''Generates URLs by polling the database for scrapes where last_scraped is NULL'''
    while not stopped:
        scrape = Scrape.next_unscraped()
        if scrape:
            yield scrape
        else:
            time.sleep(db_polling_sleep_seconds)

def scrape_forever(scrapers, p_args):
    global stopped
    count = 0
    for scrape in scrape_gen(db_polling_sleep_seconds=5):
        try:
            count += 1
            print(f"\n\nBEGIN scraping {scrape.scrapable_type} URL {scrape.url} scrape.id={scrape.id} flags={scrape.flags}")
            result = scrapers[scrape.scrapable_type].run(scrape.url)

            if result.error:
                scrape.status = 1 if result.data else 2 # 1 for partial scrape, 2 for complete failure
                has_data_str = '(but result has data)' if result.data else ''
                print(f"FAILED scrape {has_data_str} result.error={result.error}")
                scrape.message = str(result.error)


            print(f"UPDATING last_scraped for scrape.id={scrape.id} status={scrape.status} message={scrape.message} url={scrape.url}")
            s_id = scrape.update_status_in_db()
            print(f"UPDATED scrape for s_id={s_id} url={scrape.url}")

            person_or_company = result.data
            if person_or_company:
                print(f"DONE scraping #{person_or_company.name}\n\n")
                if not p_args.nosave:
                    print(f"BEGIN saving {scrape.scrapable_type} {person_or_company.name}")
                    person_or_company.save_to_db()

                if scrape.do_companies():
                    for company_id in person_or_company.all_company_ids():
                        print(f"adding scrape (if necessary) for company company_id={company_id}")
                        Scrape.find_or_create_in_db('Company', company_id) # no flags for companies yet

                if scrape.do_managers():
                    for manager_id in person_or_company.all_manager_ids():
                        print(f"adding scrape (if necessary) for manager person_id={manager_id}")
                        Scrape.find_or_create_in_db('Person', manager_id) # no flags for managers

        except Exception as e:
            print(f"Exiting because service raised {e}")
            traceback.print_exc()
            stopped = True
            # break

        # finally:

#######################################################################################################################

def parse_program_args():
    parser = argparse.ArgumentParser(description='Service to scrape LinkedIn profiles and company pages')
    parser.add_argument('-u', '--user', default=DEFAULT_LINKEDIN_USER, help='LinkedIn username')
    parser.add_argument('-p', '--password', default=DEFAULT_LINKEDIN_PASSWORD, help='LinkedIn password')
    parser.add_argument('-g', '--headless', action='store_true', help='use headless browser to scrape')
    parser.add_argument('-n', '--nosave', action='store_true', help='do not save records to the db')

    return parser.parse_args()

def main():
    p_args = parse_program_args()
    if p_args.nosave: print(f"**** -n NOT SAVING RESULTS TO DB ****\n")

    print(f"Firing up a PersonScraper and a CompanyScraper ...")
    scrapers = {
        'Person': LinkedinPersonScraper(p_args),
        'Company': LinkedinCompanyScraper(p_args)
    }
    def shutdown():
        # Shut down scrapers
        for scrapable_type, scraper in scrapers.items():
            print(f"Shutting down {scrapable_type} scraper")
            scraper.shutdown()
    atexit.register(shutdown)

    scrape_forever(scrapers, p_args)


if __name__ == "__main__":
    main()

