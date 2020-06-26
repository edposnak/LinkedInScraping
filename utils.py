import re
import pyttsx3
from datetime import datetime


class HumanCheckException(Exception): pass


class Location:
    def __init__(self, city='N/A', country='N/A', location='N/A'):
        self.full_string = location
        self.city = city
        self.country = country

    def parse_string(self, location):
        self.full_string = location
        if ',' in location:
            # TODO: Probably useless try - except. To be checked.
            try:
                self.city = location.split(',')[0]
                self.country = location.split(',')[-1]
            except:
                pass


def chunks(lst, n):
    if n == 0:
        return [lst]
    """Yield successive n-sized chunks from lst."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def is_url_valid(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None


def get_months_between_dates(date1, date2):

    if date1 < date2:
        diff = date2 - date1
    elif date1 > date2:
        diff = date1 - date2
    else:
        return 0

    return diff.days // 30


def boolean_to_string_xls(boolean_value):
    if boolean_value is None:
        return 'N/A'

    return 'X' if boolean_value else ''


def date_to_string_xls(date):
    if date is None:
        return 'N/A'

    return datetime.strftime(date, "%b-%y")


def message_to_user(message, speak=True):
    print(message)

    if speak:
        engine = pyttsx3.init()
        engine.say(message)
        engine.runAndWait()


