import argparse
import atexit
import time
import traceback
from models import Scrape, Person, Company

from linkedin_company_scraper import LinkedinCompanyScraper
from linkedin_person_scraper import LinkedinPersonScraper

DEFAULT_LINKEDIN_USER, DEFAULT_LINKEDIN_PASSWORD = 'ed.posnak@gmail.com', 'scrapers1'

def scrape_one(scraper_class, url_to_scrape, p_args):
    scraped_things = scrape_many(scraper_class, [url_to_scrape], p_args)
    if scraped_things: return scraped_things[0]

def scrape_many(scraper_class, urls_to_scrape, p_args):
    linkedin_credentials = (p_args.user, p_args.password)
    scraper = scraper_class(1, linkedin_credentials, p_args.headless)
    results = scraper.run(urls_to_scrape)

    for r in scraper.results:
        if r.error: print(f"ERROR scraping {r.url}: {r.error}")

    return [ r.data for r in scraper.results if not r.error ] # return only the valid results


stopped = False

def scrape_gen(db_polling_sleep_seconds=10):
    '''Generates URLs by polling the database for scrapes where last_scraped is NULL'''
    while not stopped:
        scrape = Scrape.next_unscraped()
        if scrape:
            print(f"   scrape_gen: Got an unscraped {scrape.scrapable_type} URL! url={scrape.url} (scrape.id={scrape.id})")
            yield scrape
        else:
            time.sleep(db_polling_sleep_seconds)

def scrape_forever(scrapers, p_args):
    global stopped
    count = 0
    for scrape in scrape_gen():
        try:
            count += 1
            print(f"\n\nBEGIN scraping {scrape.scrapable_type} URL {scrape.url} scrape.id={scrape.id}")
            result = scrapers[scrape.scrapable_type].run(scrape.url)

            if result.error:
                scrape.status = 1 if result.data else 2 # 1 for partial scrape, 2 for complete failure
                print(f"failed scrape result.error={result.error}")
                scrape.message = str(result.error)
                if result.data: print(f"but result has data")
            else:
                person_or_company = result.data

            print(f"updating last_scraped for scrape.id={scrape.id} status={scrape.status} message={scrape.message} url={scrape.url}")
            s_id = scrape.save_to_db()
            print(f"updated scrape for s_id={s_id} url={scrape.url}")

            if person_or_company:
                print(f"DONE scraping #{person_or_company.name}\n\n")
                if not p_args.nosave:
                    print(f"saving {scrape.scrapable_type} {person_or_company.name}")
                    person_or_company.save_to_db()

                if p_args.companies and scrape.scrapable_type == 'Person':
                    for job in person_or_company.job_history:
                        if job.company_id:
                            print(f"adding scrape (if necessary) for {job.company.name}")
                            Scrape.find_or_create_in_db('Company', job.company_id) # won't create duplicate records
                        else:
                            print(f"WTF no company_id for job {job}")

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
    parser.add_argument('-c', '--companies', action='store_true', help='also scrape companies found in job history')
    parser.add_argument('-g', '--headless', action='store_true', help='use headless browser to scrape')
    parser.add_argument('-n', '--nosave', action='store_true', help='do not save records to the db')

    return parser.parse_args()

def main():
    p_args = parse_program_args()
    if p_args.nosave: print(f"**** -n NOT SAVING RESULTS TO DB ****\n")
    if p_args.companies: print(f"**** -c SCRAPING ALL NEW COMPANIES ****\n")

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

