# ── JobTracker PDF Server ──────────────────────────────────────────────────────
# Deploys to Google Cloud Run
# Build: docker build -t jobtracker-pdf .
# Run:   docker run -p 5050:5050 jobtracker-pdf

FROM python:3.11-slim

# Install WeasyPrint system dependencies
RUN apt-get update && apt-get install -y \
    # Font rendering
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    # Cairo (PDF rendering)
    libcairo2 \
    # Font packages
    fonts-liberation \
    fonts-dejavu-core \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (better Docker layer caching)
COPY requirements_pdf.txt .
RUN pip install --no-cache-dir -r requirements_pdf.txt

# Copy app
COPY pdf_server.py .

# Cloud Run uses PORT env variable
ENV PORT=8080

# Run
CMD ["python", "pdf_server.py"]
