#!/usr/bin/env python3
"""
Realistic Customer Data Generator for Entity Resolution Demo

Generates synthetic but believable customer data with intentional duplicates
and variations that mirror real-world data quality issues.
"""

import json
import random
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import uuid
from dataclasses import dataclass
import argparse


@dataclass
class CustomerProfile:
    """Base customer profile for generating variations"""
    first_name: str
    last_name: str
    email_base: str
    phone_base: str
    company: str
    title: str
    address: str
    city: str
    state: str
    zip_code: str
    industry: str
    revenue: int
    employees: int
    created_date: datetime


class DataGenerator:
    """Generates realistic customer data with intentional duplicates"""
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.load_reference_data()
        
    def load_reference_data(self):
        """Load realistic reference data for generation"""
        
        # Common first names with nickname variations
        self.first_names = {
            'Robert': ['Bob', 'Rob', 'Bobby'],
            'William': ['Bill', 'Will', 'Billy'],
            'James': ['Jim', 'Jimmy', 'Jamie'],
            'John': ['Johnny', 'Jon'],
            'Michael': ['Mike', 'Mick', 'Mickey'],
            'David': ['Dave', 'Davey'],
            'Richard': ['Rick', 'Dick', 'Ricky'],
            'Joseph': ['Joe', 'Joey'],
            'Thomas': ['Tom', 'Tommy'],
            'Christopher': ['Chris', 'Christie'],
            'Daniel': ['Dan', 'Danny'],
            'Matthew': ['Matt', 'Matty'],
            'Anthony': ['Tony'],
            'Donald': ['Don', 'Donny'],
            'Steven': ['Steve', 'Stevie'],
            'Andrew': ['Andy', 'Drew'],
            'Joshua': ['Josh'],
            'Kenneth': ['Ken', 'Kenny'],
            'Kevin': ['Kev'],
            'Brian': ['Bryan'],
            'George': ['Georgie'],
            'Edward': ['Ed', 'Eddie', 'Ted'],
            'Ronald': ['Ron', 'Ronny'],
            'Timothy': ['Tim', 'Timmy'],
            'Jason': ['Jay'],
            'Jeffrey': ['Jeff'],
            'Ryan': ['Ry'],
            'Jacob': ['Jake'],
            'Gary': [],
            'Nicholas': ['Nick', 'Nicky'],
            'Eric': [],
            'Jonathan': ['Jon', 'Johnny'],
            'Stephen': ['Steve', 'Stevie'],
            'Larry': [],
            'Justin': [],
            'Scott': ['Scotty'],
            'Brandon': [],
            'Benjamin': ['Ben', 'Benny'],
            'Samuel': ['Sam', 'Sammy'],
            'Gregory': ['Greg'],
            'Frank': ['Frankie'],
            'Raymond': ['Ray'],
            'Alexander': ['Alex', 'Al'],
            'Patrick': ['Pat', 'Paddy'],
            'Jack': ['Jackie'],
            'Dennis': ['Denny'],
            'Jerry': [],
            'Tyler': ['Ty'],
            'Aaron': [],
            'Henry': ['Hank'],
            'Douglas': ['Doug'],
            'Nathan': ['Nate'],
            'Peter': ['Pete'],
            'Zachary': ['Zach'],
            'Kyle': [],
            'Noah': [],
            'Alan': ['Al'],
            'Ethan': [],
            'Jeremy': ['Jerry'],
            'Lionel': [],
            'Arthur': ['Art'],
            'Carl': [],
            'Harold': ['Harry'],
            'Jordan': [],
            'Jesse': [],
            'Bryan': ['Brian'],
            'Lawrence': ['Larry'],
            'Arthur': ['Art'],
            'Gabriel': ['Gabe'],
            'Bruce': [],
            'Logan': [],
            'Wayne': [],
            'Ralph': [],
            'Roy': [],
            'Eugene': ['Gene'],
            'Louis': ['Lou'],
            'Philip': ['Phil'],
            'Bobby': ['Bob'],
            'Johnny': ['John'],
            'Mason': [],
            
            # Female names
            'Mary': ['Marie'],
            'Patricia': ['Pat', 'Patty', 'Tricia'],
            'Jennifer': ['Jen', 'Jenny'],
            'Linda': [],
            'Elizabeth': ['Liz', 'Beth', 'Betty', 'Lizzy'],
            'Barbara': ['Barb', 'Barbie'],
            'Susan': ['Sue', 'Susie'],
            'Jessica': ['Jess', 'Jessie'],
            'Sarah': ['Sara'],
            'Karen': [],
            'Nancy': [],
            'Lisa': [],
            'Betty': ['Beth'],
            'Helen': [],
            'Sandra': ['Sandy'],
            'Donna': [],
            'Carol': ['Carrie'],
            'Ruth': [],
            'Sharon': ['Shari'],
            'Michelle': ['Shelly'],
            'Laura': [],
            'Sarah': ['Sara'],
            'Kimberly': ['Kim'],
            'Deborah': ['Deb', 'Debbie'],
            'Dorothy': ['Dot', 'Dotty'],
            'Lisa': [],
            'Nancy': [],
            'Karen': [],
            'Betty': ['Beth'],
            'Helen': [],
            'Sandra': ['Sandy'],
            'Donna': [],
            'Carol': ['Carrie'],
            'Ruth': [],
            'Sharon': ['Shari'],
            'Michelle': ['Shelly'],
            'Laura': [],
            'Emily': ['Em', 'Emmy'],
            'Ashley': ['Ash'],
            'Kimberly': ['Kim'],
            'Linda': [],
            'Sarah': ['Sara'],
            'Brittany': ['Britt'],
            'Megan': ['Meg'],
            'Nicole': ['Nikki'],
            'Jessica': ['Jess', 'Jessie'],
            'Elizabeth': ['Liz', 'Beth', 'Betty'],
            'Rebecca': ['Becky', 'Becca'],
            'Kelly': [],
            'Christina': ['Chris', 'Christie', 'Tina'],
            'Amanda': ['Mandy'],
            'Melissa': ['Mel'],
            'Deborah': ['Deb', 'Debbie'],
            'Rachel': [],
            'Carolyn': ['Carol', 'Carrie'],
            'Janet': [],
            'Catherine': ['Cathy', 'Kate', 'Katie'],
            'Maria': [],
            'Heather': [],
            'Diane': [],
            'Julie': [],
            'Joyce': [],
            'Victoria': ['Vicky', 'Tori'],
            'Kelly': [],
            'Christina': ['Chris', 'Christie'],
            'Joan': [],
            'Evelyn': [],
            'Lauren': [],
            'Judith': ['Judy'],
            'Megan': ['Meg'],
            'Cheryl': [],
            'Andrea': ['Andy'],
            'Hannah': [],
            'Jacqueline': ['Jackie'],
            'Martha': [],
            'Gloria': [],
            'Teresa': ['Terry'],
            'Sara': ['Sarah'],
            'Janice': ['Jan'],
            'Marie': ['Mary'],
            'Julia': ['Julie'],
            'Kathryn': ['Kathy', 'Kate'],
            'Frances': ['Fran'],
            'Jean': [],
            'Abigail': ['Abby'],
            'Alice': [],
            'Judy': ['Judith'],
            'Sophia': ['Sophie'],
            'Grace': [],
            'Denise': [],
            'Amber': [],
            'Doris': [],
            'Marilyn': [],
            'Danielle': ['Dani'],
            'Beverly': ['Bev'],
            'Charlotte': ['Charlie'],
            'Marie': ['Mary'],
            'Diana': [],
            'Alexis': ['Alex'],
            'Lori': [],
            'Rose': [],
            'Katherine': ['Kathy', 'Kate', 'Katie'],
            'Tiffany': ['Tiff'],
            'Pamela': ['Pam'],
            'Anna': [],
            'Amy': [],
            'Nicole': ['Nikki'],
            'Emma': ['Em'],
            'Brenda': [],
            'Emma': ['Em'],
            'Olivia': ['Liv'],
            'Cynthia': ['Cindy'],
            'Marie': ['Mary'],
            'Janet': [],
            'Catherine': ['Cathy', 'Kate'],
            'Frances': ['Fran'],
            'Christine': ['Chris', 'Christie'],
            'Samantha': ['Sam'],
            'Debra': ['Deb', 'Debbie'],
            'Rachel': [],
            'Carolyn': ['Carol'],
            'Janet': [],
            'Virginia': ['Ginny'],
            'Maria': [],
            'Heather': [],
            'Diane': [],
            'Ruth': [],
            'Julie': [],
            'Joyce': [],
            'Victoria': ['Vicky'],
            'Kelly': [],
            'Christina': ['Chris'],
            'Joan': [],
            'Evelyn': [],
            'Lauren': [],
            'Judith': ['Judy'],
            'Megan': ['Meg'],
            'Andrea': ['Andy'],
            'Cheryl': [],
            'Hannah': [],
            'Jacqueline': ['Jackie'],
            'Martha': [],
            'Madison': ['Maddie'],
            'Teresa': ['Terry'],
            'Gloria': [],
            'Sara': ['Sarah'],
            'Janice': ['Jan'],
            'Ann': ['Annie'],
            'Kathryn': ['Kathy'],
            'Abigail': ['Abby'],
            'Sophia': ['Sophie'],
            'Frances': ['Fran'],
            'Jean': [],
            'Alice': [],
            'Judy': ['Judith'],
            'Isabella': ['Bella', 'Izzy'],
            'Julia': ['Julie'],
            'Grace': [],
            'Amber': [],
            'Denise': [],
            'Danielle': ['Dani'],
            'Marilyn': [],
            'Beverly': ['Bev'],
            'Charlotte': ['Charlie'],
            'Marie': ['Mary']
        }
        
        # Common last names for realistic distribution
        self.last_names = [
            'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
            'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
            'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
            'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker',
            'Young', 'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill',
            'Flores', 'Green', 'Adams', 'Nelson', 'Baker', 'Hall', 'Rivera', 'Campbell',
            'Mitchell', 'Carter', 'Roberts', 'Gomez', 'Phillips', 'Evans', 'Turner',
            'Diaz', 'Parker', 'Cruz', 'Edwards', 'Collins', 'Reyes', 'Stewart', 'Morris',
            'Morales', 'Murphy', 'Cook', 'Rogers', 'Gutierrez', 'Ortiz', 'Morgan',
            'Cooper', 'Peterson', 'Bailey', 'Reed', 'Kelly', 'Howard', 'Ramos', 'Kim',
            'Cox', 'Ward', 'Richardson', 'Watson', 'Brooks', 'Chavez', 'Wood', 'James',
            'Bennett', 'Gray', 'Mendoza', 'Ruiz', 'Hughes', 'Price', 'Alvarez', 'Castillo',
            'Sanders', 'Patel', 'Myers', 'Long', 'Ross', 'Foster', 'Jimenez'
        ]
        
        # Company names with variations
        self.companies = {
            'Microsoft': ['Microsoft Corp', 'Microsoft Corporation', 'MSFT', 'Microsoft Inc'],
            'Apple': ['Apple Inc', 'Apple Computer', 'Apple Corp'],
            'Google': ['Google Inc', 'Google LLC', 'Alphabet Inc', 'Alphabet'],
            'Amazon': ['Amazon.com', 'Amazon Inc', 'Amazon Web Services', 'AWS'],
            'Meta': ['Facebook', 'Meta Platforms', 'Facebook Inc'],
            'Tesla': ['Tesla Inc', 'Tesla Motors', 'Tesla Corp'],
            'Netflix': ['Netflix Inc', 'Netflix Corp'],
            'Salesforce': ['Salesforce.com', 'Salesforce Inc'],
            'Oracle': ['Oracle Corp', 'Oracle Corporation'],
            'IBM': ['International Business Machines', 'IBM Corp'],
            'Intel': ['Intel Corp', 'Intel Corporation'],
            'Cisco': ['Cisco Systems', 'Cisco Inc'],
            'Adobe': ['Adobe Systems', 'Adobe Inc'],
            'PayPal': ['PayPal Inc', 'PayPal Holdings'],
            'Zoom': ['Zoom Video', 'Zoom Communications'],
            'Slack': ['Slack Technologies', 'Slack Inc'],
            'Shopify': ['Shopify Inc', 'Shopify Corp'],
            'Square': ['Block Inc', 'Square Inc'],
            'Stripe': ['Stripe Inc', 'Stripe Corp'],
            'Uber': ['Uber Technologies', 'Uber Inc'],
            'Lyft': ['Lyft Inc', 'Lyft Corp'],
            'Airbnb': ['Airbnb Inc', 'Airbnb Corp'],
            'Spotify': ['Spotify Technology', 'Spotify AB'],
            'LinkedIn': ['LinkedIn Corp', 'LinkedIn Corporation'],
            'Twitter': ['Twitter Inc', 'X Corp'],
            'Snapchat': ['Snap Inc', 'Snapchat Inc'],
            'Pinterest': ['Pinterest Inc', 'Pinterest Corp'],
            'Reddit': ['Reddit Inc', 'Reddit Corp'],
            'GitHub': ['GitHub Inc', 'GitHub Corp'],
            'Atlassian': ['Atlassian Corp', 'Atlassian Inc'],
            'Dropbox': ['Dropbox Inc', 'Dropbox Corp']
        }
        
        # Job titles by level
        self.job_titles = {
            'c_level': ['CEO', 'CTO', 'CFO', 'CMO', 'COO', 'CDO', 'CISO', 'CPO'],
            'vp': ['VP Engineering', 'VP Sales', 'VP Marketing', 'VP Operations', 'VP Product'],
            'director': ['Director of Engineering', 'Director of Sales', 'Director of Marketing', 
                        'Director of Operations', 'Product Director'],
            'manager': ['Engineering Manager', 'Sales Manager', 'Marketing Manager', 
                       'Operations Manager', 'Product Manager'],
            'senior': ['Senior Engineer', 'Senior Developer', 'Senior Analyst', 
                      'Senior Consultant', 'Senior Specialist'],
            'individual': ['Software Engineer', 'Data Analyst', 'Marketing Specialist', 
                          'Sales Representative', 'Product Specialist']
        }
        
        # Industries with typical company sizes and revenue ranges
        self.industries = {
            'Technology': {'employees': (10, 50000), 'revenue': (1000000, 50000000000)},
            'Healthcare': {'employees': (5, 10000), 'revenue': (500000, 10000000000)},
            'Finance': {'employees': (20, 100000), 'revenue': (2000000, 100000000000)},
            'Retail': {'employees': (50, 500000), 'revenue': (5000000, 500000000000)},
            'Manufacturing': {'employees': (100, 50000), 'revenue': (10000000, 50000000000)},
            'Consulting': {'employees': (5, 5000), 'revenue': (1000000, 5000000000)},
            'Education': {'employees': (10, 50000), 'revenue': (1000000, 10000000000)},
            'Media': {'employees': (5, 10000), 'revenue': (500000, 20000000000)},
            'Real Estate': {'employees': (5, 1000), 'revenue': (1000000, 5000000000)},
            'Energy': {'employees': (100, 100000), 'revenue': (50000000, 500000000000)}
        }
        
        # US cities with states and ZIP codes
        self.locations = [
            ('New York', 'NY', '10001'), ('Los Angeles', 'CA', '90001'),
            ('Chicago', 'IL', '60601'), ('Houston', 'TX', '77001'),
            ('Phoenix', 'AZ', '85001'), ('Philadelphia', 'PA', '19101'),
            ('San Antonio', 'TX', '78201'), ('San Diego', 'CA', '92101'),
            ('Dallas', 'TX', '75201'), ('San Jose', 'CA', '95101'),
            ('Austin', 'TX', '73301'), ('Jacksonville', 'FL', '32099'),
            ('Fort Worth', 'TX', '76101'), ('Columbus', 'OH', '43085'),
            ('Charlotte', 'NC', '28201'), ('San Francisco', 'CA', '94102'),
            ('Indianapolis', 'IN', '46201'), ('Seattle', 'WA', '98101'),
            ('Denver', 'CO', '80201'), ('Boston', 'MA', '02101'),
            ('Nashville', 'TN', '37201'), ('Detroit', 'MI', '48201'),
            ('Portland', 'OR', '97201'), ('Memphis', 'TN', '38101'),
            ('Louisville', 'KY', '40201'), ('Baltimore', 'MD', '21201'),
            ('Milwaukee', 'WI', '53201'), ('Albuquerque', 'NM', '87101'),
            ('Tucson', 'AZ', '85701'), ('Fresno', 'CA', '93650'),
            ('Sacramento', 'CA', '94203'), ('Mesa', 'AZ', '85201'),
            ('Kansas City', 'MO', '64101'), ('Atlanta', 'GA', '30301'),
            ('Colorado Springs', 'CO', '80903'), ('Omaha', 'NE', '68101'),
            ('Raleigh', 'NC', '27601'), ('Miami', 'FL', '33101'),
            ('Virginia Beach', 'VA', '23450'), ('Oakland', 'CA', '94601'),
            ('Minneapolis', 'MN', '55401'), ('Tulsa', 'OK', '74101'),
            ('Arlington', 'TX', '76010'), ('Tampa', 'FL', '33601'),
            ('New Orleans', 'LA', '70112'), ('Wichita', 'KS', '67202'),
            ('Cleveland', 'OH', '44101'), ('Bakersfield', 'CA', '93301'),
            ('Aurora', 'CO', '80010'), ('Anaheim', 'CA', '92801'),
            ('Honolulu', 'HI', '96801'), ('Santa Ana', 'CA', '92701'),
            ('Riverside', 'CA', '92501'), ('Corpus Christi', 'TX', '78401'),
            ('Lexington', 'KY', '40507'), ('Henderson', 'NV', '89002'),
            ('Stockton', 'CA', '95202'), ('Saint Paul', 'MN', '55101'),
            ('Cincinnati', 'OH', '45202'), ('St. Louis', 'MO', '63101'),
            ('Pittsburgh', 'PA', '15201'), ('Greensboro', 'NC', '27401'),
            ('Lincoln', 'NE', '68501'), ('Anchorage', 'AK', '99501'),
            ('Plano', 'TX', '75023'), ('Orlando', 'FL', '32801'),
            ('Irvine', 'CA', '92602'), ('Newark', 'NJ', '07102'),
            ('Durham', 'NC', '27701'), ('Chula Vista', 'CA', '91910'),
            ('Toledo', 'OH', '43604'), ('Fort Wayne', 'IN', '46802'),
            ('St. Petersburg', 'FL', '33701'), ('Laredo', 'TX', '78040'),
            ('Jersey City', 'NJ', '07302'), ('Chandler', 'AZ', '85224'),
            ('Madison', 'WI', '53703'), ('Lubbock', 'TX', '79401'),
            ('Buffalo', 'NY', '14201'), ('Winston-Salem', 'NC', '27101'),
            ('Glendale', 'AZ', '85301'), ('Scottsdale', 'AZ', '85251'),
            ('Norfolk', 'VA', '23501'), ('Las Vegas', 'NV', '89101'),
            ('Irving', 'TX', '75061'), ('Fremont', 'CA', '94536'),
            ('Garland', 'TX', '75040'), ('Richmond', 'VA', '23220'),
            ('Boise', 'ID', '83702'), ('Spokane', 'WA', '99201')
        ]
        
        # Street names for realistic addresses
        self.street_names = [
            'Main St', 'First St', 'Second St', 'Third St', 'Park Ave', 'Oak St',
            'Pine St', 'Maple St', 'Cedar St', 'Elm St', 'Washington St', 'Jefferson St',
            'Lincoln Ave', 'Madison Ave', 'Jackson St', 'Franklin St', 'Church St',
            'Spring St', 'Hill St', 'Broadway', 'Market St', 'State St', 'High St',
            'School St', 'Water St', 'North St', 'South St', 'East St', 'West St',
            'Central Ave', 'Sunset Blvd', 'River Rd', 'Lake St', 'Valley Rd'
        ]
        
    def generate_base_profiles(self, count: int) -> List[CustomerProfile]:
        """Generate base customer profiles without duplicates"""
        profiles = []
        
        for _ in range(count):
            # Select random name
            first_name = random.choice(list(self.first_names.keys()))
            last_name = random.choice(self.last_names)
            
            # Generate company and industry
            industry = random.choice(list(self.industries.keys()))
            company_base = random.choice(list(self.companies.keys()))
            company = random.choice(self.companies[company_base])
            
            # Generate title based on company size
            emp_range = self.industries[industry]['employees']
            employees = random.randint(*emp_range)
            
            if employees < 50:
                title_level = random.choices(['c_level', 'manager', 'individual'], [0.3, 0.3, 0.4])[0]
            elif employees < 500:
                title_level = random.choices(['c_level', 'vp', 'director', 'manager', 'senior', 'individual'], 
                                           [0.1, 0.15, 0.2, 0.25, 0.15, 0.15])[0]
            else:
                title_level = random.choices(['c_level', 'vp', 'director', 'manager', 'senior', 'individual'], 
                                           [0.05, 0.1, 0.15, 0.2, 0.25, 0.25])[0]
            
            title = random.choice(self.job_titles[title_level])
            
            # Generate contact info
            email_base = f"{first_name.lower()}.{last_name.lower()}"
            phone_base = f"555{random.randint(1000000, 9999999)}"
            
            # Generate address
            city, state, zip_base = random.choice(self.locations)
            street_num = random.randint(1, 9999)
            street_name = random.choice(self.street_names)
            address = f"{street_num} {street_name}"
            zip_code = f"{zip_base[:3]}{random.randint(10, 99)}"
            
            # Generate company financials
            rev_range = self.industries[industry]['revenue']
            revenue = random.randint(*rev_range)
            
            # Generate creation date (within last 5 years)
            days_ago = random.randint(0, 1825)  # 5 years
            created_date = datetime.now() - timedelta(days=days_ago)
            
            profile = CustomerProfile(
                first_name=first_name,
                last_name=last_name,
                email_base=email_base,
                phone_base=phone_base,
                company=company,
                title=title,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                industry=industry,
                revenue=revenue,
                employees=employees,
                created_date=created_date
            )
            
            profiles.append(profile)
            
        return profiles
    
    def create_duplicate_variations(self, profile: CustomerProfile, num_variations: int = 2) -> List[Dict[str, Any]]:
        """Create realistic duplicate variations of a profile"""
        variations = []
        
        # Always include the original
        original = self.profile_to_record(profile, variation_type="original")
        variations.append(original)
        
        for i in range(num_variations):
            # Choose variation types for this duplicate
            variation_types = random.choices([
                'nickname', 'typo', 'email_format', 'phone_format', 'company_format',
                'title_variation', 'address_format', 'middle_initial', 'professional_title'
            ], k=random.randint(1, 3))
            
            varied_record = self.apply_variations(profile, variation_types, i + 1)
            variations.append(varied_record)
        
        return variations
    
    def apply_variations(self, profile: CustomerProfile, variation_types: List[str], variation_num: int) -> Dict[str, Any]:
        """Apply specific variations to create a realistic duplicate"""
        record = self.profile_to_record(profile, variation_type="duplicate")
        
        for variation in variation_types:
            if variation == 'nickname' and profile.first_name in self.first_names:
                nicknames = self.first_names[profile.first_name]
                if nicknames:
                    record['first_name'] = random.choice(nicknames)
            
            elif variation == 'typo':
                # Introduce realistic typos
                typo_field = random.choice(['first_name', 'last_name', 'company'])
                original_value = record[typo_field]
                if len(original_value) > 3:
                    # Common typo patterns
                    typo_patterns = [
                        lambda x: x.replace('o', '0') if 'o' in x else x,  # o -> 0
                        lambda x: x.replace('i', '1') if 'i' in x else x,  # i -> 1
                        lambda x: x.replace('e', 'a') if 'e' in x else x,  # e -> a
                        lambda x: x[:-1] + x[-2] + x[-1] if len(x) > 2 else x,  # transpose last two
                        lambda x: x + x[-1] if len(x) > 2 else x,  # duplicate last char
                        lambda x: x[:-1] if len(x) > 3 else x,  # drop last char
                    ]
                    pattern = random.choice(typo_patterns)
                    record[typo_field] = pattern(original_value)
            
            elif variation == 'email_format':
                # Different email formats
                base_name = profile.email_base
                company_domain = profile.company.lower().replace(' ', '').replace('.', '').replace(',', '')[:10]
                formats = [
                    f"{base_name}@{company_domain}.com",
                    f"{profile.first_name.lower()}{profile.last_name.lower()}@{company_domain}.com",
                    f"{profile.first_name[0].lower()}.{profile.last_name.lower()}@{company_domain}.com",
                    f"{profile.first_name.lower()}{profile.last_name[0].lower()}@{company_domain}.com",
                    f"{base_name}@gmail.com",
                    f"{base_name}@outlook.com"
                ]
                record['email'] = random.choice(formats)
            
            elif variation == 'phone_format':
                # Different phone formats
                base_phone = profile.phone_base
                formats = [
                    f"({base_phone[:3]}) {base_phone[3:6]}-{base_phone[6:]}",
                    f"{base_phone[:3]}-{base_phone[3:6]}-{base_phone[6:]}",
                    f"{base_phone[:3]}.{base_phone[3:6]}.{base_phone[6:]}",
                    f"+1{base_phone}",
                    f"1-{base_phone[:3]}-{base_phone[3:6]}-{base_phone[6:]}"
                ]
                record['phone'] = random.choice(formats)
            
            elif variation == 'company_format':
                # Use different company name variation
                company_base = None
                for base, variations in self.companies.items():
                    if profile.company in variations or profile.company == base:
                        company_base = base
                        break
                
                if company_base:
                    available_variations = [v for v in self.companies[company_base] if v != profile.company]
                    if available_variations:
                        record['company'] = random.choice(available_variations)
            
            elif variation == 'title_variation':
                # Slight title variations
                title_variations = {
                    'CEO': ['Chief Executive Officer', 'Chief Executive', 'President & CEO'],
                    'CTO': ['Chief Technology Officer', 'Chief Technical Officer'],
                    'CFO': ['Chief Financial Officer', 'Chief Finance Officer'],
                    'VP Engineering': ['Vice President Engineering', 'VP of Engineering', 'Engineering VP'],
                    'Director of Engineering': ['Engineering Director', 'Director, Engineering'],
                    'Software Engineer': ['Software Developer', 'Engineer', 'Developer'],
                    'Product Manager': ['PM', 'Product Lead', 'Product Owner']
                }
                
                if record['title'] in title_variations:
                    record['title'] = random.choice(title_variations[record['title']])
            
            elif variation == 'address_format':
                # Address variations
                street_variations = {
                    'St': ['Street', 'St.'],
                    'Ave': ['Avenue', 'Ave.'],
                    'Rd': ['Road', 'Rd.'],
                    'Blvd': ['Boulevard', 'Blvd.']
                }
                
                for abbrev, full_forms in street_variations.items():
                    if abbrev in record['address']:
                        record['address'] = record['address'].replace(abbrev, random.choice(full_forms))
                        break
            
            elif variation == 'middle_initial':
                # Add middle initial
                middle_initials = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                initial = random.choice(middle_initials)
                record['first_name'] = f"{record['first_name']} {initial}."
            
            elif variation == 'professional_title':
                # Add professional titles
                professional_prefixes = ['Dr.', 'Prof.', 'Mr.', 'Ms.']
                if random.random() < 0.3:  # 30% chance
                    prefix = random.choice(professional_prefixes)
                    record['first_name'] = f"{prefix} {record['first_name']}"
        
        # Ensure some fields change to make it a realistic duplicate
        if variation_num > 0:
            # Slightly different creation date (within 30 days)
            date_offset = random.randint(-30, 30)
            record['created_date'] = (profile.created_date + timedelta(days=date_offset)).isoformat()
        
        return record
    
    def profile_to_record(self, profile: CustomerProfile, variation_type: str = "original") -> Dict[str, Any]:
        """Convert profile to customer record format"""
        company_domain = profile.company.lower().replace(' ', '').replace('.', '').replace(',', '')[:10]
        
        return {
            'id': str(uuid.uuid4()),
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'email': f"{profile.email_base}@{company_domain}.com",
            'phone': f"({profile.phone_base[:3]}) {profile.phone_base[3:6]}-{profile.phone_base[6:]}",
            'company': profile.company,
            'title': profile.title,
            'address': profile.address,
            'city': profile.city,
            'state': profile.state,
            'zip_code': profile.zip_code,
            'industry': profile.industry,
            'revenue': profile.revenue,
            'employees': profile.employees,
            'created_date': profile.created_date.isoformat(),
            'source_system': random.choice(['CRM', 'Marketing', 'Sales', 'Support', 'Website']),
            'data_quality_score': random.randint(60, 100),
            'variation_type': variation_type,
            'last_updated': datetime.now().isoformat()
        }
    
    def generate_dataset(self, total_records: int = 10000, duplicate_rate: float = 0.2) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Generate complete dataset with duplicates"""
        
        # Calculate how many unique profiles we need
        estimated_duplicates_per_profile = 2.5  # Average variations per duplicate profile
        unique_profiles_needed = int(total_records / (1 + duplicate_rate * estimated_duplicates_per_profile))
        
        print(f"Generating {unique_profiles_needed} unique profiles...")
        base_profiles = self.generate_base_profiles(unique_profiles_needed)
        
        all_records = []
        duplicate_groups = []
        
        # Determine which profiles will have duplicates
        profiles_with_duplicates = random.sample(base_profiles, 
                                                int(len(base_profiles) * duplicate_rate))
        
        print(f"Creating variations for {len(profiles_with_duplicates)} profiles...")
        
        for i, profile in enumerate(base_profiles):
            if profile in profiles_with_duplicates:
                # Create duplicate variations
                num_variations = random.choices([1, 2, 3], weights=[0.4, 0.4, 0.2])[0]
                variations = self.create_duplicate_variations(profile, num_variations)
                all_records.extend(variations)
                
                # Track duplicate group
                duplicate_groups.append({
                    'group_id': len(duplicate_groups),
                    'profile_key': f"{profile.first_name}_{profile.last_name}_{profile.company}",
                    'record_ids': [record['id'] for record in variations],
                    'variation_count': len(variations)
                })
            else:
                # Single record, no duplicates
                record = self.profile_to_record(profile)
                all_records.append(record)
            
            if (i + 1) % 1000 == 0:
                print(f"Processed {i + 1}/{len(base_profiles)} profiles...")
        
        # Shuffle records to simulate real-world data distribution
        random.shuffle(all_records)
        
        # Generate metadata
        metadata = {
            'generation_date': datetime.now().isoformat(),
            'total_records': len(all_records),
            'unique_entities': len(base_profiles),
            'duplicate_groups': len(duplicate_groups),
            'duplicate_rate': len([r for r in all_records if r['variation_type'] == 'duplicate']) / len(all_records),
            'duplicate_group_info': duplicate_groups,
            'industries': list(self.industries.keys()),
            'data_sources': ['CRM', 'Marketing', 'Sales', 'Support', 'Website'],
            'quality_metrics': {
                'avg_data_quality_score': sum(r['data_quality_score'] for r in all_records) / len(all_records),
                'records_by_source': {source: len([r for r in all_records if r['source_system'] == source]) 
                                    for source in ['CRM', 'Marketing', 'Sales', 'Support', 'Website']},
                'records_by_industry': {industry: len([r for r in all_records if r['industry'] == industry]) 
                                      for industry in self.industries.keys()}
            }
        }
        
        print(f"\nDataset generation complete!")
        print(f"Total records: {len(all_records)}")
        print(f"Unique entities: {len(base_profiles)}")
        print(f"Duplicate groups: {len(duplicate_groups)}")
        print(f"Actual duplicate rate: {metadata['duplicate_rate']:.1%}")
        
        return all_records, metadata


def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description='Generate realistic customer data for entity resolution demo')
    parser.add_argument('--records', type=int, default=10000, help='Number of total records to generate')
    parser.add_argument('--duplicate-rate', type=float, default=0.2, help='Percentage of records that are duplicates')
    parser.add_argument('--output-dir', type=str, default='data', help='Output directory for generated files')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducible results')
    
    args = parser.parse_args()
    
    # Create output directory
    import os
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Generate data
    generator = DataGenerator(seed=args.seed)
    records, metadata = generator.generate_dataset(args.records, args.duplicate_rate)
    
    # Save records as JSON
    records_file = os.path.join(args.output_dir, 'demo_customers.json')
    with open(records_file, 'w') as f:
        json.dump(records, f, indent=2)
    
    # Save metadata
    metadata_file = os.path.join(args.output_dir, 'demo_metadata.json')
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Save as CSV for easy viewing
    csv_file = os.path.join(args.output_dir, 'demo_customers.csv')
    with open(csv_file, 'w', newline='') as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
    
    # Save duplicate groups analysis
    groups_file = os.path.join(args.output_dir, 'duplicate_groups.json')
    with open(groups_file, 'w') as f:
        json.dump(metadata['duplicate_group_info'], f, indent=2)
    
    print(f"\nFiles generated:")
    print(f"  Records: {records_file}")
    print(f"  Metadata: {metadata_file}")
    print(f"  CSV: {csv_file}")
    print(f"  Duplicate groups: {groups_file}")


if __name__ == "__main__":
    main()
