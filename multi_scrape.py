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

# TODO -u username -p password  -h (== --headless) -l linkedin_url_to_scrape (or -f urls_to_scrape_file)

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
urls_to_scrape = [entry.strip() for entry in open(urls_filename, 'r')]

#################################
# DEBUG
urls_to_scrape = [
    # 'https://www.linkedin.com/in/jcartwright/',
    'https://www.linkedin.com/in/jennifergunther/',
    'https://www.linkedin.com/in/andrewcorrado/',
    'https://www.linkedin.com/in/jerrysandoval/',
    'https://www.linkedin.com/in/keith-hulen-a874175/',
    'https://www.linkedin.com/in/edposnak/',
    'https://www.linkedin.com/in/smallbusinessadvocate/',
    # 'https://www.linkedin.com/in/luther-knox-96178a12/',
]

urls_to_scrape = [
    # 'https://www.linkedin.com/in/jcartwright',
    # 'https://www.linkedin.com/in/madhuavayamukari/',
    'https://www.linkedin.com/in/chrisskhabbaz/',
    'https://www.linkedin.com/in/sravanaswati/',
    'https://www.linkedin.com/in/christian-esqueda-7a024923/',
    'https://www.linkedin.com/in/douglas-baker1971/',
    'https://www.linkedin.com/in/marlicreeach/',
    'https://www.linkedin.com/in/ryan5732/',
    'https://www.linkedin.com/in/davidwolitzer/',
    'https://www.linkedin.com/in/jaime-bellmyer-816559b/',
    'https://www.linkedin.com/in/rick-puglisi-93a2816/',
    'https://www.linkedin.com/in/jessharring/',
    'https://www.linkedin.com/in/rogersalam/',
    'https://www.linkedin.com/in/robertwdempsey/',
    'https://www.linkedin.com/in/johanntagle/',
    'https://www.linkedin.com/in/chriscoddington/',
    'https://www.linkedin.com/in/saqibkhalil/',
    'https://www.linkedin.com/in/weston-henderson-b00829a/',
    'https://www.linkedin.com/in/willbridges/',
    'https://www.linkedin.com/in/troysabin/',
    'https://www.linkedin.com/in/mdeering/',
    'https://www.linkedin.com/in/jgully/',
    'https://www.linkedin.com/in/breckmorrison/',
    'https://www.linkedin.com/in/greggpollack/',
    'https://www.linkedin.com/in/monchaiolo/',
    'https://www.linkedin.com/in/jverden/',
    'https://www.linkedin.com/in/johnlivermore/',
    'https://www.linkedin.com/in/ianjames22/',
    'https://www.linkedin.com/in/adam-selig-7194a11/',
    'https://www.linkedin.com/in/arron-mabrey-4818b775/',
    'https://www.linkedin.com/in/pkaiden/',
]

urls_to_scrape = [
    # 'https://www.linkedin.com/in/jennifergunther/',
    'https://www.linkedin.com/in/robertspryn/',
    'https://www.linkedin.com/in/studiodelve/',
    'https://www.linkedin.com/in/bonnie-palmatory/',
    'https://www.linkedin.com/in/annelmurphy/',
    'https://www.linkedin.com/in/mikelewis/',
    'https://www.linkedin.com/in/ryanspohn/',

    # 'https://www.linkedin.com/in/jerrysandoval/',
    'https://www.linkedin.com/in/mlunin/',
    'https://www.linkedin.com/in/suneetbhatt/',
    'https://www.linkedin.com/in/keith-hulen-a874175/',
    'https://www.linkedin.com/in/constantine-kokolis-4003682/',
    'https://www.linkedin.com/in/bwalkgartner/',
    'https://www.linkedin.com/in/kyledchristian/',
    'https://www.linkedin.com/in/ericwilsonew/',
    'https://www.linkedin.com/in/michelleolive/',
    'https://www.linkedin.com/in/justinsmittysmith/',
    'https://www.linkedin.com/in/marty-vanderploeg-1020037/',
    'https://www.linkedin.com/in/leskojennifer/',
    'https://www.linkedin.com/in/matthewgwilson/',
    'https://www.linkedin.com/in/tomherriage/',
    'https://www.linkedin.com/in/philevitt/',
    'https://www.linkedin.com/in/smallbusinessadvocate/',
]

urls_to_scrape = [
    # 'https://www.linkedin.com/in/edposnak/',
    'https://www.linkedin.com/in/neilturner/',
    'https://www.linkedin.com/in/davidbleznak/',
    'https://www.linkedin.com/in/susan-cheng-8935754/',


    'https://www.linkedin.com/in/ryan-marston-0a587739/',
    'https://www.linkedin.com/in/ryanvolk/',
    'https://www.linkedin.com/in/amandahansen/',
    'https://www.linkedin.com/in/jennifer-oldenborg-phr-shrm-cp-a3225a58/',
    'https://www.linkedin.com/in/kirstan-sandoval-94872412/',
    'https://www.linkedin.com/in/freddymarchant93/',
    'https://www.linkedin.com/in/phil-navratil-02a6998/',
    'https://www.linkedin.com/in/markdiffenderfer/',
    'https://www.linkedin.com/in/gaylehenderson/',
    'https://www.linkedin.com/in/vernongarding/',
    'https://www.linkedin.com/in/teresagartoncharles/',
    'https://www.linkedin.com/in/mark-fosmoen-a86a4a5/',
    'https://www.linkedin.com/in/jasonfey/',
    'https://www.linkedin.com/in/bethsmithalistinterviews/',
    'https://www.linkedin.com/in/jonmwakser/',
    'https://www.linkedin.com/in/steveestle/',
    'https://www.linkedin.com/in/jerrycomer/',
    'https://www.linkedin.com/in/jmgoldsberry/',
    'https://www.linkedin.com/in/jcjackjames/',
    'https://www.linkedin.com/in/zack-hughes-31a700/',
    'https://www.linkedin.com/in/leesyndergaard/',
    'https://www.linkedin.com/in/aslinn/',
]
#################################


# Scrape all the people with a single scraper
urls_to_scrape = [ u for u in urls_to_scrape if is_valid_url(u) ]

person_results = scrape(LinkedinPersonScraper, urls_to_scrape, linkedin_credentials, headless_option)

company_urls_to_scrape = []
for scraping_result in person_results:
    if scraping_result.error:
        print(f"{scraping_result.error} scraping {scraping_result.url}")
    else:
        person = scraping_result.data
        print(person)
        for job in person.job_history: print(job.company.full_details())
        person_id = person.save_to_db()
        print(f"saved {person.name} id={person_id}")

        company_urls_to_scrape += [job.company.linkedin_url for job in person.job_history]

print(f"EARLY EXIT NO COMPANY SCRAPING")
exit(0)

if company_urls_to_scrape:
    try:
        # Scrape all the companies with a single scraper
        print(f"scraping {len(company_urls_to_scrape)} companies")
        company_results = scrape(LinkedinCompanyScraper, company_urls_to_scrape, linkedin_credentials, headless_option)

        for scraping_result in company_results:
            if scraping_result.error:
                print(f"{scraping_result.error} scraping {scraping_result.url}")  # TODO put URL
            else:
                company = scraping_result.data
                print(company.full_details())
                company_id = company.save_to_db()
                print(f"saved {company.name} id={company_id}")
    except Exception as e:
        print(f"scraping companies raised {e}")


print(f"Successfully scraped {len(person_results)} of {len(urls_to_scrape)} URLs")
