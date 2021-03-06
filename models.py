import functools
from datetime import datetime
import psycopg2

def canonize_linkedin_url(linkedin_url):
    # keyword search company URLs don't end in '/'
    if '?keywords=' in linkedin_url:
        return linkedin_url
    else: # everything else (companies, people) ends with '/'
        return f"{linkedin_url}/" if not linkedin_url.endswith('/') else linkedin_url

class Person:
    def __init__(self, name, linkedin_url):
        self.name = name
        self.linkedin_url = linkedin_url

        self.summary = None
        self.location = None
        self.contact_info = None
        self.skills = None
        self.recommendations_given = None
        self.recommendations_received = None
        self.job_history = None

    def __str__(self):
        companies = "Companies:\n" + "\n".join([ job.company.full_details() for job in self.job_history ]) if self.job_history else ''
        return f"Profile for {self.contact_info.name}\n   {self.contact_info}\n   {self.skills}\n   Received {self.recommendations_received}\n   Given {self.recommendations_given}\n   {self.job_history}\n{companies}"

    def is_same(self, other):
        return canonize_linkedin_url(self.linkedin_url) == canonize_linkedin_url(other.linkedin_url)

    def all_company_ids(self):
        if self.job_history is None: return []
        return [ job.company_id for job in self.job_history ]

    def all_manager_ids(self):
        if self.recommendations_given is None or self.recommendations_received is None: return []
        return [ r.manager_id for r in self.recommendations_given + self.recommendations_received if r.manager_id ]

    def save_to_db(self):
        person_id = Person.find_or_create_in_db(self.name, self.linkedin_url, self.summary, self.location)
        self.update_new_info_in_db(person_id)

        if self.contact_info: self.contact_info.save_to_db('Person', person_id)

        if self.skills: self.skills.save_to_db(person_id)

        if self.recommendations_given: self.recommendations_given.save_to_db(person_id, person_is='giver')
        if self.recommendations_received: self.recommendations_received.save_to_db(person_id, person_is='receiver')

        if self.job_history: self.job_history.save_to_db(person_id)

        return person_id

    def update_new_info_in_db(self, person_id):
        # check if we have new/better information on the person
        rows = db_instance().exec_read('SELECT name, summary, location FROM people WHERE id = %s', (person_id,))
        p_name, p_summary, p_location = rows[0]
        new_info = {}
        if not p_name and self.name: new_info['name'] = self.name
        if not p_summary and self.name: new_info['summary'] = self.summary
        if not p_location and self.name: new_info['location'] = self.location

        if new_info:
            print(f"UPDATE Person {self.name} person_id={person_id} with {new_info}")
            updated_at = datetime.utcnow()
            sql = '''
                UPDATE people SET (name, summary, location, updated_at)
                = (%s, %s, %s, %s)
                WHERE people.id = %s
                RETURNING id
            '''
            params = (p_name or self.name, p_summary or self.summary, p_location or self.location, updated_at, person_id)
            _ = db_instance().exec_write(sql, params)

    @classmethod
    def find_or_create_in_db(cls, name, linkedin_url, summary, location=None):
        linkedin_url = canonize_linkedin_url(linkedin_url)
        '''does a quick creation of a person with just name and linkedin_url'''
        created_at = updated_at = datetime.utcnow()
        sql = '''
            INSERT INTO people (name, linkedin_url, summary, location, created_at, updated_at) 
            VALUES(%s, %s, %s, %s, %s, %s)
            ON CONFLICT (linkedin_url) DO NOTHING
            RETURNING id
        '''
        params = (name, linkedin_url, summary, location, created_at, updated_at)
        person_id = db_instance().exec_write(sql, params)
        if person_id:
            print(f"INSERTED Person {name} person_id={person_id}")
        else:
            person_id = db_instance().exec_read('SELECT id FROM people WHERE linkedin_url = %s', (linkedin_url,))[0][0]
            print(f"EXISTING Person {name} person_id={person_id}")

        return person_id

