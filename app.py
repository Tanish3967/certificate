import streamlit as st
import sqlite3
import requests
from requests_oauthlib import OAuth2Session
from PIL import Image
from io import BytesIO
from reportlab.pdfgen import canvas

# Load Secrets from streamlit secrets.toml
CLIENT_ID = st.secrets["oauth"]["client_id"]
CLIENT_SECRET = st.secrets["oauth"]["client_secret"]
REDIRECT_URI = st.secrets["oauth"]["redirect_uri"]

# OAuth URLs
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

DB_FILE = "users.db"

# Connect to database
def get_db_connection():
    return sqlite3.connect(DB_FILE)

# Save user to database
def save_user(name, email, role):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Assign leave balance if user doesn't exist
    leave_balance = 20 if role == "Student" else 30
    cursor.execute(
        "INSERT OR IGNORE INTO users (name, email, role, total_leaves) VALUES (?, ?, ?, ?)",
        (name, email, role, leave_balance)
    )
    
    conn.commit()
    conn.close()

# Get role and leave balance
def get_user_info(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, total_leaves FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    return user if user else ("Unknown", 0)

# Apply for leave
def request_leave(email, leave_type, start_date, end_date, reason, leave_days):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check current leave balance
    cursor.execute("SELECT total_leaves FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        return "❌ User not found."
    
    total_leaves = user[0]

    if leave_days > total_leaves:
        return "❌ Not enough leave balance!"

    # Deduct leave balance
    new_balance = total_leaves - leave_days
    cursor.execute("UPDATE users SET total_leaves = ? WHERE email = ?", (new_balance, email))
    
    # Insert leave request
    cursor.execute(
        "INSERT INTO leave_requests (email, leave_type, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, ?, ?)",
        (email, leave_type, start_date, end_date, reason, "Pending")
    )
    
    conn.commit()
    conn.close()
    
    return f"✅ Leave request submitted! Remaining leave balance: {new_balance} days"

# Google OAuth login
st.title("🎓 Google Sign-In, Certificate & Leave System")

if "token" not in st.session_state:
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=["openid", "email", "profile"])
    authorization_url, state = google.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline")
    st.session_state["oauth_state"] = state
    st.markdown(f"[🔑 Login with Google]({authorization_url})", unsafe_allow_html=True)

if "code" in st.query_params:
    code = st.query_params["code"]
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=st.session_state["oauth_state"])
    
    try:
        token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, code=code)
        st.session_state["token"] = token

        user_info = requests.get(USER_INFO_URL, headers={"Authorization": f"Bearer {token['access_token']}"}).json()
        st.session_state["user"] = user_info
    except Exception as e:
        st.error(f"OAuth Error: {e}")

# Show user info
if "user" in st.session_state:
    user = st.session_state["user"]
    user_email = user["email"]
    user_name = user["name"]
    
    role, leave_balance = get_user_info(user_email)

    save_user(user_name, user_email, role)

    st.success(f"✅ Logged in as {user_name} ({user_email})")
    st.info(f"**Role: {role}** | 🏖 **Remaining Leave Balance: {leave_balance} days**")

    if st.button("Generate Certificate"):
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer)
        c.setFont("Helvetica", 30)
        c.drawString(200, 700, "Certificate of Achievement")
        c.setFont("Helvetica", 20)
        c.drawString(220, 650, f"Awarded to: {user_name}")
        c.setFont("Helvetica", 15)
        c.drawString(220, 600, f"Role: {role}")
        c.save()
        
        pdf_buffer.seek(0)
        st.download_button(label="📄 Download Certificate", data=pdf_buffer, file_name="certificate.pdf", mime="application/pdf")

    # Leave Application Form
    st.subheader("🏖 Apply for Leave")
    leave_type = st.selectbox("Leave Type", ["Sick Leave", "Casual Leave", "Vacation"])
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    reason = st.text_area("Reason for Leave")

    leave_days = (end_date - start_date).days + 1

    if st.button("Submit Leave Request"):
        if leave_days <= 0:
            st.error("❌ Invalid leave dates.")
        else:
            message = request_leave(user_email, leave_type, start_date, end_date, reason, leave_days)
            st.success(message)
