# ==========================================
# Base image
# ==========================================
FROM python:3.11-slim-bookworm

# ==========================================
# 1. Environment variables
# ==========================================
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# ==========================================
# 2. Essential system packages
# ==========================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libxshmfence1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# 3. Install Python dependencies
# ==========================================
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==========================================
# 4. Install Playwright Chromium + dependencies
# ==========================================
RUN playwright install chromium --with-deps

# ==========================================
# 5. Copy application code
# ==========================================
COPY . .

# ==========================================
# 6. Create folders for session & uploads
# ==========================================
RUN mkdir -p fb_session uploads && chmod -R 777 fb_session uploads

# ==========================================
# 7. Expose port (Render uses $PORT)
# ==========================================
EXPOSE 5000

# ==========================================
# 8. Run Flask app
# ==========================================
CMD ["python", "app.py"]
