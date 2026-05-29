"""
JobTracker PDF Generation — Vercel Serverless Function
Uses ReportLab for ATS-readable PDFs.
"""

import json
import io
import os
from http.server import BaseHTTPRequestHandler

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, KeepTogether, Table, TableStyle,
    ListFlowable, ListItem
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def hex_color(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return colors.Color(int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)

def page_size(fmt):
    return LETTER if fmt == "Letter" else A4


# ── Resume Builder ────────────────────────────────────────────────────────────
def build_resume_pdf(data):
    r  = data.get("resume", {})
    s  = data.get("style", {})

    fs       = float(s.get("fontSize",    10))
    lh       = float(s.get("lineHeight",  1.5))
    ns       = float(s.get("nameSize",    22))
    mg       = float(s.get("margin",      14)) * mm
    vmg      = float(s.get("vmargin",     10)) * mm
    esp      = float(s.get("entrySpace",  6))
    ssp      = float(s.get("sectionSpace",8))
    accent   = hex_color(s.get("accent",       "#111111"))
    namecol  = hex_color(s.get("nameColor",    "#111111"))
    bodycol  = hex_color(s.get("bodyColor",    "#222222"))
    seccol   = hex_color(s.get("sectionColor", "#111111"))
    pgsz     = page_size(s.get("pageFormat",   "A4"))
    csz      = max(fs - 1, 7)
    tsz      = max(fs + 0.5, 9)
    leading  = fs * lh
    grey     = colors.Color(0.4, 0.4, 0.4)
    ltgrey   = colors.Color(0.8, 0.8, 0.8)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=pgsz,
        leftMargin=mg, rightMargin=mg, topMargin=vmg, bottomMargin=vmg)

    # ── Style helpers ─────────────────────────────────────────────────────────
    def sty(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=fs,
                        leading=leading, textColor=bodycol)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    S = {
        "name":    sty("name", fontSize=ns, leading=ns*1.15, textColor=namecol,
                       fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=3),
        "contact": sty("contact", fontSize=csz, leading=csz*1.6, textColor=grey,
                       alignment=TA_CENTER, spaceAfter=4),
        "secttitle": sty("secttitle", fontSize=tsz, leading=tsz*1.3, textColor=seccol,
                         fontName="Helvetica-Bold", spaceBefore=ssp, spaceAfter=3),
        "summary": sty("summary", alignment=TA_JUSTIFY, spaceAfter=2),
        "company": sty("company", fontName="Helvetica-Bold", textColor=seccol),
        "dates":   sty("dates",   fontSize=csz, leading=csz*1.4, textColor=grey,
                       alignment=TA_RIGHT),
        "italic":  sty("italic",  fontName="Helvetica-Oblique",
                       textColor=colors.Color(0.2,0.2,0.2)),
        "bullet":  sty("bullet", spaceAfter=1),
        "skills":  sty("skills",  spaceAfter=2),
    }

    # Page width for table calculations
    pw = pgsz[0] - mg*2

    story = []

    # ── Name ──────────────────────────────────────────────────────────────────
    name = f"{r.get('fname','')} {r.get('lname','')}".strip()
    if name:
        story.append(Paragraph(name, S["name"]))

    # ── Contacts (pipe-separated, clean) ──────────────────────────────────────
    contacts = [c for c in [
        r.get("email",""), r.get("phone",""),
        r.get("location",""), r.get("linkedin",""), r.get("website","")
    ] if c]
    if contacts:
        story.append(Paragraph(" &nbsp;|&nbsp; ".join(contacts), S["contact"]))

    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=accent, spaceAfter=6))

    def section(title):
        story.append(Paragraph(title, S["secttitle"]))
        story.append(HRFlowable(width="100%", thickness=1.0,
                                color=seccol, spaceAfter=4))

    def entry_row(left, right):
        """Two-column row: company/school left, dates right — on same line."""
        t = Table([[Paragraph(left, S["company"]),
                    Paragraph(right, S["dates"])]],
                  colWidths=[pw*0.68, pw*0.32],
                  hAlign='LEFT')
        t.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 1),
            ("LEFTPADDING",  (1,0), (1,0),   0),
            ("RIGHTPADDING", (1,0), (1,0),   0),
        ]))
        return t

    # ── Summary ───────────────────────────────────────────────────────────────
    if r.get("summary"):
        section("SUMMARY")
        story.append(Paragraph(r["summary"], S["summary"]))
        story.append(Spacer(1, ssp * 0.4))

    # ── Education ─────────────────────────────────────────────────────────────
    edu = r.get("eduEntries", [])
    if edu:
        section("EDUCATION")
        for e in edu:
            dates  = " – ".join(filter(None,[e.get("startdate",""),e.get("enddate","")]))
            loc    = e.get("location","")
            dateloc = dates + (" | " + loc if loc else "")
            items  = []
            items.append(entry_row(
                f'<b>{e.get("school","")}</b>', dateloc))
            if e.get("degree"):
                items.append(Paragraph(f'<i>{e["degree"]}</i>', S["italic"]))
            if e.get("note"):
                items.append(ListFlowable([
                    ListItem(Paragraph(e["note"], S["bullet"]),
                        bulletColor=seccol, value="bullet",
                        leftIndent=16, bulletIndent=4, spaceAfter=0)],
                    bulletType="bullet", start="•",
                    leftIndent=0, spaceAfter=0, spaceBefore=0))
            story.append(KeepTogether(items))
            story.append(Spacer(1, esp))
        story.append(Spacer(1, ssp * 0.4))

    # ── Experience ────────────────────────────────────────────────────────────
    exp = r.get("expEntries", [])
    if exp:
        section("EXPERIENCE")
        for e in exp:
            dates   = " – ".join(filter(None,[e.get("startdate",""),e.get("enddate","")]))
            loc     = e.get("location","")
            dateloc = dates + (" | " + loc if loc else "")
            company = e.get("company","")
            title   = e.get("title","")
            raw     = e.get("bullets","")
            bullets = [b.strip().lstrip("•-").strip()
                      for b in raw.split("\n")
                      if b.strip() and b.strip() != "•"]

            left = ""
            if company and title:
                left = f'<b>{company},</b> <i>{title}</i>'
            elif company:
                left = f'<b>{company}</b>'
            elif title:
                left = f'<i>{title}</i>'

            items = []
            items.append(entry_row(left, dateloc))
            if bullets:
                bullet_items = [ListItem(Paragraph(b, S["bullet"]),
                    bulletColor=seccol, value="bullet",
                    leftIndent=16, bulletIndent=4,
                    spaceAfter=1) for b in bullets]
                items.append(ListFlowable(bullet_items,
                    bulletType="bullet", start="•",
                    leftIndent=0, bulletIndent=0,
                    spaceAfter=0, spaceBefore=0))
            story.append(KeepTogether(items))
            story.append(Spacer(1, esp))
        story.append(Spacer(1, ssp * 0.4))

    # ── Skills ────────────────────────────────────────────────────────────────
    if r.get("skills"):
        section("SKILLS")
        story.append(Paragraph(r["skills"], S["skills"]))
        story.append(Spacer(1, ssp * 0.4))

    # ── Certifications ────────────────────────────────────────────────────────
    if r.get("certs"):
        section("CERTIFICATIONS")
        lines = [l.strip().lstrip("•-").strip()
                for l in r["certs"].split("\n") if l.strip()]
        cert_items = [ListItem(Paragraph(line, S["bullet"]),
            bulletColor=seccol, value="bullet",
            leftIndent=16, bulletIndent=4,
            spaceAfter=1) for line in lines]
        story.append(ListFlowable(cert_items,
            bulletType="bullet", start="•",
            leftIndent=0, spaceAfter=0, spaceBefore=0))

    doc.build(story)
    buf.seek(0)
    return buf


