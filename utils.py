import re
import pyttsx3
from datetime import datetime




def get_months_between_dates(date1, date2):

    if date1 < date2:
        diff = date2 - date1
    elif date1 > date2:
        diff = date1 - date2
    else:
        return 0

    return diff.days // 30



