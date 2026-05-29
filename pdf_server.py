"""
JobTracker PDF Generation Server
Uses WeasyPrint for ATS-readable PDFs.

Local:  python pdf_server.py
Cloud:  Deployed via Docker to Google Cloud Run
"""

import os
import json
import tempfile
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)

# Allow requests from GitHub Pages and localhost
CORS(app, resources={r"/*": {"origins": [
    "https://*.github.io",
    "http://localhost:*",
    "http://127.0.0.1:*",
]}})

# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    try:
        import weasyprint
        return jsonify({"status": "ok", "engine": "weasyprint", "version": weasyprint.__version__})
    except ImportError:
        return jsonify({"status": "error", "message": "weasyprint not installed"}), 500

# ── Resume HTML builder ───────────────────────────────────────────────────────
def build_resume_html(data):
    r = data.get("resume", {})
    s = data.get("style", {})

    font         = s.get("font", "Arial")
    fontsize     = float(s.get("fontSize", 10))
    lineheight   = float(s.get("lineHeight", 1.5))
    namesize     = float(s.get("nameSize", 22))
    margin       = float(s.get("margin", 14))
    vmargin      = float(s.get("vmargin", 10))
    entryspace   = float(s.get("entrySpace", 6))
    sectionspace = float(s.get("sectionSpace", 8))
    accent       = s.get("accent", "#111111")
    namecolor    = s.get("nameColor", "#111111")
    bodycolor    = s.get("bodyColor", "#222222")
    sectioncolor = s.get("sectionColor", "#111111")
    page_size    = s.get("pageFormat", "A4")
    contactsize  = max(fontsize - 1, 7)
    titlesize    = max(fontsize + 0.5, 9)

    fname = r.get("fname", "")
    lname = r.get("lname", "")
    name  = f"{fname} {lname}".strip()

    css = f"""
    @page {{
        size: {page_size};
        margin: {vmargin}mm {margin}mm;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: '{font}', 'Helvetica Neue', Arial, sans-serif;
        font-size: {fontsize}pt;
        line-height: {lineheight};
        color: {bodycolor};
        background: white;
    }}
    .rv-name {{
        font-size: {namesize}pt;
        font-weight: 800;
        text-align: center;
        color: {namecolor};
        margin-bottom: 4pt;
    }}
    .rv-contacts {{
        text-align: center;
        font-size: {contactsize}pt;
        color: #444;
        margin-bottom: 6pt;
        line-height: 1.8;
    }}
    .rv-divider {{
        border: none;
        border-top: 1.5pt solid {accent};
        margin-bottom: 8pt;
    }}
    .rv-section {{
        margin-bottom: {sectionspace}pt;
        page-break-inside: avoid;
    }}
    .rv-section-title {{
        font-size: {titlesize}pt;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {sectioncolor};
        border-bottom: 0.75pt solid #ccc;
        padding-bottom: 2pt;
        margin-bottom: 5pt;
    }}
    .rv-summary {{
        font-size: {fontsize}pt;
        line-height: {lineheight};
    }}
    .rv-entry {{
        margin-bottom: {entryspace}pt;
        page-break-inside: avoid;
    }}
    .rv-entry-head {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 8pt;
        margin-bottom: 2pt;
    }}
    .rv-entry-left {{ flex: 1; min-width: 0; }}
    .rv-entry-company {{
        font-weight: 700;
        color: {sectioncolor};
    }}
    .rv-entry-title {{
        font-style: italic;
        color: #333;
    }}
    .rv-entry-dates {{
        font-size: {contactsize}pt;
        color: #555;
        white-space: nowrap;
        text-align: right;
        flex-shrink: 0;
    }}
    .rv-bullets {{
        margin: 3pt 0 0 14pt;
        padding: 0;
        list-style-type: disc;
    }}
    .rv-bullets li {{
        font-size: {fontsize}pt;
        line-height: {lineheight};
        margin-bottom: 1pt;
        list-style-type: disc;
        list-style-position: outside;
    }}
    .rv-edu-head {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 8pt;
        margin-bottom: 2pt;
    }}
    .rv-edu-left {{ flex: 1; }}
    .rv-edu-school {{ font-weight: 700; display: block; }}
    .rv-edu-degree {{ font-style: italic; color: #333; display: block; }}
    .rv-edu-dates {{
        font-size: {contactsize}pt;
        color: #555;
        white-space: nowrap;
        text-align: right;
    }}
    .rv-edu-note {{
        font-size: {fontsize}pt;
        padding-left: 14pt;
    }}
    .rv-skills, .rv-certs {{
        font-size: {fontsize}pt;
        line-height: {lineheight};
    }}
    .rv-certs ul {{
        margin-left: 14pt;
        list-style-type: disc;
    }}
    .rv-certs li {{
        list-style-type: disc;
        list-style-position: outside;
        margin-bottom: 1pt;
    }}
    """

    body = ""
    if name:
        body += f'<div class="rv-name">{name}</div>\n'

    contacts = [c for c in [
        r.get("email",""), r.get("phone",""),
        r.get("location",""), r.get("linkedin",""), r.get("website","")
    ] if c]
    if contacts:
        body += f'<div class="rv-contacts">{" &nbsp;|&nbsp; ".join(contacts)}</div>\n'

    body += '<hr class="rv-divider"/>\n'

    if r.get("summary"):
        body += f'<div class="rv-section"><div class="rv-section-title">Summary</div><div class="rv-summary">{r["summary"]}</div></div>\n'

    edu_entries = r.get("eduEntries", [])
    if edu_entries:
        body += '<div class="rv-section"><div class="rv-section-title">Education</div>\n'
        for e in edu_entries:
            dates   = " – ".join(filter(None, [e.get("startdate",""), e.get("enddate","")]))
            loc     = e.get("location","")
            dateloc = dates + (" | " + loc if loc else "")
            body += '<div class="rv-entry"><div class="rv-edu-head">'
            body += '<div class="rv-edu-left">'
            body += f'<span class="rv-edu-school">{e.get("school","")}</span>'
            if e.get("degree"): body += f'<span class="rv-edu-degree">{e["degree"]}</span>'
            body += '</div>'
            body += f'<span class="rv-edu-dates">{dateloc}</span>'
            body += '</div>'
            if e.get("note"): body += f'<div class="rv-edu-note">• {e["note"]}</div>'
            body += '</div>\n'
        body += '</div>\n'

    exp_entries = r.get("expEntries", [])
    if exp_entries:
        body += '<div class="rv-section"><div class="rv-section-title">Experience</div>\n'
        for e in exp_entries:
            dates   = " – ".join(filter(None, [e.get("startdate",""), e.get("enddate","")]))
            loc     = e.get("location","")
            dateloc = dates + (" | " + loc if loc else "")
            raw     = e.get("bullets","")
            bullets = [b.strip().lstrip("•-").strip() for b in raw.split("\n") if b.strip() and b.strip() != "•"]
            body += '<div class="rv-entry"><div class="rv-entry-head"><div class="rv-entry-left">'
            if e.get("company"): body += f'<span class="rv-entry-company">{e["company"]},&nbsp;</span>'
            if e.get("title"):   body += f'<span class="rv-entry-title">{e["title"]}</span>'
            body += '</div>'
            body += f'<span class="rv-entry-dates">{dateloc}</span></div>'
            if bullets:
                body += '<ul class="rv-bullets">' + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
            body += '</div>\n'
        body += '</div>\n'

    if r.get("skills"):
        body += f'<div class="rv-section"><div class="rv-section-title">Skills</div><div class="rv-skills">{r["skills"]}</div></div>\n'

    if r.get("certs"):
        lines = [l.strip().lstrip("•-").strip() for l in r["certs"].split("\n") if l.strip()]
        body += '<div class="rv-section"><div class="rv-section-title">Certifications</div><div class="rv-certs">'
        if len(lines) > 1:
            body += '<ul>' + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"
        else:
            body += r["certs"]
        body += '</div></div>\n'

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>
<style>{css}</style>
</head><body>{body}</body></html>"""


# ── Cover letter HTML builder ─────────────────────────────────────────────────
def build_coverletter_html(data):
    cl = data.get("coverLetter", {})
    s  = data.get("style", {})

    font      = s.get("font", "Arial")
    fs        = float(s.get("fontSize", 10.5))
    lh        = float(s.get("lineHeight", 1.85))
    margin    = float(s.get("margin", 20))
    vmargin   = float(s.get("vmargin", 18))
    accent    = s.get("accent", "#111111")
    namecolor = s.get("nameColor", "#111111")
    bodycolor = s.get("bodyColor", "#222222")
    page_size = s.get("pageFormat", "A4")

    css = f"""
    @page {{
        size: {page_size};
        margin: {vmargin}mm {margin}mm;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: '{font}', 'Helvetica Neue', Arial, sans-serif;
        font-size: {fs}pt;
        line-height: {lh};
        color: {bodycolor};
        background: white;
    }}
    .name {{
        font-size: 20pt;
        font-weight: 800;
        text-align: center;
        color: {namecolor};
        margin-bottom: 3pt;
    }}
    .contacts {{
        text-align: center;
        font-size: 9pt;
        color: #444;
        margin-bottom: 6pt;
        line-height: 1.8;
    }}
    .divider {{
        border: none;
        border-top: 1.5pt solid {accent};
        margin-bottom: 14pt;
    }}
    .date {{
        font-size: {fs}pt;
        color: #444;
        margin-bottom: 12pt;
    }}
    .recipient {{ margin-bottom: 14pt; }}
    .recipient-name {{
        font-size: {fs + 0.5}pt;
        font-weight: 700;
        color: #111;
        display: block;
    }}
    .recipient-addr {{
        font-size: {fs}pt;
        color: #555;
        line-height: 1.6;
        display: block;
    }}
    .subject {{
        font-size: {fs}pt;
        font-weight: 700;
        color: #111;
        margin-bottom: 14pt;
    }}
    .para {{
        font-size: {fs}pt;
        line-height: {lh};
        color: {bodycolor};
        margin-bottom: 10pt;
        text-align: justify;
    }}
    .signoff {{
        font-size: {fs}pt;
        margin-bottom: 28pt;
    }}
    .sig-name {{
        font-size: 12pt;
        font-weight: 700;
        color: #111;
    }}
    .sig-title {{
        font-size: 9pt;
        color: #555;
        margin-top: 2pt;
    }}
    """

    name     = cl.get("fullname", "")
    contacts = [c for c in [cl.get("email",""), cl.get("phone",""), cl.get("location",""), cl.get("linkedin","")] if c]
    manager  = cl.get("manager","")
    company  = cl.get("company","")
    address  = cl.get("address","")
    jobtitle = cl.get("title","")
    body_txt = cl.get("body","")
    signoff  = cl.get("signoff","Sincerely")
    signame  = cl.get("signame","") or name
    ptitle   = cl.get("jobtitlePersonal","")

    html = ""
    if name:     html += f'<div class="name">{name}</div>\n'
    if contacts: html += f'<div class="contacts">{" &nbsp;|&nbsp; ".join(contacts)}</div>\n'
    html += '<div class="divider"></div>\n'
    html += f'<div class="date">{cl.get("date","")}</div>\n'

    if manager or company or address:
        html += '<div class="recipient">'
        if manager: html += f'<span class="recipient-name">{manager}</span>'
        if company: html += f'<span class="recipient-addr">{company}</span>'
        if address: html += f'<span class="recipient-addr">{address}</span>'
        html += '</div>\n'

    if jobtitle or company:
        subj = " — ".join(filter(None, [jobtitle, company]))
        html += f'<div class="subject">Re: {subj}</div>\n'

    if body_txt:
        salutation = f"Dear {manager}," if manager else "Dear Hiring Manager,"
        html += f'<div class="para">{salutation}</div>\n'
        for p in [p.strip() for p in body_txt.split("\n\n") if p.strip()]:
            html += f'<div class="para">{p.replace(chr(10), "<br>")}</div>\n'

    html += f'<div class="signoff">{signoff},</div>\n'
    html += '<div style="margin-top:28pt"></div>\n'
    if signame: html += f'<div class="sig-name">{signame}</div>\n'
    if ptitle:  html += f'<div class="sig-title">{ptitle}</div>\n'

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>
<style>{css}</style>
</head><body>{html}</body></html>"""


# ── PDF generation endpoint ───────────────────────────────────────────────────
@app.route("/generate-pdf", methods=["POST"])
def generate_pdf():
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        return jsonify({"error": "WeasyPrint not installed. Run: pip install weasyprint"}), 500

    data      = request.json or {}
    doc_type  = data.get("type", "resume")

    if doc_type == "resume":
        html_content = build_resume_html(data)
        r            = data.get("resume", {})
        fname        = r.get("fname", "resume").replace(" ", "_")
        filename     = f"{fname}_resume.pdf"
    else:
        html_content = build_coverletter_html(data)
        cl           = data.get("coverLetter", {})
        name         = cl.get("fullname", "cover_letter").replace(" ", "_")
        filename     = f"{name}_cover_letter.pdf"

    # Generate PDF in memory
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    try:
        HTML(string=html_content).write_pdf(pdf_path)
        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: os.unlink(pdf_path)
        except: pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    print(f"JobTracker PDF Server starting on port {port}")
    print("Using WeasyPrint for PDF generation")
    app.run(host="0.0.0.0", port=port, debug=debug)
