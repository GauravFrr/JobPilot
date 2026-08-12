import os
import sys

# Add workers directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from discovery.dedup import get_title_similarity

def test_title_similarity():
    print("Running title similarity tests...")
    
    # Perfect match
    assert get_title_similarity("Backend Engineer", "Backend Engineer") == 1.0
    
    # Case insensitivity
    assert get_title_similarity("backend engineer", "Backend Engineer") == 1.0
    
    # High similarity (>85%)
    assert get_title_similarity("Backend Engineer", "Backend Engineer (Remote)") >= 0.85
    assert get_title_similarity("AI Software Engineer", "AI Engineer") >= 0.70
    
    # Low similarity (<85%)
    assert get_title_similarity("Backend Engineer", "Frontend Engineer") < 0.85
    assert get_title_similarity("Python Developer", "React Developer") < 0.75
    
    print("Title similarity tests passed!")

if __name__ == "__main__":
    test_title_similarity()
