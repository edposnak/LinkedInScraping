import argparse
import traceback

from linkedin_company_scraper import LinkedinCompanyScraper
from linkedin_person_scraper import LinkedinPersonScraper

DEFAULT_LINKEDIN_USER, DEFAULT_LINKEDIN_PASSWORD = 'ed.posnak@gmail.com', 'scrapers1'

def scrape_one(url_to_scrape, p_args, scraper=None, scraper_class=None):
    if not scraper: scraper = scraper_class(p_args)
    result = scraper.run(url_to_scrape)
    if result.error: print(result.error)
    person_or_company = result.data
    if person_or_company:
        print(person_or_company)
        if not p_args.nosave: person_or_company.save_to_db()
    return person_or_company

def scrape_many(urls_to_scrape, p_args, scraper=None, scraper_class=None):
    if not scraper: scraper = scraper_class(p_args)
    things = [ scrape_one(url, p_args, scraper=scraper) for url in urls_to_scrape ]
    return [ t for t in things if t ]


def parse_program_args():
    parser = argparse.ArgumentParser(description='Scrape LinkedIn profiles and company pages')
    parser.add_argument('url_to_scrape', help='the LinkedIn URL to scrape')
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

    # cheap detection of whether it's a company page url or a profile url
    if any([s in p_args.url_to_scrape for s in 'company school results'.split()]):
        company = scrape_one(p_args.url_to_scrape, p_args, scraper_class=LinkedinCompanyScraper)
    else:
        person = scrape_one(p_args.url_to_scrape, p_args, scraper_class=LinkedinPersonScraper)

        if person and p_args.companies: # also scrap the companies from the person's job history
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

