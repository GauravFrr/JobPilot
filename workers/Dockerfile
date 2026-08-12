FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for WeasyPrint (Cairo/Pango stack) and Chromium (Playwright)
# Note: package names are for Debian Trixie (the python:3.11-slim base).
# libgdk-pixbuf2.0-0 was renamed to libgdk-pixbuf-xlib-2.0-0 in Trixie.
# ttf-unifont -> fonts-unifont, ttf-ubuntu-font-family is unavailable (use fonts-freefont-ttf instead).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libgdk-pixbuf-xlib-2.0-0 \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    fonts-liberation \
    fonts-freefont-ttf \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser binary only (deps already installed above)
RUN playwright install chromium

# Copy both workers and api so workers can import app
COPY workers /app/workers
COPY api/app /app/app

CMD ["python", "workers/scheduler.py"]