# ── Cover Letter Builder ──────────────────────────────────────────────────────
def build_coverletter_pdf(data):
    cl = data.get("coverLetter", {})
    s  = data.get("style", {})

    fs      = float(s.get("fontSize",  10.5))
    lh      = float(s.get("lineHeight",1.85))
    mg      = float(s.get("margin",    20)) * mm
    vmg     = float(s.get("vmargin",   18)) * mm
    accent  = hex_color(s.get("accent",    "#111111"))
    namecol = hex_color(s.get("nameColor", "#111111"))
    bodycol = hex_color(s.get("bodyColor", "#222222"))
    pgsz    = page_size(s.get("pageFormat","A4"))
    leading = fs * lh
    grey    = colors.Color(0.4, 0.4, 0.4)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=pgsz,
        leftMargin=mg, rightMargin=mg, topMargin=vmg, bottomMargin=vmg)

    def sty(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=fs,
                        leading=leading, textColor=bodycol)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    S = {
        "name":    sty("name", fontSize=20, leading=24, textColor=namecol,
                       fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=3),
        "contact": sty("contact", fontSize=9, leading=16, textColor=grey,
                       alignment=TA_CENTER, spaceAfter=4),
        "date":    sty("date", textColor=grey, spaceAfter=fs*0.8),
        "recname": sty("recname", fontName="Helvetica-Bold",
                       textColor=colors.Color(0.07,0.07,0.07)),
        "recaddr": sty("recaddr", textColor=grey, leading=fs*1.6),
        "subject": sty("subject", fontName="Helvetica-Bold",
                       textColor=colors.Color(0.07,0.07,0.07),
                       spaceAfter=fs*0.8),
        "body":    sty("body", alignment=TA_JUSTIFY, spaceAfter=fs*0.8),
        "signoff": sty("signoff", spaceBefore=fs*1.5, spaceAfter=fs*2.2),
        "signame": sty("signame", fontSize=12, leading=15,
                       fontName="Helvetica-Bold",
                       textColor=colors.Color(0.07,0.07,0.07)),
        "sigtitle":sty("sigtitle", fontSize=9, leading=12, textColor=grey),
    }

    story = []

    name = cl.get("fullname","")
    if name:
        story.append(Paragraph(name, S["name"]))

    contacts = [c for c in [
        cl.get("email",""), cl.get("phone",""),
        cl.get("location",""), cl.get("linkedin","")
    ] if c]
    if contacts:
        story.append(Paragraph(" &nbsp;|&nbsp; ".join(contacts), S["contact"]))

    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=accent, spaceAfter=14))

    if cl.get("date"):
        story.append(Paragraph(cl["date"], S["date"]))

    manager = cl.get("manager","")
    company = cl.get("company","")
    address = cl.get("address","")
    if manager: story.append(Paragraph(manager, S["recname"]))
    if company: story.append(Paragraph(company, S["recaddr"]))
    if address: story.append(Paragraph(address, S["recaddr"]))
    if manager or company or address:
        story.append(Spacer(1, fs*0.8))

    jobtitle = cl.get("title","")
    if jobtitle or company:
        subj = " — ".join(filter(None,[jobtitle, company]))
        story.append(Paragraph(f"Re: {subj}", S["subject"]))

    body_txt = cl.get("body","")
    if body_txt:
        salutation = f"Dear {manager}," if manager else "Dear Hiring Manager,"
        story.append(Paragraph(salutation, S["body"]))
        for p in [p.strip() for p in body_txt.split("\n\n") if p.strip()]:
            story.append(Paragraph(p.replace("\n","<br/>"), S["body"]))

    signoff = cl.get("signoff","Sincerely")
    story.append(Paragraph(f"{signoff},", S["signoff"]))

    signame = cl.get("signame","") or name
    if signame:
        story.append(Paragraph(signame, S["signame"]))

    ptitle = cl.get("jobtitlePersonal","")
    if ptitle:
        story.append(Paragraph(ptitle, S["sigtitle"]))

    doc.build(story)
    buf.seek(0)
    return buf


# ── Vercel handler ────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        try:
            import reportlab
            msg = json.dumps({"status":"ok","engine":"reportlab","version":reportlab.Version})
        except ImportError:
            msg = json.dumps({"status":"error","message":"reportlab not installed"})
        self._json(200, msg)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data   = json.loads(self.rfile.read(length))
        except Exception as e:
            self._json(400, json.dumps({"error": str(e)}))
            return

        doc_type = data.get("type","resume")
        try:
            if doc_type == "resume":
                buf      = build_resume_pdf(data)
                r        = data.get("resume",{})
                fname    = r.get("fname","resume").replace(" ","_")
                filename = f"{fname}_resume.pdf"
            else:
                buf      = build_coverletter_pdf(data)
                cl       = data.get("coverLetter",{})
                name     = cl.get("fullname","cover_letter").replace(" ","_")
                filename = f"{name}_cover_letter.pdf"

            pdf_bytes = buf.read()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition",
                             f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            self._json(500, json.dumps({"error": str(e)}))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, body):
        b = body.encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *args):
        pass
