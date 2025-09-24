#!/usr/bin/env python3
"""
Industry-Specific Demo Scenarios for Entity Resolution

Creates tailored demonstrations for different industry verticals,
highlighting specific use cases and value propositions.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from demo.scripts.data_generator import DataGenerator


class IndustryScenarioGenerator:
    """Generate industry-specific entity resolution scenarios"""
    
    def __init__(self):
        self.base_generator = DataGenerator()
        
    def generate_b2b_sales_scenario(self, records_count: int = 5000) -> Dict[str, Any]:
        """B2B Sales: Lead deduplication and account management scenario"""
        
        scenario = {
            'industry': 'B2B Sales',
            'use_case': 'Lead Deduplication & Account Management',
            'business_challenges': [
                'Duplicate leads wasting sales time',
                'Fragmented account view across systems',
                'Poor lead scoring due to incomplete data',
                'Marketing and sales misalignment'
            ],
            'data_characteristics': {
                'lead_sources': ['Website', 'Trade Shows', 'Cold Email', 'Referrals', 'LinkedIn'],
                'duplicate_patterns': [
                    'Same person, different job titles',
                    'Personal vs business email addresses',
                    'Company name variations (Inc, Corp, LLC)',
                    'Different phone number formats'
                ],
                'quality_issues': [
                    'Missing company information',
                    'Inconsistent job titles',
                    'Outdated contact information',
                    'Duplicate entries from multiple campaigns'
                ]
            },
            'roi_drivers': {
                'sales_efficiency': 'Reduce time spent on duplicate leads by 40%',
                'conversion_rates': 'Improve conversion by 25% with unified view',
                'pipeline_accuracy': 'Increase forecast accuracy by 30%',
                'customer_experience': 'Eliminate duplicate outreach'
            }
        }
        
        # Generate B2B-focused data
        records = self._generate_b2b_data(records_count)
        
        scenario['demo_data'] = {
            'records': records,
            'metadata': {
                'total_records': len(records),
                'estimated_duplicates': int(len(records) * 0.25),  # Higher duplicate rate for B2B
                'data_sources': scenario['data_characteristics']['lead_sources']
            }
        }
        
        scenario['demo_script'] = self._create_b2b_demo_script()
        
        return scenario
    
    def generate_ecommerce_scenario(self, records_count: int = 8000) -> Dict[str, Any]:
        """E-commerce: Customer experience and marketing efficiency"""
        
        scenario = {
            'industry': 'E-commerce',
            'use_case': 'Customer 360 & Marketing Personalization',
            'business_challenges': [
                'Customers creating multiple accounts',
                'Cart abandonment due to poor experience',
                'Ineffective email marketing campaigns',
                'Fraud detection challenges'
            ],
            'data_characteristics': {
                'data_sources': ['Website', 'Mobile App', 'Email', 'Social Media', 'Customer Service'],
                'duplicate_patterns': [
                    'Multiple email addresses per customer',
                    'Guest checkout vs registered accounts',
                    'Different shipping addresses',
                    'Mobile vs desktop registrations'
                ],
                'quality_issues': [
                    'Inconsistent name formats',
                    'Multiple phone numbers',
                    'Address variations',
                    'Email typos and variations'
                ]
            },
            'roi_drivers': {
                'marketing_efficiency': 'Reduce duplicate email sends by 30%',
                'customer_ltv': 'Increase lifetime value by 20% with personalization',
                'fraud_prevention': 'Detect 95% of fraudulent account patterns',
                'operational_efficiency': 'Reduce customer service lookup time by 60%'
            }
        }
        
        records = self._generate_ecommerce_data(records_count)
        
        scenario['demo_data'] = {
            'records': records,
            'metadata': {
                'total_records': len(records),
                'estimated_duplicates': int(len(records) * 0.18),
                'data_sources': scenario['data_characteristics']['data_sources']
            }
        }
        
        scenario['demo_script'] = self._create_ecommerce_demo_script()
        
        return scenario
    
    def generate_healthcare_scenario(self, records_count: int = 3000) -> Dict[str, Any]:
        """Healthcare: Patient matching and care coordination"""
        
        scenario = {
            'industry': 'Healthcare',
            'use_case': 'Patient Matching & Care Coordination',
            'business_challenges': [
                'Patient safety risks from mismatched records',
                'Duplicate medical records causing confusion',
                'Insurance claim processing delays',
                'Care coordination across providers'
            ],
            'data_characteristics': {
                'data_sources': ['EMR', 'Registration', 'Insurance', 'Lab Systems', 'Pharmacy'],
                'duplicate_patterns': [
                    'Name changes (marriage, divorce)',
                    'Insurance changes',
                    'Address moves',
                    'Emergency vs scheduled visits'
                ],
                'quality_issues': [
                    'Incomplete demographic information',
                    'Date of birth discrepancies',
                    'Social security number variations',
                    'Multiple MRN assignments'
                ]
            },
            'roi_drivers': {
                'patient_safety': 'Reduce medical errors by 40%',
                'operational_efficiency': 'Decrease registration time by 50%',
                'compliance': 'Improve audit compliance by 90%',
                'cost_reduction': 'Reduce duplicate testing by 25%'
            }
        }
        
        records = self._generate_healthcare_data(records_count)
        
        scenario['demo_data'] = {
            'records': records,
            'metadata': {
                'total_records': len(records),
                'estimated_duplicates': int(len(records) * 0.15),  # Lower but high-impact
                'data_sources': scenario['data_characteristics']['data_sources']
            }
        }
        
        scenario['demo_script'] = self._create_healthcare_demo_script()
        
        return scenario
    
    def generate_financial_scenario(self, records_count: int = 6000) -> Dict[str, Any]:
        """Financial Services: KYC, fraud detection, and compliance"""
        
        scenario = {
            'industry': 'Financial Services',
            'use_case': 'KYC, Fraud Detection & Regulatory Compliance',
            'business_challenges': [
                'KYC compliance across multiple systems',
                'Fraud detection and prevention',
                'Regulatory reporting accuracy',
                'Customer onboarding efficiency'
            ],
            'data_characteristics': {
                'data_sources': ['CRM', 'Core Banking', 'KYC Systems', 'Trading Platforms', 'Mobile Banking'],
                'duplicate_patterns': [
                    'Multiple account types per customer',
                    'Joint vs individual accounts',
                    'Business vs personal relationships',
                    'Historical vs current information'
                ],
                'quality_issues': [
                    'Address standardization challenges',
                    'Name format inconsistencies',
                    'Date format variations',
                    'Multiple identification numbers'
                ]
            },
            'roi_drivers': {
                'compliance_efficiency': 'Reduce KYC processing time by 60%',
                'fraud_detection': 'Improve fraud detection accuracy by 45%',
                'regulatory_reporting': 'Achieve 99.9% reporting accuracy',
                'customer_experience': 'Reduce onboarding time by 70%'
            }
        }
        
        records = self._generate_financial_data(records_count)
        
        scenario['demo_data'] = {
            'records': records,
            'metadata': {
                'total_records': len(records),
                'estimated_duplicates': int(len(records) * 0.22),
                'data_sources': scenario['data_characteristics']['data_sources']
            }
        }
        
        scenario['demo_script'] = self._create_financial_demo_script()
        
        return scenario
    
    def _generate_b2b_data(self, count: int) -> List[Dict[str, Any]]:
        """Generate B2B-specific customer data"""
        
        # B2B-specific company names and industries
        b2b_companies = {
            'Salesforce': ['Salesforce.com', 'Salesforce Inc', 'SFDC'],
            'HubSpot': ['HubSpot Inc', 'HubSpot Corp', 'HubSpot'],
            'Marketo': ['Marketo Inc', 'Adobe Marketo', 'Marketo Corp'],
            'Pardot': ['Pardot LLC', 'Salesforce Pardot', 'Pardot Inc'],
            'ZoomInfo': ['ZoomInfo Inc', 'ZoomInfo Corp', 'ZI Corp'],
            'Outreach': ['Outreach.io', 'Outreach Inc', 'Outreach Corp'],
            'Gong': ['Gong.io', 'Gong Inc', 'Gong Corp'],
            'Drift': ['Drift Inc', 'Drift Corp', 'Drift.com']
        }
        
        lead_sources = ['Website', 'Trade Shows', 'Cold Email', 'Referrals', 'LinkedIn']
        job_functions = ['Sales', 'Marketing', 'IT', 'Operations', 'Finance', 'HR']
        
        records = []
        base_profiles = self.base_generator.generate_base_profiles(int(count * 0.8))
        
        for profile in base_profiles:
            # Create multiple lead entries for some profiles (simulating B2B lead generation)
            num_leads = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
            
            for i in range(num_leads):
                record = self.base_generator.profile_to_record(profile)
                
                # Add B2B-specific fields
                record.update({
                    'lead_source': random.choice(lead_sources),
                    'job_function': random.choice(job_functions),
                    'company_size': profile.employees,
                    'annual_revenue': profile.revenue,
                    'lead_score': random.randint(1, 100),
                    'campaign_id': f"CAMP_{random.randint(1000, 9999)}",
                    'utm_source': random.choice(['google', 'linkedin', 'email', 'direct']),
                    'qualification_status': random.choice(['MQL', 'SQL', 'Opportunity', 'Customer']),
                    'lead_owner': f"sales_rep_{random.randint(1, 20)}"
                })
                
                # Apply B2B-specific variations for duplicates
                if i > 0:
                    # Different email formats for business contacts
                    email_variations = [
                        f"{profile.first_name.lower()}@{record['company'].lower().replace(' ', '').replace('.', '')[:10]}.com",
                        f"{profile.first_name[0].lower()}{profile.last_name.lower()}@{record['company'].lower().replace(' ', '').replace('.', '')[:10]}.com",
                        f"{profile.first_name.lower()}.{profile.last_name.lower()}@gmail.com"  # Personal email
                    ]
                    record['email'] = random.choice(email_variations)
                    
                    # Different lead sources
                    record['lead_source'] = random.choice(lead_sources)
                    record['campaign_id'] = f"CAMP_{random.randint(1000, 9999)}"
                    
                    # Title variations
                    if 'Manager' in record['title']:
                        record['title'] = record['title'].replace('Manager', random.choice(['Mgr', 'Lead', 'Head of']))
                
                records.append(record)
        
        return records
    
    def _generate_ecommerce_data(self, count: int) -> List[Dict[str, Any]]:
        """Generate e-commerce-specific customer data"""
        
        data_sources = ['Website', 'Mobile App', 'Email', 'Social Media', 'Customer Service']
        purchase_categories = ['Electronics', 'Clothing', 'Home & Garden', 'Books', 'Sports', 'Beauty']
        
        records = []
        base_profiles = self.base_generator.generate_base_profiles(int(count * 0.85))
        
        for profile in base_profiles:
            # Create multiple accounts for some customers (guest vs registered)
            num_accounts = random.choices([1, 2, 3], weights=[0.7, 0.25, 0.05])[0]
            
            for i in range(num_accounts):
                record = self.base_generator.profile_to_record(profile)
                
                # Add e-commerce specific fields
                record.update({
                    'customer_type': random.choice(['Guest', 'Registered', 'Premium']),
                    'registration_source': random.choice(data_sources),
                    'total_orders': random.randint(0, 50),
                    'total_spent': random.randint(0, 5000),
                    'favorite_category': random.choice(purchase_categories),
                    'last_login': (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
                    'marketing_opt_in': random.choice([True, False]),
                    'mobile_user': random.choice([True, False]),
                    'loyalty_points': random.randint(0, 10000)
                })
                
                # Apply e-commerce variations for duplicates
                if i > 0:
                    # Different account types
                    if i == 1 and record['customer_type'] == 'Registered':
                        record['customer_type'] = 'Guest'
                        record['email'] = f"guest_{random.randint(10000, 99999)}@tempmail.com"
                    
                    # Mobile vs desktop variations
                    if record['mobile_user']:
                        record['phone'] = f"+1{profile.phone_base}"
                    
                    # Different shipping addresses
                    if random.random() < 0.3:
                        record['address'] = f"{random.randint(1, 999)} {random.choice(['Oak St', 'Pine Ave', 'Main Rd'])}"
                
                records.append(record)
        
        return records
    
    def _generate_healthcare_data(self, count: int) -> List[Dict[str, Any]]:
        """Generate healthcare-specific patient data"""
        
        data_sources = ['EMR', 'Registration', 'Insurance', 'Lab Systems', 'Pharmacy']
        insurance_providers = ['Aetna', 'Blue Cross', 'Cigna', 'UnitedHealth', 'Humana']
        
        records = []
        base_profiles = self.base_generator.generate_base_profiles(count)
        
        for profile in base_profiles:
            record = self.base_generator.profile_to_record(profile)
            
            # Add healthcare-specific fields
            record.update({
                'patient_id': f"PAT_{random.randint(100000, 999999)}",
                'mrn': f"MRN_{random.randint(1000000, 9999999)}",
                'date_of_birth': (datetime.now() - timedelta(days=random.randint(365*18, 365*80))).strftime('%Y-%m-%d'),
                'ssn': f"XXX-XX-{random.randint(1000, 9999)}",
                'insurance_provider': random.choice(insurance_providers),
                'insurance_id': f"INS_{random.randint(100000000, 999999999)}",
                'emergency_contact': f"{random.choice(list(self.base_generator.first_names.keys()))} {random.choice(self.base_generator.last_names)}",
                'primary_physician': f"Dr. {random.choice(self.base_generator.last_names)}",
                'last_visit': (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
                'allergies': random.choice(['None', 'Penicillin', 'Shellfish', 'Nuts', 'Multiple']),
                'data_source': random.choice(data_sources)
            })
            
            records.append(record)
        
        return records
    
    def _generate_financial_data(self, count: int) -> List[Dict[str, Any]]:
        """Generate financial services customer data"""
        
        data_sources = ['CRM', 'Core Banking', 'KYC Systems', 'Trading Platforms', 'Mobile Banking']
        account_types = ['Checking', 'Savings', 'Credit Card', 'Mortgage', 'Investment']
        risk_levels = ['Low', 'Medium', 'High']
        
        records = []
        base_profiles = self.base_generator.generate_base_profiles(int(count * 0.8))
        
        for profile in base_profiles:
            # Create multiple accounts per customer
            num_accounts = random.choices([1, 2, 3, 4], weights=[0.4, 0.3, 0.2, 0.1])[0]
            
            for i in range(num_accounts):
                record = self.base_generator.profile_to_record(profile)
                
                # Add financial services fields
                record.update({
                    'customer_id': f"CUST_{random.randint(1000000, 9999999)}",
                    'account_number': f"ACC_{random.randint(100000000, 999999999)}",
                    'account_type': random.choice(account_types),
                    'account_balance': random.randint(100, 100000),
                    'credit_score': random.randint(300, 850),
                    'risk_level': random.choice(risk_levels),
                    'kyc_status': random.choice(['Pending', 'Verified', 'Requires Update']),
                    'relationship_manager': f"rm_{random.randint(1, 50)}",
                    'onboarding_date': (datetime.now() - timedelta(days=random.randint(0, 1825))).isoformat(),
                    'last_transaction': (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                    'data_source': random.choice(data_sources),
                    'aml_flag': random.choice([True, False]) if random.random() < 0.05 else False
                })
                
                # Apply financial-specific variations
                if i > 0:
                    # Different account types have different data patterns
                    if record['account_type'] == 'Investment':
                        record['email'] = f"{profile.first_name.lower()}.{profile.last_name.lower()}.invest@gmail.com"
                    elif record['account_type'] == 'Mortgage':
                        # Joint accounts might have different names
                        if random.random() < 0.3:
                            record['first_name'] = f"{profile.first_name} & Spouse"
                
                records.append(record)
        
        return records
    
    def _create_b2b_demo_script(self) -> List[Dict[str, str]]:
        """Create B2B-specific demo talking points"""
        return [
            {
                "section": "Problem Statement",
                "talking_points": [
                    "Your sales team spends 40% of their time on duplicate leads",
                    "Marketing campaigns reach the same prospect multiple times",
                    "Account executives lack a unified view of prospect interactions",
                    "Lead scoring is inaccurate due to fragmented data"
                ]
            },
            {
                "section": "Solution Demonstration",
                "talking_points": [
                    "Watch as we identify prospects across multiple lead sources",
                    "See how John Smith from Salesforce.com matches Jon Smith from SFDC",
                    "Observe the creation of a unified prospect profile",
                    "Note the improved lead scoring with complete data"
                ]
            },
            {
                "section": "Business Impact",
                "talking_points": [
                    "Sales efficiency increases by 40% with eliminated duplicates",
                    "Conversion rates improve 25% with unified customer view",
                    "Marketing spend optimization saves $200K annually",
                    "Customer experience improves with consistent messaging"
                ]
            }
        ]
    
    def _create_ecommerce_demo_script(self) -> List[Dict[str, str]]:
        """Create e-commerce-specific demo talking points"""
        return [
            {
                "section": "Problem Statement",
                "talking_points": [
                    "Customers create multiple accounts causing fragmented experience",
                    "Marketing campaigns send duplicate emails to same customer",
                    "Customer service can't find complete purchase history",
                    "Fraud detection is hindered by incomplete customer view"
                ]
            },
            {
                "section": "Solution Demonstration",
                "talking_points": [
                    "See how guest checkout links to registered account",
                    "Watch mobile and desktop profiles merge seamlessly",
                    "Observe how different email addresses connect to one customer",
                    "Note the creation of a complete customer journey"
                ]
            },
            {
                "section": "Business Impact",
                "talking_points": [
                    "Customer lifetime value increases 20% with personalization",
                    "Email marketing efficiency improves 30% with deduplication",
                    "Customer service resolution time reduces by 60%",
                    "Fraud detection accuracy increases to 95%"
                ]
            }
        ]
    
    def _create_healthcare_demo_script(self) -> List[Dict[str, str]]:
        """Create healthcare-specific demo talking points"""
        return [
            {
                "section": "Problem Statement",
                "talking_points": [
                    "Duplicate patient records create safety risks",
                    "Care coordination is difficult across systems",
                    "Insurance claim processing is delayed",
                    "Patient registration takes too long"
                ]
            },
            {
                "section": "Solution Demonstration",
                "talking_points": [
                    "Watch as we safely match patients across systems",
                    "See how name changes and moves are handled",
                    "Observe the creation of a master patient index",
                    "Note the preservation of complete medical history"
                ]
            },
            {
                "section": "Business Impact",
                "talking_points": [
                    "Medical errors reduce by 40% with accurate matching",
                    "Patient registration time decreases 50%",
                    "Duplicate testing reduces by 25% saving costs",
                    "Audit compliance improves to 90%"
                ]
            }
        ]
    
    def _create_financial_demo_script(self) -> List[Dict[str, str]]:
        """Create financial services demo talking points"""
        return [
            {
                "section": "Problem Statement",
                "talking_points": [
                    "KYC processes are inefficient across multiple systems",
                    "Fraud detection is hampered by fragmented data",
                    "Regulatory reporting lacks accuracy",
                    "Customer onboarding takes too long"
                ]
            },
            {
                "section": "Solution Demonstration",
                "talking_points": [
                    "See how customer data unifies across all banking systems",
                    "Watch as we detect suspicious relationship patterns",
                    "Observe the creation of a golden customer record",
                    "Note the automated compliance validation"
                ]
            },
            {
                "section": "Business Impact",
                "talking_points": [
                    "KYC processing time reduces by 60%",
                    "Fraud detection accuracy improves 45%",
                    "Regulatory reporting achieves 99.9% accuracy",
                    "Customer onboarding time reduces by 70%"
                ]
            }
        ]


def main():
    """Generate all industry scenarios"""
    
    generator = IndustryScenarioGenerator()
    
    scenarios = {
        'b2b_sales': generator.generate_b2b_sales_scenario(),
        'ecommerce': generator.generate_ecommerce_scenario(),
        'healthcare': generator.generate_healthcare_scenario(),
        'financial': generator.generate_financial_scenario()
    }
    
    # Create output directory
    output_dir = Path(__file__).parent.parent / "data" / "industry_scenarios"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save each scenario
    for industry, scenario in scenarios.items():
        scenario_file = output_dir / f"{industry}_scenario.json"
        
        with open(scenario_file, 'w') as f:
            json.dump(scenario, f, indent=2)
        
        print(f"Generated {industry} scenario: {scenario_file}")
        print(f"  Records: {len(scenario['demo_data']['records'])}")
        print(f"  Use case: {scenario['use_case']}")
        print(f"  Estimated duplicates: {scenario['demo_data']['metadata']['estimated_duplicates']}")
        print()
    
    # Create summary
    summary = {
        'generation_date': datetime.now().isoformat(),
        'scenarios_generated': list(scenarios.keys()),
        'total_records': sum(len(s['demo_data']['records']) for s in scenarios.values()),
        'use_cases': [s['use_case'] for s in scenarios.values()]
    }
    
    summary_file = output_dir / "scenarios_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Industry scenarios summary: {summary_file}")


if __name__ == "__main__":
    main()
