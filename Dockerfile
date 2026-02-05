FROM python:3.11-slim-bookworm

# 1. Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 2. Install only the essential system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 3. Handle requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Install Playwright and its EXACT dependencies for this OS
# We use 'playwright install --with-deps chromium' to let it 
# auto-detect the correct library versions for Debian Bookworm.
RUN playwright install chromium --with-deps

# 5. Copy your application code
COPY . .

# 6. Create necessary folders and set permissions
RUN mkdir -p fb_session uploads && chmod -R 777 fb_session uploads

# 7. Render uses the PORT environment variable
EXPOSE 5000

CMD ["python", "app.py"]