class ContactInfo:
    def __init__(self, name):
        self.name = name
        self.attrs = 'websites phones emails twitter_urls'.split()
        for key in self.attrs: setattr(self, key, [])

    def contact_points(self):
        '''Returns a list of (channel, info) tuples'''
        result = []
        for channel in self.attrs:
            points = getattr(self, channel)
            for info in points:
                # deal with phones like {'Mobile': '650-224-1605'}
                if isinstance(info, dict): info = list(info.values())[0]
                result.append((channel[:-1], info))
        return result

    def __str__(self):
        return "\n   ".join([f"{attr}: {getattr(self, attr)}" for attr in self.attrs if getattr(self, attr)])

    def save_to_db(self, contactable_type, contactable_id):
        for channel, info in self.contact_points():
            created_at = updated_at = datetime.utcnow()
            sql = '''
                INSERT INTO contact_points (channel, info, contactable_type, contactable_id, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (channel, info) DO NOTHING
                RETURNING id
            '''
            params = (channel, info, contactable_type, contactable_id, created_at, updated_at)
            cp_id = db_instance().exec_write(sql, params)
            if cp_id:
                print(f"   INSERTED ContactPoint {channel}: {info} p_id={cp_id}")
            else:
                print(f"   EXISTING ContactPoint {channel}: {info}")

        return None


class Skills:
    def __init__(self, skills_list):
        self.skills_list = skills_list

    def __str__(self):
        return f"skills: {', '.join(self.skills_list)}"

    def save_to_db(self, person_id):
        for name in self.skills_list:

            skill_id = Skills.find_or_create_skill_in_db(name)

            created_at = updated_at = datetime.utcnow()
            #  ON CONFLICT ON CONSTRAINT (index_person_skills_on_person_id_and_skill_id) DO NOTHING
            sql = '''
                INSERT INTO person_skills (person_id, skill_id, created_at, updated_at) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (person_id, skill_id) DO NOTHING
                RETURNING id
            '''
            params = (person_id, skill_id, created_at, updated_at)
            ps_id = db_instance().exec_write(sql, params)
            # if ps_id:
            #     print(f"   INSERTED PersonSkill ps_id={ps_id}")
            # else:
            #     print(f"   FOUND existing PersonSkill ps_id={ps_id}")

        return None

    @classmethod
    def find_or_create_skill_in_db(cls, name):
        '''returns the skill with the given name, inserting it if necessary'''
        created_at = updated_at = datetime.utcnow()
        # find_or_create skill (requires unique index on name column)
        sql = '''
            INSERT INTO skills (name, created_at, updated_at) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (name) DO NOTHING 
            RETURNING id
        '''
        params = (name, created_at, updated_at)
        skill_id = db_instance().exec_write(sql, params)

        if skill_id:
            print(f"   INSERTED Skill {name} skill_id={skill_id}")
        else:
            skill_id = db_instance().exec_read('SELECT id FROM skills WHERE name = %s', (name,))[0][0]
            print(f"   EXISTING Skill {name} skill_id={skill_id}")

        return skill_id


class Recommendation:
    def __init__(self):
        # name and linkedin_url of the other person involved in the recommendation
        self.linkedin_url = None
        self.name = None

        self.title_co = None
        self.date = None
        self.relationship = None
        self.reciprocal = False

        self.manager_id = None # used by Person to return a list of manager_ids

    def __str__(self):
        flags = []
        if self.reciprocal: flags.append('*reciprocal*')
        if self.managed: flags.append('*MANAGER*')
        return f"{self.date}: {', '.join(flags) if flags else ''} {self.name} ({self.title_co}) {self.relationship}"

    # These are dumb functions that just tell if 'managed' or 'reported directly' is in the relationship
    def managed(self):
        return bool('managed' in self.relationship)

    def reported_to(self):
        return bool('reported directly' in self.relationship)

    def save_to_db(self, person_id, person_is):
        # find or create the person giving the recommendation
        other_id = Person.find_or_create_in_db(self.name, self.linkedin_url, self.title_co) # self.title_co is the person's summary
        giver_id, receiver_id = (person_id, other_id) if person_is == 'giver' else (other_id, person_id)

        created_at = updated_at = datetime.utcnow()
        sql = '''
            INSERT INTO recommendations (giver_id, receiver_id, title_co, date, relationship, reciprocal, managed, created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (giver_id, receiver_id) DO NOTHING 
            RETURNING id
        '''
        params = (giver_id, receiver_id, self.title_co, self.date, self.relationship, self.reciprocal, self.managed(), created_at, updated_at)
        recommendation_id = db_instance().exec_write(sql, params)

        if recommendation_id:
            print(f"   INSERTED Recommendation")
        else:
            print(f"   EXISTING Recommendation")

        if self.managed() or self.reported_to(): # create manager_subordinate row
            # Assumes the giver is always the one who managed or reported to the person
            manager_id, subordinate_id = (receiver_id, giver_id) if self.reported_to() else (giver_id, receiver_id)

            # save the manager_id if the other was the manager
            if manager_id == other_id: self.manager_id = manager_id

            # INSERT INTO manager_subordinates (manager_id, subordinate_id, created_at, updated_at)
            created_at = updated_at = datetime.utcnow()
            sql = '''
                INSERT INTO manager_subordinates (manager_id, subordinate_id, created_at, updated_at) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (manager_id, subordinate_id) DO NOTHING 
                RETURNING id
            '''
            params = (manager_id, subordinate_id, created_at, updated_at)
            recommendation_id = db_instance().exec_write(sql, params)

        return recommendation_id

