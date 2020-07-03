import sys

import argparse
import traceback

from linkedin_company_scraper import LinkedinCompanyScraper
from linkedin_person_scraper import LinkedinPersonScraper

DEFAULT_LINKEDIN_USER, DEFAULT_LINKEDIN_PASSWORD = 'ed.posnak@gmail.com', 'scrapers1'

def scrape_one(scraper_class, url_to_scrape, p_args):
    scraper = scraper_class(1, [url_to_scrape], (p_args.user, p_args.password), p_args.headless)
    scraper.start()
    scraper.join()

    first_result = scraper.results[0]
    if first_result.error:
        print(f"ERROR scraping {url_to_scrape}: {first_result.error}")
    return first_result.data

def scrape_many(scraper_class, urls_to_scrape, p_args):
    scraper = scraper_class(1, urls_to_scrape, (p_args.user, p_args.password), p_args.headless)
    scraper.start()
    scraper.join()

    for r in scraper.results:
        if r.error: print(f"ERROR scraping {r.url}: {r.error}")


    return [ r.data for r in scraper.results if not r.error ] # return only the valid results


def main():
    parser = argparse.ArgumentParser(description='Scrape LinkedIn profiles and company pages')
    parser.add_argument('url_to_scrape', help='the LinkedIn URL to scrape')
    parser.add_argument('-u', '--user', default=DEFAULT_LINKEDIN_USER, help='LinkedIn username')
    parser.add_argument('-p', '--password', default=DEFAULT_LINKEDIN_PASSWORD, help='LinkedIn password')
    parser.add_argument('-c', '--companies', action='store_true', help='also scrape companies found in job history')
    parser.add_argument('-g', '--headless', action='store_true', help='use headless browser to scrape')
    parser.add_argument('-n', '--nosave', action='store_true', help='do not save records to the db')

    p_args = parser.parse_args()

    if p_args.nosave: print(f"****\n-n NOT SAVING RESULTS TO DB\n****\n")

    # cheap detection of whether it's a company page url or a profile url
    if any([s in p_args.url_to_scrape for s in 'company school results'.split()]):
        company = scrape_one(LinkedinCompanyScraper, p_args.url_to_scrape, p_args)
        if not p_args.nosave: company.save_to_db()
    else:
        person = scrape_one(LinkedinPersonScraper, p_args.url_to_scrape, p_args)
        if person:
            print(person)
            if not p_args.nosave: person.save_to_db()

            if p_args.companies: # also scrap the companies from the person's job history
                try:
                    urls_to_scrape = { job.company.linkedin_url for job in person.job_history } # dedup
                    if urls_to_scrape:
                        print(f"scraping {len(urls_to_scrape)} companies from {person.name}'s job history")
                        companies = scrape_many(LinkedinCompanyScraper, urls_to_scrape, p_args)
                        print(f"successfully scraped {len(companies)}/{len(urls_to_scrape)} companies")
                        for company in companies:
                            try:
                                print(company)
                                if not p_args.nosave: company.save_to_db()
                            except Exception as e:
                                print(f"saving companies raised {e}")
                                with open(f"models_errors.txt", "a") as errlog:
                                    traceback.print_exc(file=errlog)

                except Exception as e:
                    print(f"scraping companies raised {e}")




if __name__ == "__main__":
    main()

