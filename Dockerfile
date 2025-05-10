# Use official Python slim image
FROM python:3.9-slim

# 1. Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    wget \
    gnupg \
    unzip \
    gcc \
    g++ \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    xvfb \
    x11vnc \
    net-tools \
    curl \
    iputils-ping \
    fonts-liberation \
    libappindicator3-1 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libnspr4 \
    libu2f-udev \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 2. Install specific Chrome version (latest often works better for avoiding detection)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 3. Install ChromeDriver - using a known working version (114)
RUN wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip

# 4. Set environment variables
ENV DISPLAY=:99
ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV STREAMLIT_GATHER_USAGE_STATS=False
ENV STREAMLIT_SERVER_ENABLE_WATCHER=False
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=False
ENV STREAMLIT_SERVER_ENABLE_STATIC_SERVING=True

# 5. Set working directory
WORKDIR /app

# 6. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy application code
COPY . .

# 8. Create data directory for screenshots
RUN mkdir -p /app/data

# 9. Entry point script
RUN echo '#!/bin/bash\n\
# Start Xvfb\n\
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &\n\
# Give Xvfb time to start\n\
sleep 2\n\
# Optional: Start VNC server for debugging\n\
#x11vnc -display :99 -forever -nopw > /dev/null 2>&1 &\n\
# Run Streamlit app\n\
exec streamlit run app.py --server.headless=true --server.port=8501 --server.address=0.0.0.0\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 10. Run command
CMD ["/app/entrypoint.sh"]