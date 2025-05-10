# LinkedIn Lead Generator

A Streamlit application that automates LinkedIn profile scraping to generate leads and send cold emails.

## Features

- Scrape LinkedIn profiles based on search keywords
- Extract email addresses from company domains
- Validate email addresses
- Send personalized cold emails
- Export leads to CSV

## Setup and Installation

### Using Docker (Recommended)

1. Clone the repository:
   ```
   git clone <repository-url>
   cd linkedin_scraper_v1
   ```

2. Create a `.env` file with your credentials:
   ```
   # LinkedIn Credentials
   LINKEDIN_EMAIL=your_linkedin_email@example.com
   LINKEDIN_PASSWORD=your_linkedin_password

   # SMTP Email Settings
   SMTP_EMAIL=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   ```

3. Build and run the Docker container:
   ```
   docker build -t linkedin-scraper .
   docker run -p 8501:8501 --env-file .env linkedin-scraper
   ```

4. Open your browser and navigate to `http://localhost:8501`

### Manual Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd linkedin_scraper_v1
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your credentials (as shown above)

4. Run the application:
   ```
   streamlit run app.py
   ```

## Usage

1. Enter a search keyword (e.g., "AI Product Manager")
2. Select the number of profiles to scrape
3. Click "Run Extraction"
4. Wait for the process to complete
5. View and download the extracted leads
6. Optionally, send cold emails using the email campaign section

## Notes

- Make sure you have a valid LinkedIn account with login credentials
- For sending emails, you need to use an app password if you're using Gmail
- The application uses Selenium with Chrome in headless mode
- The email validation may take some time as it checks if the email server exists

## License

MIT 