class Recommendations:
    def __init__(self):
        self.recommendations = []

    def __iter__(self):
        return iter(self.recommendations)

    def __add__(self, other):
        result = Recommendations()
        result.recommendations = self.recommendations + other.recommendations
        return result

    def __str__(self):
        result = 'Recommendations:'
        for recommendation in self.recommendations:
            result += f"\n      {recommendation}"
        return result

    def add(self, recommendation: Recommendation):
        self.recommendations.append(recommendation)

    def save_to_db(self, person_id, person_is):
        for recommendation in self.recommendations:
            recommendation.save_to_db(person_id, person_is)


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

    def is_same(self, other):
        return canonize_linkedin_url(self.linkedin_url) == canonize_linkedin_url(other.linkedin_url)

    def full_details(self):
        result = f"{self.name} is a "
        if self.shareholder_type: result += f"{self.shareholder_type} "
        if self.industry: result += f"{self.industry} company "
        if self.founded: result += f"founded {self.founded} "
        if self.headquarters: result += f"with headquarters in {self.headquarters} "
        if self.phone: result += f"\nphone {self.phone} "
        if self.website: result += f"\nwebsite {self.website} "
        if self.linkedin_url: result += f"linkedin {self.linkedin_url} "
        if self.size: result += f"\n {self.name} has about {self.size} "
        if self.current_linkedin_employees: result += f"({self.current_linkedin_employees} on LinkedIn) "
        employee_strs = [ f"{e.name}: {e.job_history.jobs[0].positions[0].title if e.job_history else ''}" for e in self.employees ]
        if employee_strs: result += f"including  {', '.join(employee_strs)}"
        return result

    def add_employee(self, person: Person):
        self.employees.append(person)

    def save_to_db(self):
        company_id = Company.find_or_create_in_db(self.name, self.linkedin_url)
        self.update_new_info_in_db(company_id)

        # create contact points for website and phone
        if self.website or self.phone:
            contact_info = ContactInfo(self.name)
            if self.website: contact_info.websites.append(self.website)
            if self.phone: contact_info.phones.append(self.phone)
            contact_info.save_to_db('Company', company_id)

        if self.employees:
            for e in self.employees:
                print(f"      SAVING employee {e.name}")
                e.save_to_db() # will update the person, but not add the job position if it has the same title and company_id

        return company_id

    def update_new_info_in_db(self, company_id):
        # Update will blow away any existing values (but not employees)

        rows = db_instance().exec_read('SELECT name, industry, size, headquarters, shareholder_type, founded, current_linkedin_employees, num_linkedin_results FROM companies WHERE id = %s', (company_id,))
        c_name, c_industry, c_size, c_headquarters, c_shareholder_type, c_founded, c_current_linkedin_employees, c_num_linkedin_results = rows[0]
        new_info = {}

        if not c_name and self.name: new_info['name'] = self.name
        if not c_industry and self.industry: new_info['industry'] = self.industry
        if not c_size and self.size: new_info['size'] = self.size
        if not c_headquarters and self.headquarters: new_info['headquarters'] = self.headquarters
        if not c_shareholder_type and self.shareholder_type: new_info['shareholder_type'] = self.shareholder_type
        if not c_founded and self.founded: new_info['founded'] = self.founded
        if not c_current_linkedin_employees and self.current_linkedin_employees: new_info['current_linkedin_employees'] = self.current_linkedin_employees
        if not c_num_linkedin_results and self.num_linkedin_results: new_info['num_linkedin_results'] = self.num_linkedin_results

        if new_info:
            print(f"UPDATE Company {self.name} company_id={company_id} with {new_info}")
            updated_at = datetime.utcnow()
            sql = '''
                UPDATE companies SET (name, industry, size, headquarters, shareholder_type, founded, current_linkedin_employees, num_linkedin_results, updated_at) 
                = (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                WHERE companies.id = %s
                RETURNING id
            '''

            params = (c_name or self.name, c_industry or self.industry, c_size or self.size, c_headquarters or self.headquarters, c_shareholder_type or self.shareholder_type, c_founded or self.founded,
                      c_current_linkedin_employees or self.current_linkedin_employees, c_num_linkedin_results or self.num_linkedin_results, updated_at, company_id)
            _ = db_instance().exec_write(sql, params)


    @classmethod
    def find_or_create_in_db(cls, name, linkedin_url):
        '''does a quick creation of a company with just name and linkedin_url'''
        linkedin_url = canonize_linkedin_url(linkedin_url)

        created_at = updated_at = datetime.utcnow()
        sql = '''
            INSERT INTO companies (name, linkedin_url, created_at, updated_at) 
            VALUES(%s, %s, %s, %s)
            ON CONFLICT (linkedin_url) DO NOTHING
            RETURNING id
        '''
        params = (name, linkedin_url, created_at, updated_at)
        company_id = db_instance().exec_write(sql, params)
        if company_id:
            print(f"INSERTED Company {name} company_id={company_id}")
        else:
            company_id = cls.get_id(linkedin_url)
            print(f"EXISTING Company {name} company_id={company_id}")
        return company_id

    @classmethod
    def get_id(cls, linkedin_url):
        return db_instance().exec_read('SELECT id FROM companies WHERE linkedin_url = %s', (linkedin_url,))[0][0]


