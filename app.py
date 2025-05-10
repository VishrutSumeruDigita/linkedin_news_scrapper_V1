import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from scraper import (
    linkedin_login, 
    search_profiles,
    extract_company_domain, 
    get_valid_email
)

# Load environment variables
load_dotenv()


# Verify environment variables are loading correctly
print("LinkedIn email exists:", bool(os.getenv("LINKEDIN_EMAIL")))
print("LinkedIn password exists:", bool(os.getenv("LINKEDIN_PASSWORD")))

# Page configuration
st.set_page_config(
    page_title="LinkedIn Lead Generator",
    page_icon="🔍",
    layout="wide"
)

def main():
    st.title("🔍 Automated LinkedIn Lead Generator")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Search Parameters")
        keyword = st.text_input("Search Keyword", "AI Product Manager")
        limit = st.slider("Number of profiles", 5, 100, 10)
        
        st.header("Email Settings")
        email_template = st.text_area(
            "Email Template",
            """Hi {name},\n\nI noticed your profile on LinkedIn and thought you might be interested in our services.\n\nBest regards,\nYour Name"""
        )
    
    # Main content area
    tab1, tab2 = st.tabs(["Lead Generation", "Email Campaign"])
    
    with tab1:
        if st.button("🚀 Run Extraction", type="primary"):
            run_extraction(keyword, limit)
    
    with tab2:
        if 'leads_df' in st.session_state and not st.session_state.leads_df.empty:
            send_email_campaign(email_template)
        else:
            st.warning("No leads available. Run extraction first.")

def run_extraction(keyword, limit):
    """Run the lead generation process"""
    try:
        with st.spinner("🔒 Logging in to LinkedIn..."):
            driver = linkedin_login()
        
        with st.spinner(f"🔍 Searching for '{keyword}' profiles..."):
            profiles = search_profiles(driver, keyword, limit=limit)
            st.success(f"✅ Found {len(profiles)} profiles")
        
        leads = []
        progress_bar = st.progress(0)
        results_placeholder = st.empty()
        
        for i, profile in enumerate(profiles):
            try:
                with st.spinner(f"🔄 Processing {i+1}/{len(profiles)}: {profile['name']}"):
                    # Extract name parts
                    name_parts = profile["name"].split(" ", 1)
                    first = name_parts[0].strip()
                    last = name_parts[1].strip() if len(name_parts) > 1 else ""
                    
                    # Get company domain
                    domain = extract_company_domain(driver, profile["url"])
                    
                    # Generate email if domain found
                    email = None
                    if domain and first and last:
                        email = get_valid_email(first.lower(), last.lower(), domain)
                    
                    if email:
                        leads.append({
                            "Name": profile["name"],
                            "Email": email,
                            "LinkedIn": profile["url"],
                            "Company Domain": domain,
                            "First Name": first,
                            "Last Name": last
                        })
                    
                    # Update progress
                    progress = (i + 1) / len(profiles)
                    progress_bar.progress(progress)
                    
                    # Show interim results
                    if leads:
                        results_placeholder.dataframe(pd.DataFrame(leads))
            except Exception as e:
                st.error(f"Error processing {profile['name']}: {str(e)}")
        
        # Final results
        if leads:
            df = pd.DataFrame(leads)
            st.session_state.leads_df = df
            
            st.success(f"🎉 Successfully extracted {len(leads)} leads!")
            st.dataframe(df)
            
            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name="linkedin_leads.csv",
                mime="text/csv"
            )
        else:
            st.warning("No valid leads found. Try different search parameters.")
            
    except Exception as e:
        st.error(f"❌ Extraction failed: {str(e)}")
    finally:
        if 'driver' in locals() and driver:
            driver.quit()

def send_email_campaign(template):
    """Send email campaign to collected leads"""
    st.subheader("Email Campaign")
    
    if st.button("✉️ Send Emails", type="primary"):
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            sender = os.getenv("SMTP_EMAIL")
            pwd = os.getenv("SMTP_PASSWORD")
            
            if not sender or not pwd:
                st.error("Missing email credentials in .env file")
                return
                
            with st.spinner("Sending emails..."):
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(sender, pwd)
                    
                    success_count = 0
                    for _, row in st.session_state.leads_df.iterrows():
                        try:
                            msg = MIMEMultipart()
                            msg['From'] = sender
                            msg['To'] = row["Email"]
                            msg['Subject'] = "Opportunity"
                            
                            body = template.format(
                                name=row['Name'],
                                first_name=row['First Name'],
                                last_name=row['Last Name'],
                                company=row['Company Domain'].split('.')[0]
                            )
                            msg.attach(MIMEText(body, 'plain'))
                            
                            server.send_message(msg)
                            success_count += 1
                        except Exception as e:
                            st.warning(f"Failed to send to {row['Email']}: {str(e)}")
                    
                    st.success(f"✅ Successfully sent {success_count} emails!")
        except Exception as e:
            st.error(f"❌ Email sending failed: {str(e)}")

if __name__ == "__main__":
    main()