import re
import sys

# TODO use concurrent.futures
import concurrent.futures
# with concurrent.futures.ThreadPoolExecutor() as executor:
#     futures = { executor.submit(run_scraper, scraper_class, urls_to_scrape, linkedin_credentials, headless_option): scraper for scraper in scrapers }
#     for f in concurrent.futures.as_completed(futures):
#         print(f"{f.result()}", end='', flush=True)
from linkedin_company_scraper import LinkedinCompanyScraper
from linkedin_person_scraper import LinkedinPersonScraper


def is_valid_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def chunks(lst, n):
    if n == 0:
        return [lst]
    """Yield successive n-sized chunks from lst."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]

MAX_THREADS = 4
def run_parallel_scrapers(scraper_class, urls_to_scrape, linkedin_credentials, headless_option):
    chunked_urls = chunks(urls_to_scrape, len(urls_to_scrape) // MAX_THREADS)
    scrapers = [scraper_class(i + 1, chunk_of_urls, linkedin_credentials, headless_option) for i, chunk_of_urls in enumerate(chunked_urls)]
    print(f"Starting {len(scrapers)} parallel scrapers.")
    for scraper in scrapers: scraper.start()
    scraping_results = []
    for scraper in scrapers:
        scraper.join()
        scraping_results.extend(scraper.results)
    return scraping_results

def run_single_scraper(scraper_class, urls_to_scrape, linkedin_credentials, headless_option):
    scraper = scraper_class(1, urls_to_scrape, linkedin_credentials, headless_option)
    scraper.start()
    scraper.join()
    return scraper.results

def scrape(scraper_class, company_urls_to_scrape, linkedin_credentials, headless_option):
    args = [scraper_class, company_urls_to_scrape, linkedin_credentials, headless_option]
    # when running headless we can create multiple threads to run in parallel
    scraping_results = run_parallel_scrapers(*args) if headless_option else run_single_scraper(*args)
    return scraping_results

####################################################################################################################################


if len(sys.argv) < 3:
    print(f"usage: {sys.argv[0]} username password [--headless]")
    exit(-1)
linkedin_credentials = (sys.argv[1], sys.argv[2])
headless_option = len(sys.argv) > 3 and sys.argv[3] == '--headless'

# TODO -u username -p password -l linkedin_url_to_scrape (or -f urls_to_scrape_file) -h (== --headless)

#################################
# DEBUG company scraper
# company_results = scrape(LinkedinCompanyScraper, ['https://www.linkedin.com/company/power-pro-leasing/'], linkedin_credentials, False)
# # company_results = scrape(LinkedinCompanyScraper, ['https://www.linkedin.com/school/colorado-state-university/'], linkedin_credentials, False)
# for scraping_result in company_results:
#     if scraping_result.error:
#         print(f"{scraping_result.error} scraping {scraping_result.url}")
#     else:
#         company = scraping_result.data
#         print(company.full_details())
#
# exit(0)
#################################


urls_filename = 'urls_to_scrape.txt'
#################################
# DEBUG
urls_provided = [
    'https://www.linkedin.com/in/jennifergunther/',
    'https://www.linkedin.com/in/jerrysandoval/',
    'https://www.linkedin.com/in/smallbusinessadvocate/'
]
#################################
urls_provided = [entry.strip() for entry in open(urls_filename, 'r')]
urls_provided = [f"{e}/" if not e.endswith('/') else e for e in urls_provided]

urls_to_scrape = [u for u in urls_provided if is_valid_url(u)]
if not urls_to_scrape: raise ValueError(f"No valid URLs found in {urls_filename}")


employee_results = scrape(LinkedinPersonScraper, urls_to_scrape, linkedin_credentials, headless_option)

for scraping_result in employee_results:
    if scraping_result.error:
        print(f"{scraping_result.error} scraping {scraping_result.url}")
    else:
        employee = scraping_result.data
        try:
            company_urls_to_scrape = [ job.company.linkedin_url for job in employee.job_history ]
            print(f"scraping {len(company_urls_to_scrape)} companies for {employee.name}")
            company_results = scrape(LinkedinCompanyScraper, company_urls_to_scrape, linkedin_credentials, headless_option)

            for scraping_result in company_results:
                if scraping_result.error:
                    print(f"{scraping_result.error} scraping {scraping_result.url}")  # TODO put URL
                else:
                    company = scraping_result.data
                    for job in employee.job_history: # merge company data
                        if job.company.linkedin_url == company.linkedin_url: job.company.merge(company)


        except Exception as e:
            print(f"scraping companies raised {e}")

        print(employee)
        for job in employee.job_history: print(job.company.full_details())

print(f"Successfully scraped {len(employee_results)} of {len(urls_provided)} URLs")
