import os
import sys
import asyncio

# Add workers directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from contacts.find_contacts import (
    get_role_keyword,
    extract_domain_from_url,
    verify_evidence_snippet,
    get_role_keyword
)

def test_contact_finder_helpers():
    print("Running contact finder helper unit tests...")
    
    # 1. Test get_role_keyword
    assert get_role_keyword("Software Engineer II") == "Engineering"
    assert get_role_keyword("Director of Engineering") == "Engineering"
    assert get_role_keyword("Lead Product Manager") == "Product"
    assert get_role_keyword("Account Executive") == "Sales"
    assert get_role_keyword("UX Designer") == "Design"
    assert get_role_keyword("Talent Specialist") == "Talent"
    
    # 2. Test extract_domain_from_url
    assert extract_domain_from_url("https://jobs.lever.co/acme/123", "Acme") == "acme.com"
    assert extract_domain_from_url("https://boards.greenhouse.io/acme-corp/jobs/456", "Acme Corp") == "acme-corp.com"
    assert extract_domain_from_url("https://www.google.com/careers", "Google") == "google.com"
    assert extract_domain_from_url("", "Acme Inc") == "acme.com"
    
    # 3. Test verify_evidence_snippet
    assert verify_evidence_snippet("Jane Doe", "Jane Doe - Technical Recruiter at Acme Corp") == True
    assert verify_evidence_snippet("Jane Doe", "Technical Recruiter J. Doe at Acme Corp") == True
    assert verify_evidence_snippet("Jane Doe", "Recruiting Manager at Acme Corp") == False
    
    print("Contact finder helper unit tests passed successfully!")

if __name__ == "__main__":
    test_contact_finder_helpers()
