import streamlit as st
import requests
from oauthlib.oauth2 import WebApplicationClient
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

# Google OAuth Credentials
GOOGLE_CLIENT_ID = "141742353498-5geiqu2biuf2s81klgau6qjsjve9fcrc.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

def generate_certificate(user_name):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Helvetica", 16)
    pdf.drawString(100, 700, f"Certificate of Participation")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 650, f"This certifies that {user_name} has successfully participated.")
    pdf.save()
    buffer.seek(0)
    return buffer

st.title("AI Certificate Generator")

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri="https://certificate-generator-1.streamlit.app",
        scope=["openid", "email", "profile"],
    )
    
    st.markdown(f"[Login with Google]({request_uri})")
else:
    st.success(f"Welcome, {st.session_state.user['name']}!")

    if st.button("Generate Certificate"):
        pdf_buffer = generate_certificate(st.session_state.user["name"])
        st.download_button(
            label="Download Certificate",
            data=pdf_buffer,
            file_name="certificate.pdf",
            mime="application/pdf"
        )
