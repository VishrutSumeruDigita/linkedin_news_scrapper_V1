# LinkedIn Lead Generator

A powerful tool to extract LinkedIn profiles and generate business email addresses using completely free methods.

## Features

- Search for LinkedIn profiles based on keywords
- Extract profile information including name and current company
- Find company domains from LinkedIn profiles
- Generate and verify email addresses using multiple free methods:
  - DNS-based email verification for common patterns
  - Pattern-based email generation with format validation
  - GitHub public email discovery
  - Fallback to most common patterns when other methods fail
- Clean export to CSV for lead generation campaigns

## How It Works

1. **LinkedIn Profile Extraction**: Uses Selenium to search and extract profiles from LinkedIn
2. **Company Domain Identification**: Extracts and cleans company domains from profiles
3. **Email Generation**:
   - Tries multiple email formats (first.last@domain, firstlast@domain, etc.)
   - Verifies domain MX records to confirm email deliverability
   - Uses GitHub API to find public emails when possible
   - Generates the most likely pattern as a fallback

## Free Methods Used

This tool uses completely free methods to find email addresses:

1. **DNS Verification**: Checks if MX records exist for the email domain (ensures deliverability)
2. **Pattern Generation**: Creates common email patterns and validates format
3. **GitHub Integration**: Searches GitHub for public emails associated with the profile name
4. **Intelligent Fallbacks**: Uses most common patterns when other methods fail

## Docker Commands

### Quick Start

```bash
# Build the Docker image
docker build -t linkedin-scraper .

# Run the container
docker run -p 8501:8501 --env-file .env -d linkedin-scraper
```

### Additional Docker Commands

```bash
# Check running containers
docker ps

# View container logs
docker logs [CONTAINER_ID]

# Stop running container
docker stop [CONTAINER_ID]

# Remove container
docker rm [CONTAINER_ID]

# Build with a specific tag
docker build -t linkedin-scraper:latest .

# Build with a custom tag (e.g., for versions)
docker build -t linkedin-scraper:v1.2 .

# Run with a specific tag
docker run -p 8501:8501 --env-file .env -d linkedin-scraper:v1.2

# Rebuild and restart in one command
docker stop $(docker ps -q) || true && docker build -t linkedin-scraper:latest . && docker run -p 8501:8501 --env-file .env -d linkedin-scraper:latest
```

### Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3'
services:
  linkedin-scraper:
    build:
      context: .
    restart: unless-stopped
    ports:
      - "8501:8501"
    env_file:
      - .env
```

Then run:

```bash
# Start with docker-compose
docker-compose up -d

# Stop with docker-compose
docker-compose down
```

## Installation

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/linkedin-lead-generator.git
cd linkedin-lead-generator

# Create .env file with your credentials
cp env.example .env
# Edit .env with your LinkedIn credentials
nano .env

# Build and run with Docker
docker build -t linkedin-scraper .
docker run -p 8501:8501 --env-file .env linkedin-scraper
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/linkedin-lead-generator.git
cd linkedin-lead-generator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
cp env.example .env
# Edit .env with your LinkedIn credentials
nano .env

# Run the application
streamlit run app.py
```

## Environment Variables

Create a `.env` file in the project root with the following:

```
LINKEDIN_EMAIL=your_linkedin_email@example.com
LINKEDIN_PASSWORD=your_linkedin_password

# Optional: For email sending capability
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_email_password

# Proxycurl API Key (Optional but recommended)
PROXYCURL_API_KEY=your_proxycurl_api_key
```

## Usage

1. Open the application in your browser (typically at http://localhost:8501)
2. Enter a search keyword (e.g., "Product Manager San Francisco")
3. Set the number of profiles to extract
4. Configure advanced options if needed
5. Click "Run Extraction"
6. Download the results as CSV when complete

## Disclaimer

This tool is for educational purposes only. Users are responsible for complying with LinkedIn's terms of service and relevant privacy laws. Always use responsibly and ethically. 