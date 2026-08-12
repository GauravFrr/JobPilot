import os
import logging
import json
from pathlib import Path

logger = logging.getLogger("workers.tailoring.render_pdf")

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"WeasyPrint could not load system libraries: {str(e)}. Falling back to HTML output.")
    WEASYPRINT_AVAILABLE = False

# Load Liberation Serif from fonts shipped with this repo (or system fallback)
FONTS_DIR = Path(__file__).parent.parent.parent / "api" / "fonts"

def _build_html(data: dict) -> str:
    """Builds the full HTML document matching Gaurav's Jake-Ryan-style resume layout."""

    name = data.get("name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")
    linkedin = data.get("linkedin", "").replace("https://", "").replace("http://", "")
    github = data.get("github", "").replace("https://", "")
    website = data.get("website", "").replace("https://", "").replace("http://", "")
    location = data.get("location", "Bhiwani, Haryana, India | Open to Remote Worldwide | Immediate Joiner")

    # Contact bar with hyperlinks
    contact_parts = []
    if phone: 
        contact_parts.append(phone)
    if email: 
        contact_parts.append(f'<a href="mailto:{email}" class="link">{email}</a>')
    if linkedin: 
        contact_parts.append(f'<a href="https://{linkedin}" class="link">{linkedin}</a>')
    if github: 
        contact_parts.append(f'<a href="https://{github}" class="link">{github}</a>')
    if website: 
        contact_parts.append(f'<a href="https://{website}" class="link">{website}</a>')
    contact_line = " | ".join(contact_parts)

    # Skills section
    skills = data.get("skills", {})
    skills_rows = ""
    skill_order = ["languages", "frameworks", "databases", "tools", "concepts"]
    for category in skill_order:
        items = skills.get(category)
        if not items:
            continue
        label = {
            "languages": "Languages",
            "frameworks": "Frameworks",
            "databases": "Databases",
            "tools": "Dev Tools",
            "concepts": "AI/LLM/Concepts"
        }.get(category, category.capitalize())
        skills_rows += f"""
        <div class="skills-row">
            <span class="skill-label">{label}:</span>
            <span class="skill-values">{", ".join(items)}</span>
        </div>
        """

    # Education section
    education = data.get("education", [])
    edu_html = ""
    for edu in education:
        degree = edu.get("degree", "")
        inst = edu.get("institution", "")
        start = edu.get("start", "")
        loc = edu.get("location", "")
        edu_html += f"""
        <div class="entry">
            <div class="entry-header">
                <span class="entry-org">{inst}</span>
                <span class="entry-date">{start}</span>
            </div>
            <div class="entry-title">{degree}{f" &ndash; {loc}" if loc else ""}</div>
        </div>
        """

    # Experience section
    experience = data.get("experience", [])
    exp_html = ""
    for exp in experience:
        role = exp.get("role", "")
        company = exp.get("company", "")
        date_str = exp.get("date", "")
        loc = exp.get("location", "")
        summary = exp.get("summary", "")
        bullets = exp.get("bullets", [])
        bullets_html = "".join(f"<li>{b}</li>" for b in bullets)
        exp_html += f"""
        <div class="entry">
            <div class="entry-header">
                <span class="entry-org">{role} &ndash; {company}</span>
                <span class="entry-date">{date_str}</span>
            </div>
            <div class="entry-subtitle">{f"{summary} &ndash; " if summary else ""}{loc}</div>
            <ul class="bullet-list">{bullets_html}</ul>
        </div>
        """

    # Projects section
    projects = data.get("projects", [])
    proj_html = ""
    for proj in projects:
        pname = proj.get("name", "")
        tech = proj.get("tech", proj.get("summary", ""))
        date_str = proj.get("date", "")
        bullets = proj.get("bullets", [])
        repo = proj.get("repo", "")
        bullets_html = "".join(f"<li>{b}</li>" for b in bullets)
        
        # Clickable Repo URL inside the bullet list
        repo_html = ""
        if repo:
            repo_url = repo if repo.startswith("http") else f"https://{repo}"
            repo_html = f'<li>Repo: <a href="{repo_url}" class="link">{repo}</a></li>'
            
        proj_html += f"""
        <div class="entry">
            <div class="entry-header">
                <span><span class="entry-org">{pname}</span><span class="entry-tech"> | {tech}</span></span>
                <span class="entry-date">{date_str}</span>
            </div>
            <ul class="bullet-list">{bullets_html}{repo_html}</ul>
        </div>
        """

    # Additional Projects
    add_projects = data.get("additional_projects", [])
    add_proj_html = ""
    if add_projects:
        items_html = ""
        for p in add_projects:
            ap_name = p.get("name", "")
            ap_tech = p.get("tech", "")
            ap_summary = p.get("summary", "")
            items_html += f'<li><strong>{ap_name}</strong> ({ap_tech}) &ndash; {ap_summary}</li>'
        add_proj_html = f"""
        <div class="section">
            <div class="section-title">ADDITIONAL PROJECTS</div>
            <div class="section-rule"></div>
            <ul class="bullet-list">{items_html}</ul>
        </div>
        """

    # Certifications
    certs = data.get("certifications", [])
    certs_html = ""
    if certs:
        items_html = "".join(f"<li>{c}</li>" for c in certs)
        certs_html = f"""
        <div class="section">
            <div class="section-title">CERTIFICATIONS</div>
            <div class="section-rule"></div>
            <ul class="bullet-list">{items_html}</ul>
        </div>
        """

    # Assemble the full page HTML
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{name} Resume</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400;1,700&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  @page {{
    size: A4;
    margin: 10mm 15mm 10mm 15mm;
  }}

  body {{
    font-family: 'Lato', 'Liberation Serif', 'Times New Roman', serif;
    font-size: 9.5pt;
    color: #000;
    background: #fff;
    margin: 0;
    padding: 0;
  }}

  .page {{
    width: 100%;
  }}

  /* ── Header ── */
  .header {{ text-align: center; margin-bottom: 6pt; }}
  .header-name {{
    font-size: 20pt;
    font-weight: 700;
    letter-spacing: 0.5pt;
    line-height: 1.2;
  }}
  .header-contact {{
    font-size: 8.5pt;
    margin-top: 3pt;
    color: #000;
  }}
  .header-tagline {{
    font-size: 8.5pt;
    color: #333;
    margin-top: 2pt;
  }}

  /* ── Section ── */
  .section {{
    margin-top: 8pt;
  }}
  .section-title {{
    font-size: 10.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3pt;
    margin-bottom: 1pt;
  }}
  .section-rule {{
    border-top: 1.2pt solid #000;
    margin-bottom: 4pt;
  }}

  /* ── Entry (Experience / Projects / Education) ── */
  .entry {{
    margin-bottom: 5pt;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .entry-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }}
  .entry-org {{
    font-size: 10pt;
    font-weight: 700;
  }}
  .entry-tech {{
    font-size: 9pt;
    font-style: italic;
    font-weight: 400;
  }}
  .entry-title {{
    font-size: 9.5pt;
    font-weight: 400;
    font-style: italic;
    margin-top: 0pt;
  }}
  .entry-subtitle {{
    font-size: 9pt;
    color: #000;
    font-style: italic;
    margin-top: 0pt;
  }}
  .entry-date {{
    font-size: 9.5pt;
    font-weight: 400;
    white-space: nowrap;
    flex-shrink: 0;
    margin-left: 8pt;
  }}

  /* ── Bullets ── */
  .bullet-list {{
    margin-top: 2pt;
    margin-left: 0;
    padding-left: 0;
    list-style-type: disc;
    list-style-position: inside;
  }}
  .bullet-list li {{
    margin-bottom: 1.5pt;
    line-height: 1.4;
    font-size: 9.5pt;
    page-break-inside: avoid;
    break-inside: avoid;
    text-indent: -10pt;
    padding-left: 10pt;
  }}

  /* ── Skills ── */
  .skills-row {{
    margin-bottom: 2pt;
    line-height: 1.4;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .skill-label {{
    font-weight: 700;
    font-size: 9.5pt;
  }}
  .skill-values {{
    font-size: 9.5pt;
  }}

  /* ── Link style ── */
  .link {{
    color: #0b57d0;
    text-decoration: none;
    font-weight: bold;
  }}
  .link:hover {{
    text-decoration: underline;
  }}
</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="header">
    <div class="header-name">{name}</div>
    <div class="header-contact">{contact_line}</div>
    <div class="header-tagline">{location}</div>
  </div>

  <!-- EDUCATION -->
  {"" if not edu_html else f'''<div class="section">
    <div class="section-title">EDUCATION</div>
    <div class="section-rule"></div>
    {edu_html}
  </div>'''}

  <!-- EXPERIENCE -->
  {"" if not exp_html else f'''<div class="section">
    <div class="section-title">EXPERIENCE</div>
    <div class="section-rule"></div>
    {exp_html}
  </div>'''}

  <!-- PROJECTS -->
  {"" if not proj_html else f'''<div class="section">
    <div class="section-title">PROJECTS</div>
    <div class="section-rule"></div>
    {proj_html}
  </div>'''}

  <!-- ADDITIONAL PROJECTS -->
  {add_proj_html}

  <!-- TECHNICAL SKILLS -->
  {"" if not skills_rows else f'''<div class="section">
    <div class="section-title">TECHNICAL SKILLS</div>
    <div class="section-rule"></div>
    {skills_rows}
  </div>'''}

  <!-- CERTIFICATIONS -->
  {certs_html}

</div>
</body>
</html>
"""
    return html


def render_resume_to_pdf(tailored_json: dict, output_path: str) -> str:
    """
    Renders a tailored resume JSON into a properly formatted PDF matching
    Gaurav's actual resume layout (Jake Ryan / serif / single-column style).
    Uses WeasyPrint if available; falls back to HTML in dev environments.
    """
    logger.info(f"Rendering resume to: {output_path}")
    html_content = _build_html(tailored_json)

    if WEASYPRINT_AVAILABLE:
        weasyprint.HTML(string=html_content).write_pdf(output_path)
        logger.info("Resume PDF rendered via WeasyPrint.")
    else:
        # Write as HTML for inspection in local dev (Windows, no GTK)
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        # Also write a stub at the .pdf path so downstream code can find the file
        with open(output_path, "wb") as f:
            f.write(html_content.encode("utf-8"))
        logger.warning(
            f"WeasyPrint unavailable — resume written as HTML ({html_path}). "
            "To get real PDF output, install GTK3 runtime on Windows or run inside the worker Docker container."
        )

    return output_path