# To avoid creating duplicate positions for the people who get scraped we use DEFAULT_TITLE as the title to
# allow Job.save to distinguish between an employee scrape with no title and a person's scraped job history,
# and to know whether to replace (DEFAULT_TITLE with scraped info), update (scraped info with scraped info) or
# do nothing (to scraped info when current title is DEFAULT_TITLE)
DEFAULT_TITLE = 'Employed'

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

    def save_to_db(self, job_id):
        self.title = self.title or DEFAULT_TITLE
        print(f"         INSERTING Position for job_id={job_id}")
        created_at = updated_at = datetime.utcnow()
        sql = '''
            INSERT INTO positions (job_id, date_range, duration, title, location, created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        '''
        params = (job_id, self.date_range, self.duration, self.title, self.location, created_at, updated_at)
        position_id = db_instance().exec_write(sql, params)
        return position_id



class Job:
    def __init__(self):
        self.company = Company()
        self.positions = []
        self.total_duration = None

    def __str__(self):
        if self.positions:
            duration, location = self.positions[0].date_range, self.positions[0].location
            if len(self.positions) > 1: duration = self.total_duration
        else:
            duration = f"Job at {self.company.name} has no positions"
        return f"{self.company} {duration if duration else ''}"

    def add_position(self, position: Position):
        self.positions.append(position)

    def save_to_db(self, person_id, existing_jobs):
        '''Saves the job inserting if not already in existing_jobs, which is a dict of {company_id: existing_job_id}'''

        # check whether the company exists because it often will and job history is not a deep scrape of the company
        self.company_id = Company.find_or_create_in_db(self.company.name, self.company.linkedin_url)

        # ASSUMPTION any job with the same (company_id, person_id) is a duplicate
        # THIS IS A BAD ASSUMPTION because we can't require (company_id, person_id) to be unique as the person may have
        # held multiple jobs with the company at different times so just updating the position instead of creating a
        # totally separate job is wrong
        if self.company_id in existing_jobs:
            existing_job_id = existing_jobs[self.company_id]
            print(f"   EXISTING Job for company_id={self.company_id}, person_id={person_id} existing_job_id={existing_job_id}")
            # TODO update with total_duration

            existing_positions = {row[0]: row[1] for row in db_instance().exec_read('SELECT title, id as position_id FROM positions WHERE job_id = %s', (existing_job_id,))}

            try:
                if self.positions[0].title is None:  # we have no new information to add
                    print(f"      SKIPPING single position with blank title for existing_job_id={existing_job_id}")
                    if len(self.positions) == 1:
                        return
                    else: # should never happen
                        raise ValueError(f"Job with multiple positions (i.e. non-employee scrape) has no title")
            except Exception as e:
                print(f"WTF: self.positions[0].title is None raised {e} ")
                print(f"existing_job_id={existing_job_id}")
                print(f"self.positions={self.positions}")
                print(f"self.total_duration={self.total_duration}")
                return

            if DEFAULT_TITLE in existing_positions:
                if len(existing_positions) != 1: print(f"   UNEXPECTED: Job has multiple positions but one with DEFAULT_TITLE")
                print(f"      DELETING default position(s) under same job for company_id={self.company_id}, person_id={person_id} existing_job_id={existing_job_id}")
                db_instance().exec_write('''DELETE from positions WHERE job_id = (%s) AND title = (%s)''', (existing_job_id, DEFAULT_TITLE), return_id=False)

            for p in self.positions:
                # ASSUMPTION the person could not have held multiple positions with the same title at the job
                if existing_positions and p.title in existing_positions:
                    print(f"      EXISTING Position with title={p.title} for existing_job_id={existing_job_id}")
                else:
                    p.save_to_db(existing_job_id)

        else: # this is a totally new job, so just add all the positions
            print(f"      INSERTING job for person_id = {person_id} company_id = {self.company_id}")
            created_at = updated_at = datetime.utcnow()
            sql = '''
                INSERT INTO jobs (company_id, person_id, total_duration, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            '''
            params = (self.company_id, person_id, self.total_duration, created_at, updated_at)
            job_id = db_instance().exec_write(sql, params)

            for p in self.positions: p.save_to_db(job_id)


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

    def save_to_db(self, person_id):
        print(f"   SAVING job history for Person {person_id}")

        # search for existing jobs once and pass into Job.save_to_db so it can update and not duplicate existing jobs
        existing_jobs = {row[0]: row[1] for row in db_instance().exec_read('SELECT company_id, id as job_id FROM jobs WHERE person_id = %s', (person_id,))}
        for job in self.jobs:
            job.save_to_db(person_id, existing_jobs)


