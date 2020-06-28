from datetime import datetime

class Employee:
    def __init__(self, name, linkedin_url):
        self.name = name
        self.linkedin_url = linkedin_url

        self.contact_info = None
        self.skills = None
        self.recommendations = None
        self.job_history = None

    def __str__(self):
        companies = "Companies:\n" + "\n".join([ job.company.full_details() for job in self.job_history ])
        return f"Profile for {self.contact_info.name}\n   {self.contact_info}\n   {self.skills}\n   {self.recommendations}\n   {self.job_history}\n{companies}"

class ContactInfo:
    def __init__(self, name):
        self.name = name
        self.attrs = 'websites phones emails twitter_urls'.split()
        for key in self.attrs: setattr(self, key, [])

    def __str__(self):
        return "\n   ".join([f"{attr}: {getattr(self, attr)}" for attr in self.attrs if getattr(self, attr)])

class Skills:
    def __init__(self, skills_list):
        self.skills_list = skills_list

    def __str__(self):
        return f"skills: {', '.join(self.skills_list)}"

class Company:
    def __init__(self):
        self.name = None
        self.linkedin_url = None

        self.website = None
        self.phone = None
        self.industry = None
        self.size = None
        self.headquarters = None
        self.shareholder_type = None
        self.founded = None

        self.employees = []
        self.current_linkedin_employees = 0 # as indicated by the company about page
        self.num_linkedin_results = None # as found in search results (could be past employees)

    def __str__(self):
        return f"{self.name} {self.industry or ''} {self.headquarters or ''}"

    def merge(self, other):
        if self.linkedin_url != other.linkedin_url:
            raise ValueError(f"attempt to merge company with a different linkedin_url self={self.linkedin_url} other={other.linkedin_url}")

        for k, v in other.__dict__.items():
            if v:
                self_val = getattr(self, k)
                # if self_val and v != self_val: print(f"self.{k}={self_val} and other.{k}={v}")
                if isinstance(self_val, list): # merge employees
                    self_val.extend(v)
                else: # overwrite other attributes
                    setattr(self, k, v)
                
    def full_details(self):
        result = f"{self.name} is a "
        if self.shareholder_type: result += f"{self.shareholder_type} "
        if self.industry: result += f"{self.industry} company "
        if self.founded: result += f"founded {self.founded} "
        if self.headquarters: result += f"with headquarters in {self.headquarters} "
        if self.phone: result += f"\nphone {self.phone} "
        if self.website: result += f"\nwebsite {self.website} "
        if self.website: result += f"linkedin {self.linkedin_url} "
        if self.size: result += f"\n {self.name} has about {self.size} "
        if self.current_linkedin_employees: result += f"({self.current_linkedin_employees} on LinkedIn) "
        employee_strs = [ f"{e.name}: {e.job_history.jobs[0].positions[0].title if e.job_history else ''}" for e in self.employees ]
        if employee_strs: result += f"including  {', '.join(employee_strs)}"
        return result

    def add_employee(self, employee: Employee):
        self.employees.append(employee)


class Position:
    def __init__(self):
        self.date_range = None
        self.duration = None
        self.title = None
        self.location = None

    def __str__(self):
        return f"{self.date_range or self.duration} {self.title} {self.location}"

    def get_start_and_end_dates(self):
        if not self.date_range: return None, None

        dates = self.date_range.split(' – ')
        if len(dates) > 1:
            begin = self.parse_date(dates[0])
            if dates[1] == 'less than a year':
                end = begin
            else:
                end = self.parse_date(dates[1])
                end = datetime.fromtimestamp(datetime.timestamp(end) + 24 * 60 * 60 * 31) # TODO 31 days is too long, also -1 second to get 12:59pm
        else:
            # TODO is this date_range string really a parsable date?
            print(f"split_date_range: '{self.date_range}' is not a range")
            end = begin = self.parse_date(self.date_range.strip())

        return begin, end

    # private
    def parse_date(self, date_str):
        if date_str == 'Present':
            return datetime.today()
        try:
            date = datetime.strptime(date_str, '%b %Y')
            return date
        except ValueError:
            try:
                date = datetime.strptime(date_str, '%Y')
                return date
            except ValueError:
                return None

class Job:
    def __init__(self):
        self.company = Company()
        self.positions = []
        self.total_duration = None

    def __str__(self):
        duration, location = self.positions[0].date_range, self.positions[0].location
        if len(self.positions) > 1:
            duration = self.total_duration
        return f"{self.company} {duration if duration else ''}"

    def add_position(self, position: Position):
        self.positions.append(position)


class JobHistory:
    def __init__(self):
        self.jobs = []

    def __iter__(self):
        return iter(self.jobs)

    def __len__(self):
        return len(self.jobs)

    def __str__(self):
        result = 'Job History:'
        for job in self.jobs:
            result += f"\n      {job}"
            for position in job.positions:
                result += f"\n         {position}"
        return result

    def add(self, job: Job):
        self.jobs.append(job)

    @classmethod
    def from_single_position_title(cls, company, position_title):
        position = Position()
        position.title = position_title
        job = Job()
        job.company = company
        job.add_position(position)
        job_history = cls()
        job_history.add(job)
        return job_history


class Recommendation:
    def __init__(self):
        self.linkedin_url = None
        self.name = None
        self.title_co = None
        self.date = None
        self.relationship = None
        self.reciprocal = None

    def __str__(self):
        flags = []
        if self.reciprocal: flags.append('*reciprocal*')
        if self.relationship and 'managed' in self.relationship: flags.append('*managed*')
        return f"{self.date}: {flags if flags else ''} {self.name} ({self.title_co}) {self.relationship}"


class Recommendations:
    def __init__(self):
        self.recommendations = []

    def __iter__(self):
        return iter(self.recommendations)

    def __str__(self):
        result = 'Recommendations:'
        for recommendation in self.recommendations:
            result += f"\n      {recommendation}"
        return result


    def add(self, recommendation: Recommendation):
        self.recommendations.append(recommendation)

