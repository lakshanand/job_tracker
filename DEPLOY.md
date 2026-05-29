# Deploying JobTracker to Vercel

One deployment. Everything included. Free.

## Architecture

```
Vercel (single deployment)
├── index.html           ← Job Tracker (static)
├── resume.html          ← Resume Builder (static)
├── cover-letter.html    ← Cover Letter (static)
├── shared.js            ← Shared logic (static)
└── api/
    └── generate-pdf.py  ← PDF generation (serverless function)
```

When a user clicks Download PDF → browser calls `/api/generate-pdf` →
Vercel runs the Python function → ReportLab generates the PDF → returned to user.

---

## Deploy in 3 steps

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial release"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/jobtracker.git
git push -u origin main
```

### Step 2 — Deploy to Vercel
1. Go to [vercel.com](https://vercel.com) and sign up (free, use GitHub login)
2. Click **Add New Project**
3. Import your `jobtracker` GitHub repo
4. Leave all settings as default — Vercel auto-detects everything
5. Click **Deploy**

That's it. Vercel gives you a URL like `https://jobtracker-abc123.vercel.app`

### Step 3 — Set a custom domain (optional)
In your Vercel project → Settings → Domains → add `jobtracker.yourdomain.com`

---

## How it works for users

1. User visits your Vercel URL
2. First AI click → prompted for their free Gemini API key
   - Get one free at [aistudio.google.com](https://aistudio.google.com)
   - Saved in their browser only — never sent anywhere
3. Click Download PDF → `/api/generate-pdf` generates a proper ATS-readable PDF
4. Everything works — no installs, no setup

---

## Updating the app

```bash
git add .
git commit -m "Your changes"
git push
```
Vercel auto-deploys on every push. Takes ~30 seconds.

---

## Running locally

```bash
# Install Vercel CLI
npm i -g vercel

# Run locally (simulates Vercel environment including the Python function)
vercel dev
```
Opens at http://localhost:3000

Or without Vercel CLI (PDF falls back to browser print locally):
```bash
python -m http.server 8080
# Open http://localhost:8080
```

---

## Cost

| Resource | Vercel Free Tier | Your usage |
|---|---|---|
| Bandwidth | 100 GB/month | Way under |
| Serverless function invocations | 100,000/month | ~1 per PDF download |
| Function execution time | 100 GB-hours/month | ~1 sec per PDF |
| Deployments | Unlimited | ✅ |

**You would need 100,000 PDF downloads/month to exceed free tier.**

---

## File structure

```
jobtracker/
├── api/
│   └── generate-pdf.py   # Vercel serverless function (ReportLab PDF)
├── index.html            # Job Tracker
├── resume.html           # Resume Builder
├── cover-letter.html     # Cover Letter Builder
├── shared.js             # Shared data, AI, sidebar
├── vercel.json           # Vercel routing config
├── requirements.txt      # Python deps (reportlab)
├── pdf_server.py         # Optional: local WeasyPrint server
├── .gitignore
└── README.md
```
