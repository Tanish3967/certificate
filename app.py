import streamlit as st
import requests
import json
from urllib.parse import urlencode
from requests_oauthlib import OAuth2Session
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# GOOGLE OAUTH CONFIG
CLIENT_ID = "141742353498-5geiqu2biuf2s81klgau6qjsjve9fcrc.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "https://certificate-generator-1.streamlit.app"

AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

SCOPE = ["openid", "email", "profile"]

st.title("Google Sign-In & Certificate Generator")

# OAuth2 Session
oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)
authorization_url, state = oauth.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline", prompt="consent")

# Show login button if user is not authenticated
if "oauth_token" not in st.session_state:
    st.markdown(f"[Login with Google]({authorization_url})")

# Capture OAuth callback
query_params =  st.experimental_get_query_params()
if "code" in query_params:
    code = query_params["code"][0]

    # Exchange authorization code for access token
    token = oauth.fetch_token(
        TOKEN_URL,
        client_secret=CLIENT_SECRET,
        code=code
    )

    # Store token in session
    st.session_state["oauth_token"] = token

# Fetch User Info
if "oauth_token" in st.session_state:
    oauth = OAuth2Session(CLIENT_ID, token=st.session_state["oauth_token"])
    response = oauth.get(USER_INFO_URL)
    user_info = response.json()

    st.subheader("User Info:")
    st.image(user_info["picture"], width=100)
    st.write(f"**Name:** {user_info['name']}")
    st.write(f"**Email:** {user_info['email']}")

    # Function to generate certificate
    def generate_certificate(name):
        pdf_filename = f"{name}_certificate.pdf"
        c = canvas.Canvas(pdf_filename, pagesize=letter)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(100, 700, "Certificate of Completion")
        c.setFont("Helvetica", 18)
        c.drawString(100, 650, f"This is to certify that {name}")
        c.drawString(100, 620, "has successfully completed the course.")
        c.save()
        return pdf_filename

    # Generate Certificate Button
    if st.button("Generate Certificate"):
        pdf_file = generate_certificate(user_info["name"])

        with open(pdf_file, "rb") as file:
            st.download_button(
                label="Download Certificate",
                data=file,
                file_name=pdf_file,
                mime="application/pdf"
            )

    # Logout button
    if st.button("Logout"):
        del st.session_state["oauth_token"]
        st.rerun()

