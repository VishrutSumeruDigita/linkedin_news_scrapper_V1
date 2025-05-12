import streamlit as st
import pandas as pd
import os
import logging
from dotenv import load_dotenv
from scraper import (
    linkedin_login, 
    search_profiles,
    extract_company_domain, 
    get_valid_email,
    get_contact_details,
    clean_name,
    clean_text_data,
    get_profile_data_hybrid,
    get_company_domain_hybrid,
    PROXYCURL_AVAILABLE
)
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    st.title("🔍 LinkedIn Lead Generator Pro")
    
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
        
        # Advanced options
        with st.expander("Advanced Options"):
            st.write("These settings help improve the success rate of finding leads.")
            verify_emails = st.checkbox("Verify emails (slower but more accurate)", value=True)
            add_generic_emails = st.checkbox("Include generic company emails (info@, sales@, etc.)", value=True)
            guess_domains = st.checkbox("Guess domains from company names", value=True)
            use_github = st.checkbox("Search GitHub for public emails (when available)", value=True)
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["Lead Generation", "Email Campaign", "Debug Info"])
    
    with tab1:
        if st.button("🚀 Run Extraction", type="primary"):
            run_extraction(keyword, limit, 
                           verify_emails=verify_emails,
                           add_generic_emails=add_generic_emails,
                           guess_domains=guess_domains,
                           use_github=use_github)
    
    with tab2:
        if 'leads_df' in st.session_state and not st.session_state.leads_df.empty:
            send_email_campaign(email_template)
        else:
            st.warning("No leads available. Run extraction first.")
    
    with tab3:
        st.subheader("Debug Information")
        if 'debug_info' in st.session_state:
            st.json(st.session_state.debug_info)
        else:
            st.info("No debug information available yet. Run extraction first.")

def run_extraction(keyword, limit, verify_emails=True, add_generic_emails=True, guess_domains=True, use_github=True):
    """Run the lead generation process"""
    debug_info = {
        "profiles_found": 0,
        "domains_found": 0,
        "emails_found": 0,
        "email_sources": {
            "dns_verification": 0,
            "pattern_generation": 0,
            "github": 0,
            "fallback": 0,
            "proxycurl": 0
        },
        "errors": [],
        "profile_details": []
    }
    
    # Add Proxycurl status to debug info
    debug_info["proxycurl_available"] = PROXYCURL_AVAILABLE
    
    try:
        with st.spinner("🔒 Logging in to LinkedIn..."):
            driver = linkedin_login()
        
        with st.spinner(f"🔍 Searching for '{keyword}' profiles..."):
            profiles = search_profiles(driver, keyword, limit=limit)
            debug_info["profiles_found"] = len(profiles)
            st.success(f"✅ Found {len(profiles)} profiles")
        
        # Add option to use Proxycurl
        use_proxycurl = PROXYCURL_AVAILABLE
        if PROXYCURL_AVAILABLE:
            use_proxycurl = st.checkbox("Use Proxycurl API (faster and more reliable)", value=True)
            if use_proxycurl:
                st.info("Using Proxycurl API for enhanced data extraction")
        
        leads = []
        all_profiles = []
        progress_bar = st.progress(0)
        results_placeholder = st.empty()
        status_placeholder = st.empty()
        
        status_placeholder.info("Processing profiles... This may take a few minutes.")
        
        for i, profile in enumerate(profiles):
            profile_debug = {
                "name": profile["name"],
                "url": profile["url"],
                "domain_found": False,
                "email_found": False,
                "email_source": None,
                "errors": []
            }
            
            try:
                with st.spinner(f"🔄 Processing {i+1}/{len(profiles)}: {profile['name']}"):
                    status_placeholder.info(f"Processing profile {i+1}/{len(profiles)}: {profile['name']}")
                    
                    # Use the hybrid approach to get profile data
                    profile_data = get_profile_data_hybrid(
                        driver,
                        profile["url"],
                        use_selenium=True,
                        use_proxycurl=use_proxycurl
                    )
                    
                    # Store profile data in the expected format
                    profile_info = {
                        "Name": profile_data["name"] or profile["name"],
                        "LinkedIn": profile_data["url"] or profile["url"],
                        "First Name": profile_data["first_name"],
                        "Last Name": profile_data["last_name"]
                    }
                    
                    # Store company domain if found
                    if profile_data["company_domain"]:
                        profile_info["Company Domain"] = profile_data["company_domain"]
                        profile_debug["domain_found"] = True
                        debug_info["domains_found"] += 1
                    
                    # Store email if found
                    if profile_data["email"]:
                        profile_info["Email"] = profile_data["email"]
                        profile_info["Email Source"] = profile_data["email_source"]
                        profile_debug["email_found"] = True
                        profile_debug["email_source"] = profile_data["email_source"]
                        debug_info["emails_found"] += 1
                        
                        # Count email sources for stats
                        if profile_data["email_source"] in debug_info["email_sources"]:
                            debug_info["email_sources"][profile_data["email_source"]] += 1
                    
                    # Add to collection of all profiles regardless of email
                    all_profiles.append(profile_info)
                    
                    # Add to leads if email found
                    if "Email" in profile_info and profile_info["Email"]:
                        leads.append(profile_info)
                    
                    # Update progress
                    progress = (i + 1) / len(profiles)
                    progress_bar.progress(progress)
                    
                    # Show interim results
                    if leads:
                        results_placeholder.dataframe(pd.DataFrame(leads))
            except Exception as e:
                err_msg = f"Error processing {profile['name']}: {str(e)}"
                st.error(err_msg)
                profile_debug["errors"].append(err_msg)
                debug_info["errors"].append(err_msg)
            
            # Add profile debug info
            debug_info["profile_details"].append(profile_debug)
        
        # Store debug info in session state
        st.session_state.debug_info = debug_info
        
        # Show all profiles even if no email found
        if all_profiles:
            all_df = pd.DataFrame(all_profiles)
            st.session_state.all_profiles_df = all_df
            
            # Display profiles with domains but no emails
            has_domain_col = "Company Domain" in all_df.columns
            has_email_col = "Email" in all_df.columns
            
            if has_domain_col and has_email_col:
                domains_no_emails = all_df[all_df["Company Domain"].notna() & all_df["Email"].isna()]
                if not domains_no_emails.empty:
                    st.warning(f"Found {len(domains_no_emails)} profiles with company domains but couldn't generate valid emails")
            
            # Display profiles with no domains
            if has_domain_col:
                no_domains = all_df[all_df["Company Domain"].isna()]
                if not no_domains.empty:
                    st.warning(f"Found {len(no_domains)} profiles but couldn't extract company domains")
        
        # Final results for leads with emails
        if leads:
            df = pd.DataFrame(leads)
            st.session_state.leads_df = df
            
            # Count by source
            source_counts = {
                "dns_verification": debug_info["email_sources"].get("dns_verification", 0),
                "pattern_generation": debug_info["email_sources"].get("pattern_generation", 0),
                "github": debug_info["email_sources"].get("github", 0),
                "fallback": debug_info["email_sources"].get("fallback", 0),
                "proxycurl": debug_info["email_sources"].get("proxycurl", 0)
            }
            
            success_message = f"🎉 Successfully extracted {len(leads)} leads with emails out of {len(profiles)} profiles!"
            source_info = ", ".join([f"{count} from {source}" for source, count in source_counts.items() if count > 0])
            if source_info:
                success_message += f" ({source_info})"
            
            st.success(success_message)
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
            # Show all profiles anyway
            if all_profiles:
                st.warning(f"Found {len(all_profiles)} profiles but couldn't extract valid email addresses.")
                st.dataframe(pd.DataFrame(all_profiles))
                
                # Download button for all profiles
                csv = pd.DataFrame(all_profiles).to_csv(index=False)
                st.download_button(
                    label="📥 Download All Profiles CSV",
                    data=csv,
                    file_name="linkedin_profiles.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No valid leads or profiles found. Try different search parameters.")
            
    except Exception as e:
        st.error(f"❌ Extraction failed: {str(e)}")
        debug_info["errors"].append(f"Extraction failed: {str(e)}")
        st.session_state.debug_info = debug_info
    finally:
        if 'driver' in locals() and driver:
            driver.quit()

