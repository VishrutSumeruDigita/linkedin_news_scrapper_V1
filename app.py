import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from scraper import (
    linkedin_login, search_profiles,
    extract_company_domain, get_valid_email
)

# Load environment variables
load_dotenv()

st.title("Automated LinkedIn Lead Generator")

keyword = st.text_input("Search Keyword", "AI Product Manager")
limit = st.slider("Number of profiles to scrape", 5, 50, 10)

if st.button("Run Extraction"):
    try:
        with st.spinner("Logging in to LinkedIn..."):
            driver = linkedin_login()
        
        with st.spinner(f"Searching for '{keyword}' profiles..."):
            profiles = search_profiles(driver, keyword, limit=limit)
            st.success(f"Found {len(profiles)} profiles")
        
        leads = []
        progress_bar = st.progress(0)
        
        for i, p in enumerate(profiles):
            try:
                with st.spinner(f"Processing profile {i+1}/{len(profiles)}: {p['name']}"):
                    name_parts = p["name"].split(" ", 1)
                    if len(name_parts) >= 2:
                        first, last = name_parts
                    else:
                        first, last = name_parts[0], ""
                    
                    domain = extract_company_domain(driver, p["url"])
                    if domain:
                        email = get_valid_email(first.lower(), last.lower(), domain)
                        if email:
                            leads.append({
                                "Name": p["name"], 
                                "Email": email,
                                "LinkedIn": p["url"],
                                "Company Domain": domain
                            })
            except Exception as e:
                st.error(f"Error processing profile {p['name']}: {str(e)}")
            
            # Update progress bar
            progress_bar.progress((i + 1) / len(profiles))
        
        if leads:
            df = pd.DataFrame(leads)
            st.dataframe(df)
            st.session_state.leads_df = df
            
            # Add download button
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="linkedin_leads.csv",
                mime="text/csv"
            )
        else:
            st.warning("No valid leads found. Try a different keyword or check your LinkedIn credentials.")
    except Exception as e:
        st.error(f"Error during extraction: {str(e)}")
    finally:
        if 'driver' in locals() and driver:
            driver.quit()

st.divider()
st.subheader("Email Campaign")

template = st.text_area("Cold Email Template", "Hi {name},\n\nI noticed your profile on LinkedIn and thought you might be interested in our services.\n\nBest regards,\nYour Name")

if st.button("Send Mail") and 'leads_df' in st.session_state and not st.session_state.leads_df.empty:
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        sender = os.getenv("SMTP_EMAIL")
        pwd = os.getenv("SMTP_PASSWORD")
        
        if not sender or not pwd:
            st.error("Missing email credentials. Please set SMTP_EMAIL and SMTP_PASSWORD environment variables.")
        else:
            with st.spinner("Sending emails..."):
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(sender, pwd)
                    
                    for _, row in st.session_state.leads_df.iterrows():
                        msg = MIMEMultipart()
                        msg['From'] = sender
                        msg['To'] = row["Email"]
                        msg['Subject'] = "Opportunity"
                        
                        body = template.format(name=row['Name'])
                        msg.attach(MIMEText(body, 'plain'))
                        
                        server.send_message(msg)
                
                st.success("Emails sent successfully!")
    except Exception as e:
        st.error(f"Error sending emails: {str(e)}")

