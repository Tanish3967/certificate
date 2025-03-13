import streamlit as st
import requests
from requests_oauthlib import OAuth2Session
from PIL import Image
from io import BytesIO
from reportlab.pdfgen import canvas

# Google OAuth2 Config
CLIENT_ID = "141742353498-5geiqu2biuf2s81klgau6qjsjve9fcrc.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "https://certificate-generator-1.streamlit.app/"
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

# Streamlit UI
st.title("🎓 Google Sign-In & Certificate Generator")

# Step 1: Generate Google OAuth2 Login URL
if "token" not in st.session_state:
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=[
        "openid", "email", "profile"
    ])
    authorization_url, state = google.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline")
    st.session_state["oauth_state"] = state
    st.markdown(f"[Login with Google]({authorization_url})", unsafe_allow_html=True)

# Step 2: Handle OAuth Callback
if "code" in st.query_params:
    code = st.query_params["code"]
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=st.session_state["oauth_state"])
    
    try:
        token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, code=code)
        st.session_state["token"] = token

        # Fetch user info
        user_info = requests.get(USER_INFO_URL, headers={"Authorization": f"Bearer {token['access_token']}"}).json()
        st.session_state["user"] = user_info
    except Exception as e:
        st.error(f"OAuth Error: {e}")

# Step 3: Display User Info & Generate Certificate
if "user" in st.session_state:
    user = st.session_state["user"]
    st.success(f"✅ Logged in as {user['name']} ({user['email']})")
    
    # User profile image
    image_url = user.get("picture", "")
    if image_url:
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        st.image(img, width=100, caption="Google Profile Picture")

    # Certificate Generation
    st.subheader("🎓 Generate Your Certificate")
    name = st.text_input("Enter Your Name", value=user["name"])
    
    if st.button("Generate Certificate"):
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer)
        c.setFont("Helvetica", 30)
        c.drawString(200, 700, f"Certificate of Achievement")
        c.setFont("Helvetica", 20)
        c.drawString(220, 650, f"Awarded to: {name}")
        c.save()

        pdf_buffer.seek(0)
        st.download_button(label="📄 Download Certificate", data=pdf_buffer, file_name="certificate.pdf", mime="application/pdf")
