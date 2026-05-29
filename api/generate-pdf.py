"""
JobTracker PDF Generation — Vercel Serverless Function
Uses ReportLab for pure-Python ATS-readable PDF generation.
No system dependencies — works perfectly on Vercel.

Endpoint: POST /api/generate-pdf
Body: { type: "resume"|"coverletter", resume: {...}, style: {...} }
      or { type: "coverletter", coverLetter: {...}, style: {...} }
"""

import json
import io
import sys
from http.server import BaseHTTPRequestHandler

# ── ReportLab imports ─────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    KeepTogether, ListFlowable, ListItem
)
from reportlab.platypus.flowables import HRFlowable


# ── Helpers ───────────────────────────────────────────────────────────────────
def hex_to_color(hex_str):
    """Convert hex color string to ReportLab color."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c*2 for c in hex_str)
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return colors.Color(r/255, g/255, b/255)


def get_page_size(fmt):
    return LETTER if fmt == "Letter" else A4


def pt_to_pt(val):
    """Font sizes come in as pt already."""
    return float(val)


# ── Resume PDF Builder ────────────────────────────────────────────────────────
def build_resume_pdf(data):
    r = data.get("resume", {})
    s = data.get("style", {})

    fontsize     = pt_to_pt(s.get("fontSize", 10))
    lineheight   = float(s.get("lineHeight", 1.5))
    namesize     = pt_to_pt(s.get("nameSize", 22))
    margin_mm    = float(s.get("margin", 14))
    vmargin_mm   = float(s.get("vmargin", 10))
    entryspace   = float(s.get("entrySpace", 6))
    sectionspace = float(s.get("sectionSpace", 8))
    accent       = hex_to_color(s.get("accent", "#111111"))
    namecolor    = hex_to_color(s.get("nameColor", "#111111"))
    bodycolor    = hex_to_color(s.get("bodyColor", "#222222"))
    sectioncolor = hex_to_color(s.get("sectionColor", "#111111"))
    page_size    = get_page_size(s.get("pageFormat", "A4"))
    contactsize  = max(fontsize - 1, 7)
    titlesize    = max(fontsize + 0.5, 9)

    margin   = margin_mm * mm
    vmargin  = vmargin_mm * mm
    leading  = fontsize * lineheight

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=vmargin, bottomMargin=vmargin
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    name_style = ParagraphStyle("Name",
        fontSize=namesize, leading=namesize*1.2,
        textColor=namecolor, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=4)

    contact_style = ParagraphStyle("Contact",
        fontSize=contactsize, leading=contactsize*1.8,
        textColor=colors.Color(0.27, 0.27, 0.27),
        alignment=TA_CENTER, spaceAfter=4)

    section_style = ParagraphStyle("Section",
        fontSize=titlesize, leading=titlesize*1.3,
        textColor=sectioncolor,
        fontName="Helvetica-Bold", spaceBefore=sectionspace,
        spaceAfter=4, textTransform="uppercase",
        letterSpacing=0.8)

    body_style = ParagraphStyle("Body",
        fontSize=fontsize, leading=leading,
        textColor=bodycolor, alignment=TA_JUSTIFY,
        spaceAfter=2)

    company_style = ParagraphStyle("Company",
        fontSize=fontsize, leading=leading,
        textColor=sectioncolor, fontName="Helvetica-Bold")

    italic_style = ParagraphStyle("Italic",
        fontSize=fontsize, leading=leading,
        textColor=colors.Color(0.2, 0.2, 0.2),
        fontName="Helvetica-Oblique")

    date_style = ParagraphStyle("Date",
        fontSize=contactsize, leading=contactsize*1.4,
        textColor=colors.Color(0.33, 0.33, 0.33),
        alignment=TA_LEFT)

    bullet_style = ParagraphStyle("Bullet",
        fontSize=fontsize, leading=leading,
        textColor=bodycolor, leftIndent=12,
        bulletIndent=0, spaceAfter=1)

    # ── Content ───────────────────────────────────────────────────────────────
    story = []

    fname = r.get("fname", "")
    lname = r.get("lname", "")
    name  = f"{fname} {lname}".strip()

    if name:
        story.append(Paragraph(name, name_style))

    contacts = [c for c in [
        r.get("email",""), r.get("phone",""),
        r.get("location",""), r.get("linkedin",""), r.get("website","")
    ] if c]
    if contacts:
        story.append(Paragraph(" &nbsp;|&nbsp; ".join(contacts), contact_style))

    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=accent, spaceAfter=6))

    # Summary
    if r.get("summary"):
        story.append(Paragraph("SUMMARY", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.Color(0.8,0.8,0.8), spaceAfter=4))
        story.append(Paragraph(r["summary"], body_style))
        story.append(Spacer(1, sectionspace))

    # Education
    edu_entries = r.get("eduEntries", [])
    if edu_entries:
        story.append(Paragraph("EDUCATION", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.Color(0.8,0.8,0.8), spaceAfter=4))
        for e in edu_entries:
            dates   = " – ".join(filter(None, [e.get("startdate",""), e.get("enddate","")]))
            loc     = e.get("location","")
            dateloc = dates + (" | " + loc if loc else "")

            entry_items = []
            # School + dates on same line using table-like formatting
            school_line = f'<b>{e.get("school","")}</b>'
            if dateloc:
                # Right-align dates using spacer trick
                school_line = f'<b>{e.get("school","")}</b>'
                entry_items.append(Paragraph(school_line, company_style))
                entry_items.append(Paragraph(dateloc, date_style))
            else:
                entry_items.append(Paragraph(school_line, company_style))

            if e.get("degree"):
                entry_items.append(Paragraph(f'<i>{e["degree"]}</i>', italic_style))
            if e.get("note"):
                entry_items.append(Paragraph(f"• {e['note']}", bullet_style))

            story.append(KeepTogether(entry_items))
            story.append(Spacer(1, entryspace))
        story.append(Spacer(1, sectionspace))

    # Experience
    exp_entries = r.get("expEntries", [])
    if exp_entries:
        story.append(Paragraph("EXPERIENCE", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.Color(0.8,0.8,0.8), spaceAfter=4))
        for e in exp_entries:
            dates   = " – ".join(filter(None, [e.get("startdate",""), e.get("enddate","")]))
            loc     = e.get("location","")
            dateloc = dates + (" | " + loc if loc else "")
            raw     = e.get("bullets","")
            bullets = [b.strip().lstrip("•-").strip()
                      for b in raw.split("\n")
                      if b.strip() and b.strip() != "•"]

            entry_items = []
            company = e.get("company","")
            title   = e.get("title","")
            if company and title:
                entry_items.append(Paragraph(
                    f'<b>{company},</b> <i>{title}</i>', company_style))
            elif company:
                entry_items.append(Paragraph(f'<b>{company}</b>', company_style))

            if dateloc:
                entry_items.append(Paragraph(dateloc, date_style))

            for b in bullets:
                entry_items.append(Paragraph(f"• {b}", bullet_style))

            story.append(KeepTogether(entry_items))
            story.append(Spacer(1, entryspace))
        story.append(Spacer(1, sectionspace))

    # Skills
    if r.get("skills"):
        story.append(Paragraph("SKILLS", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.Color(0.8,0.8,0.8), spaceAfter=4))
        story.append(Paragraph(r["skills"], body_style))
        story.append(Spacer(1, sectionspace))

    # Certifications
    if r.get("certs"):
        story.append(Paragraph("CERTIFICATIONS", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.Color(0.8,0.8,0.8), spaceAfter=4))
        lines = [l.strip().lstrip("•-").strip()
                for l in r["certs"].split("\n") if l.strip()]
        for line in lines:
            story.append(Paragraph(f"• {line}", bullet_style))

    doc.build(story)
    buf.seek(0)
    return buf


# ── Cover Letter PDF Builder ──────────────────────────────────────────────────
def build_coverletter_pdf(data):
    cl = data.get("coverLetter", {})
    s  = data.get("style", {})

    fs        = pt_to_pt(s.get("fontSize", 10.5))
    lh        = float(s.get("lineHeight", 1.85))
    margin_mm = float(s.get("margin", 20))
    vmargin_mm= float(s.get("vmargin", 18))
    accent    = hex_to_color(s.get("accent", "#111111"))
    namecolor = hex_to_color(s.get("nameColor", "#111111"))
    bodycolor = hex_to_color(s.get("bodyColor", "#222222"))
    page_size = get_page_size(s.get("pageFormat", "A4"))

    margin  = margin_mm * mm
    vmargin = vmargin_mm * mm
    leading = fs * lh

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=vmargin, bottomMargin=vmargin
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    name_style = ParagraphStyle("Name",
        fontSize=20, leading=24,
        textColor=namecolor, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=3)

    contact_style = ParagraphStyle("Contacts",
        fontSize=9, leading=16,
        textColor=colors.Color(0.27,0.27,0.27),
        alignment=TA_CENTER, spaceAfter=4)

    date_style = ParagraphStyle("Date",
        fontSize=fs, leading=fs*1.4,
        textColor=colors.Color(0.27,0.27,0.27),
        spaceAfter=fs*0.8)

    recipient_name_style = ParagraphStyle("RecipientName",
        fontSize=fs+0.5, leading=(fs+0.5)*1.3,
        textColor=colors.Color(0.07,0.07,0.07),
        fontName="Helvetica-Bold")

    recipient_style = ParagraphStyle("Recipient",
        fontSize=fs, leading=fs*1.6,
        textColor=colors.Color(0.33,0.33,0.33))

    subject_style = ParagraphStyle("Subject",
        fontSize=fs, leading=fs*1.4,
        textColor=colors.Color(0.07,0.07,0.07),
        fontName="Helvetica-Bold", spaceAfter=fs*0.8)

    body_style = ParagraphStyle("Body",
        fontSize=fs, leading=leading,
        textColor=bodycolor, alignment=TA_JUSTIFY,
        spaceAfter=fs*0.8)

    signoff_style = ParagraphStyle("Signoff",
        fontSize=fs, leading=fs*1.4,
        textColor=bodycolor, spaceBefore=fs*1.5,
        spaceAfter=fs*2.5)

    signame_style = ParagraphStyle("SigName",
        fontSize=12, leading=15,
        textColor=colors.Color(0.07,0.07,0.07),
        fontName="Helvetica-Bold")

    sigtitle_style = ParagraphStyle("SigTitle",
        fontSize=9, leading=12,
        textColor=colors.Color(0.33,0.33,0.33))

    # ── Content ───────────────────────────────────────────────────────────────
    story = []

    name = cl.get("fullname","")
    if name:
        story.append(Paragraph(name, name_style))

    contacts = [c for c in [
        cl.get("email",""), cl.get("phone",""),
        cl.get("location",""), cl.get("linkedin","")
    ] if c]
    if contacts:
        story.append(Paragraph(" &nbsp;|&nbsp; ".join(contacts), contact_style))

    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=accent, spaceAfter=14))

    if cl.get("date"):
        story.append(Paragraph(cl["date"], date_style))

    manager = cl.get("manager","")
    company = cl.get("company","")
    address = cl.get("address","")
    if manager: story.append(Paragraph(manager, recipient_name_style))
    if company: story.append(Paragraph(company, recipient_style))
    if address: story.append(Paragraph(address, recipient_style))
    if manager or company or address:
        story.append(Spacer(1, fs*0.8))

    jobtitle = cl.get("title","")
    if jobtitle or company:
        subj = " — ".join(filter(None, [jobtitle, company]))
        story.append(Paragraph(f"Re: {subj}", subject_style))

    body_txt = cl.get("body","")
    if body_txt:
        salutation = f"Dear {manager}," if manager else "Dear Hiring Manager,"
        story.append(Paragraph(salutation, body_style))
        for p in [p.strip() for p in body_txt.split("\n\n") if p.strip()]:
            story.append(Paragraph(p.replace("\n", "<br/>"), body_style))

    signoff = cl.get("signoff","Sincerely")
    story.append(Paragraph(f"{signoff},", signoff_style))

    signame = cl.get("signame","") or name
    if signame:
        story.append(Paragraph(signame, signame_style))

    ptitle = cl.get("jobtitlePersonal","")
    if ptitle:
        story.append(Paragraph(ptitle, sigtitle_style))

    doc.build(story)
    buf.seek(0)
    return buf


# ── Vercel handler ────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            data   = json.loads(body)
        except Exception as e:
            self._error(400, f"Invalid request: {e}")
            return

        doc_type = data.get("type", "resume")

        try:
            if doc_type == "resume":
                pdf_buf  = build_resume_pdf(data)
                r        = data.get("resume", {})
                fname    = r.get("fname", "resume").replace(" ", "_")
                filename = f"{fname}_resume.pdf"
            else:
                pdf_buf  = build_coverletter_pdf(data)
                cl       = data.get("coverLetter", {})
                name     = cl.get("fullname","cover_letter").replace(" ","_")
                filename = f"{name}_cover_letter.pdf"

            pdf_bytes = pdf_buf.read()

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition",
                           f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            self._error(500, str(e))

    def do_GET(self):
        """Health check endpoint."""
        try:
            import reportlab
            msg = json.dumps({
                "status": "ok",
                "engine": "reportlab",
                "version": reportlab.Version
            })
        except ImportError:
            msg = json.dumps({"status": "error", "message": "reportlab not installed"})

        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(msg.encode())

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _error(self, code, message):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress default logging
