import sys

from profile_scraper import ProfileScraper
from utils import boolean_to_string_xls, date_to_string_xls, message_to_user, chunks

import concurrent.futures

if len(sys.argv) < 3:
    print(f"usage: {sys.argv[0]} linkedin_username linkedin_password [HEADLESS]")
    exit(-1)
linkedin_credentials = (sys.argv[1], sys.argv[2])
headless_option = len(sys.argv) > 3 and sys.argv[3] == '--headless'

urls_filename = 'urls_to_scrape.txt'
urls_to_scrape = [entry.strip() for entry in open(urls_filename, 'r')]
#################################
# DEBUG
urls_to_scrape = [
    'https://www.linkedin.com/in/jennifergunther/',
    # 'https://www.linkedin.com/in/jerrysandoval/',
    # 'https://www.linkedin.com/in/smallbusinessadvocate/'
]
#################################
urls_to_scrape = [f"{e}/" if not e.endswith('/') else e for e in urls_to_scrape]
if not urls_to_scrape: raise ValueError(f"No entries found in {urls_filename}")

# when running headless we can create multiple threads to run in parallel and divide the entries into chunks
MAX_THREADS = 4
if headless_option:
    chunked_urls = chunks(urls_to_scrape, len(urls_to_scrape) // MAX_THREADS)
    scrapers = [ProfileScraper(i + 1, chunk_of_urls, linkedin_credentials, headless_option) for i, chunk_of_urls in enumerate(chunked_urls)]
    print(f"Starting {len(scrapers)} parallel scrapers.")
    # with concurrent.futures.ThreadPoolExecutor() as executor:
    #     futures = { executor.submit(self.scrape_some): scraper for scraper in scrapers }
    #     for f in concurrent.futures.as_completed(futures):
    #         print(f"{f.result()}", end='', flush=True)

    for scraper in scrapers: scraper.start()
    scraping_results = []
    for scraper in scrapers:
        scraper.join()
        scraping_results.extend(scraper.results)
else:
    scraper = ProfileScraper(1, urls_to_scrape, linkedin_credentials, headless_option)
    scraper.start()
    scraper.join()
    scraping_results = scraper.results

for scraping_result in scraping_results:
    if scraping_result.is_error():
        print(f"Failed to scrape {scraping_result.message}") # TODO put URL
    else:
        print(scraping_result.employee)
        for job in scraping_result.employee.job_history:
            print(job.company.full_details())

message_to_user(f"Successfully scraped {len(scraping_results)} of {len(urls_to_scrape)} URLs", speak=True)
