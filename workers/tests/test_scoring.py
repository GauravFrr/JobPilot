import os
import sys

# Add workers directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from matching.score import check_title_blocklist, cosine_similarity

def test_scoring_logic():
    print("Running scoring logic tests...")
    
    # 1. Check title blocklist
    assert check_title_blocklist("Lead Software Engineer") == True
    assert check_title_blocklist("Staff Backend Engineer") == True
    assert check_title_blocklist("Director of AI") == True
    assert check_title_blocklist("Backend Engineer") == False
    assert check_title_blocklist("Full-stack Engineer") == False
    
    # 2. Check cosine similarity calculation
    # Orthogonal vectors (should be 0 similarity)
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == 0.0
    
    # Identical vectors (should be 1 similarity)
    assert abs(cosine_similarity(v1, v1) - 1.0) < 1e-6
    
    # Opposite vectors (should be -1 similarity)
    v3 = [-1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v1, v3) - (-1.0)) < 1e-6
    
    print("Scoring logic tests passed!")

if __name__ == "__main__":
    test_scoring_logic()
