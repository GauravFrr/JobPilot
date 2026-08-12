import os
import sys

# Add workers directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tailoring.render_pdf import render_resume_to_pdf

def test_pdf_rendering():
    print("Running PDF rendering tests...")
    
    mock_tailored_json = {
        "name": "Gaurav Bomra",
        "email": "gauravdevxd@gmail.com",
        "phone": "+919350661422",
        "website": "gauravxd.dev",
        "linkedin": "https://www.linkedin.com/in/gauravstack/",
        "github": "github.com/GauravFrr",
        "skills": {
            "languages": ["Python", "TypeScript", "JavaScript"],
            "frameworks": ["FastAPI", "Next.js", "NestJS"]
        },
        "projects": [
            {
                "name": "Retryv",
                "summary": "RAG pipeline evaluation and retrieval system",
                "bullets": [
                    "Improved retrieval recall from 23% to 84% using hybrid BM25 + ChromaDB + RRF + cross-encoder reranker",
                    "Built FastAPI backend and Streamlit interface, tested against FastAPI's own documentation corpus"
                ]
            }
        ],
        "education": [
            {
                "degree": "BCA",
                "institution": "S.L.N. Hindu College",
                "start": "August 2026",
                "status": "upcoming"
            }
        ],
        "certifications": ["Claude 101"]
    }
    
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_resume.pdf"))
    
    # Clean up old test PDF if exists
    if os.path.exists(output_path):
        os.remove(output_path)
        
    try:
        render_resume_to_pdf(mock_tailored_json, output_path)
        assert os.path.exists(output_path) == True
        assert os.path.getsize(output_path) > 1000 # should be non-empty PDF
        print(f"PDF rendering test passed! PDF size: {os.path.getsize(output_path)} bytes.")
    finally:
        # Clean up test file
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == "__main__":
    test_pdf_rendering()