class Scrape:
    def __init__(self, id, scrapable_type, flags, url):
        self.id = id
        self.scrapable_type = scrapable_type
        self.flags = flags
        self.url = url  # this comes from a join with the scrapable_type (i.e. Person or Company)

        self.status = 0
        self.message = None

    def do_companies(self):
        return self.scrapable_type == 'Person' and self.flags and 'c' in self.flags

    def do_managers(self):
        return self.scrapable_type == 'Person' and self.flags and 'm' in self.flags

    def update_status_in_db(self):
        last_scraped = updated_at = datetime.utcnow()
        sql = '''
            UPDATE scrapes SET (status, message, last_scraped, updated_at) = (%s, %s, %s, %s)
            WHERE scrapes.id = %s RETURNING id
        '''
        params = (self.status, self.message, last_scraped, updated_at, self.id)
        return db_instance().exec_write(sql, params)

    @classmethod
    def find_or_create_in_db(cls, scrapable_type, scrapable_id, flags=None):
        '''does a quick creation of a scrape with just scrapable_type and scrapable_id'''
        created_at = updated_at = datetime.utcnow()
        sql = '''
            INSERT INTO scrapes (scrapable_type, scrapable_id, flags, created_at, updated_at) 
            VALUES(%s, %s, %s, %s, %s)
            ON CONFLICT (scrapable_type, scrapable_id) DO NOTHING
            RETURNING id
        '''
        params = (scrapable_type, scrapable_id, flags, created_at, updated_at)
        _ = db_instance().exec_write(sql, params)



    @classmethod
    def next_unscraped(cls):
        '''Returns a scrape object with the URL to scrape if an unscraped scrape exists'''
        table_map = {'Person': 'people', 'Company': 'companies'}

        for scrapable_type, table_name in table_map.items():
            sql = f'''SELECT s.id, s.scrapable_type, s.flags, t.linkedin_url
            FROM {table_name} t
            JOIN scrapes s ON s.scrapable_id = t.id 
            WHERE s.scrapable_type = %s AND s.last_scraped IS NULL 
            LIMIT 1'''

            rows = db_instance().exec_read(sql, (scrapable_type,))
            if rows:
                return cls(*rows[0])

        # returns None if no unscraped scrapes are found


