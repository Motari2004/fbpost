# ========================================
# Dockerfile for Flask + Playwright FB Poster
# ========================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering output
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Set working directory
WORKDIR /app

# Install system dependencies required by Chromium + Playwright
# (manual list to avoid deprecated/obsolete packages like ttf-unifont)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    curl \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first → better caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (chromium only)
# First install deps, then browser → avoids most common errors
RUN playwright install-deps && \
    playwright install chromium --with-deps

# Copy the rest of the application
COPY . .

# Create directories (in case they don't exist)
RUN mkdir -p fb_session uploads

# Expose Flask port (Render uses $PORT anyway)
EXPOSE 5000

# Run the app (Render will override port via $PORT)
CMD ["python", "app.py"]