def send_email_campaign(template):
    """Send email campaign to collected leads"""
    st.subheader("Email Campaign")
    
    # Add email subject field with variable placeholders explanation
    st.markdown("Available variables: `{name}`, `{first_name}`, `{last_name}`, `{company}`")
    default_subject = "Opportunity with {company}"
    email_subject = st.text_input("Email Subject", value=default_subject,
                                help="You can use variables like {name}, {first_name}, etc.")
    
    # Add test email options
    test_email_mode = st.radio(
        "Testing Mode",
        ["Send to actual emails", "Send to test email only", "BCC test email"],
        help="Choose how to handle test emails"
    )
    
    test_email = "int.vishrut@sumerudigital.com"
    
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
                            
                            # Replace variables in subject
                            subject = email_subject
                            for var, field in {
                                "{name}": "Name",
                                "{first_name}": "First Name",
                                "{last_name}": "Last Name",
                                "{company}": "Company Domain"
                            }.items():
                                if field in row and not pd.isna(row[field]):
                                    value = row[field]
                                    # For company, try to get just the company name without extension
                                    if field == "Company Domain" and "." in value:
                                        value = value.split('.')[0]
                                    subject = subject.replace(var, value)
                            
                            # Handle different test email modes
                            if test_email_mode == "Send to test email only":
                                recipient = test_email
                                # Add original recipient in subject for testing purposes
                                subject = f"Test: {row['Email']} - {subject}"
                            else:
                                recipient = row["Email"]
                                
                            msg['To'] = recipient
                            msg['Subject'] = subject
                            
                            # Add BCC if in BCC mode
                            if test_email_mode == "BCC test email":
                                msg['Bcc'] = test_email
                            
                            # Format template with available data
                            body = template
                            
                            # Replace variables in template using the same method
                            for var, field in {
                                "{name}": "Name",
                                "{first_name}": "First Name",
                                "{last_name}": "Last Name",
                                "{company}": "Company Domain"
                            }.items():
                                if field in row and not pd.isna(row[field]):
                                    value = row[field]
                                    # For company, try to get just the company name without extension
                                    if field == "Company Domain" and "." in value:
                                        value = value.split('.')[0]
                                    body = body.replace(var, value)
                            
                            msg.attach(MIMEText(body, 'plain'))
                            
                            server.send_message(msg)
                            success_count += 1
                            
                            # Add a short delay between emails to avoid being flagged as spam
                            if test_email_mode != "Send to test email only":
                                time.sleep(1)
                        except Exception as e:
                            st.warning(f"Failed to send to {row['Email']}: {str(e)}")
                    
                    if test_email_mode == "Send to test email only":
                        st.success(f"✅ Successfully sent {success_count} test emails to {test_email}!")
                    elif test_email_mode == "BCC test email":
                        st.success(f"✅ Successfully sent {success_count} emails with BCC to {test_email}!")
                    else:
                        st.success(f"✅ Successfully sent {success_count} emails!")
        except Exception as e:
            st.error(f"❌ Email sending failed: {str(e)}")

if __name__ == "__main__":
    main()