@functools.lru_cache()
def db_instance():
    return RailsDB()

class RailsDB:
    def __init__(self, db_url="postgresql://localhost:5432/alex_development"):
        print(f"**** NEW DB CONNECTION ****")
        self.conn = psycopg2.connect(db_url)
        self.cur = self.conn.cursor()

    # Alternative syntax using with
    # with self.conn:
    #     with self.conn.cursor() as curs:
    #         curs.execute(sql, params)


    def exec_read(self, sql, params=()):
        # print(f"SQL: {sql}\nPARAMS: {params}")
        self.cur.execute(sql, params)
        return self.cur.fetchall()


    def exec_write(self, sql, params, commit=True, return_id=True):
        self.cur.execute(sql, params)
        if commit: self.commit_all()
        if return_id:
            row_with_id = self.cur.fetchone()
            return row_with_id and int(row_with_id[0])

    def commit_all(self):
        self.conn.commit()


    def close(self):
        self.cur.close()
        self.conn.close()


def ejp_test():
    kh = Person('Keith Hulen', 'https://www.linkedin.com/in/keith-hulen-a874175/')
    kh_id = kh.save_to_db()

    ejp = Person('ed posnak', 'https://linkedin.com/in/edposnak')

    ejp.contact_info = ContactInfo(ejp.name)
    ejp.contact_info.phones.append('415.254.0086')
    ejp.contact_info.emails.append('ejp@gmail.com')
    ejp.skills = Skills(['Running', 'Jumping', 'Peeing', 'Humping'])
    ejp.recommendations = Recommendations()

    r1 = Recommendation()
    r1.name, r1.linkedin_url = 'Keith Hulen', 'https://www.linkedin.com/in/keith-hulen-a874175/'
    r1.title_co = 'Co-founder of Veridyme'
    r1.date, r1.relationship = 'November 5, 2013', 'Keith managed Ed directly'
    r1.reciprocal = False
    ejp.recommendations.add(r1)

    r2 = Recommendation()
    r2.name, r2.linkedin_url = 'Jennifer Gunther', 'https://www.linkedin.com/in/jennifergunther/'
    r2.title_co = 'Lead Digital Product Designer at Self Employed'
    r2.date, r2.relationship = 'January 1, 2020', 'Jennifer knows Ed'
    r2.reciprocal = True
    ejp.recommendations.add(r2)

    # JobHistory
    # 1 (single-position job)
    c1 = Company()
    c1.name, c1.linkedin_url = 'Apple', 'https://www.linkedin.com/company/apple'
    ejp.job_history = JobHistory.from_single_position_title(c1, position_title='Brewmaster')

    # 2 (multi-position job w/total_duration, company.employees, etc.)
    j2 = Job()
    j2.total_duration = '6 years 5 months'
    c2 = Company()
    c2.name, c2.linkedin_url = 'Xetex', 'https://www.linkedin.com/search/results/all/?keywords=Xetex'
    c2.employees = [ Person('Rick Fister', 'https://www.linkedin.com/in/rick-fister-7452572/'),
                     Person('Brahm Windler', 'https://www.linkedin.com/in/brahmwindeler/') ]
    c2.size, c2.founded = '10-15 Employees', 1998
    c2.headquarters, c2.num_linkedin_results = 'Austin, TX', 13
    j2.company = c2

    p1 = Position()
    p1.title, p1.date_range = 'Founder and President', 'July 1998 - September 2002'
    p1.location, p1.duration = 'San Francisco, CA', None

    p2 = Position()
    p2.title, p2.date_range = 'Chief Whitespace Officer', 'Jan 1994 - July 1998'
    p2.location, p2.duration = 'Austin, TX', None
    j2.positions = [p1, p2]

    ejp.job_history.add(j2)

    ejp_id = ejp.save_to_db()
