import streamlit as st
import requests
import sqlite3
import os
from requests_oauthlib import OAuth2Session
from PIL import Image
from io import BytesIO
from reportlab.pdfgen import canvas

# Load Secrets
CLIENT_ID = st.secrets["oauth"]["client_id"]
CLIENT_SECRET = st.secrets["oauth"]["client_secret"]
REDIRECT_URI = st.secrets["oauth"]["redirect_uri"]
DB_FILE = st.secrets["database"]["db_path"]

# Google OAuth2 URLs
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

# Database Setup
def init_db():
    """Initialize the database and create necessary tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            role TEXT,
            leave_balance INTEGER DEFAULT 10
        )
    ''')

    # Create leave_requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            leave_type TEXT,
            start_date TEXT,
            end_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

# Initialize the database
init_db()

def save_user(name, email, role):
    """Save user details in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        # Insert new user
        leave_balance = 10 if role == "Student" else 20
        cursor.execute("INSERT INTO users (name, email, role, leave_balance) VALUES (?, ?, ?, ?)", 
                       (name, email, role, leave_balance))
        conn.commit()

    conn.close()

def get_role(email):
    """Determine if the email belongs to a Student or Faculty."""
    if email.startswith("220") and email.endswith("@kiit.ac.in"):
        return "Student"
    elif email.endswith("@kiit.ac.in"):
        return "Faculty"
    return "Unknown"

def get_user_leave_balance(email):
    """Retrieve user's leave balance from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT leave_balance FROM users WHERE email = ?", (email,))
    leave_balance = cursor.fetchone()
    conn.close()
    
    return leave_balance[0] if leave_balance else None

def apply_leave(email, leave_type, start_date, end_date, reason):
    """Apply for leave and deduct leave balance if available."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Get user ID and leave balance
    cursor.execute("SELECT id, leave_balance FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return "User not found"

    user_id, leave_balance = user

    # Check if leave balance is sufficient
    if leave_balance <= 0:
        conn.close()
        return "Insufficient leave balance"

    # Insert leave request
    cursor.execute("INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, reason) VALUES (?, ?, ?, ?, ?)", 
                   (user_id, leave_type, start_date, end_date, reason))
    
    # Deduct leave balance
    cursor.execute("UPDATE users SET leave_balance = leave_balance - 1 WHERE id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    
    return "Leave request submitted successfully"

# Streamlit UI
st.title("🎓 Google Sign-In, Certificate & Leave System")

# Step 1: Generate Google OAuth2 Login URL
if "token" not in st.session_state:
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=["openid", "email", "profile"])
    authorization_url, state = google.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline")
    st.session_state["oauth_state"] = state
    st.markdown(f"[🔑 Login with Google]({authorization_url})", unsafe_allow_html=True)

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

# Step 3: Display User Info, Role & Leave System
if "user" in st.session_state:
    user = st.session_state["user"]
    user_email = user["email"]
    user_name = user["name"]
    user_role = get_role(user_email)

    # Save user in DB
    save_user(user_name, user_email, user_role)

    st.success(f"✅ Logged in as {user_name} ({user_email})")
    st.info(f"**Role: {user_role}**")

    # Fetch leave balance
    leave_balance = get_user_leave_balance(user_email)
    st.info(f"**Remaining Leave Balance: {leave_balance} days**")

    # Leave Request Section
    st.subheader("📅 Apply for Leave")
    leave_type = st.selectbox("Select Leave Type", ["Sick Leave", "Casual Leave", "Emergency Leave"])
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    reason = st.text_area("Reason for Leave")

    if st.button("Submit Leave Request"):
        response = apply_leave(user_email, leave_type, str(start_date), str(end_date), reason)
        st.success(response)

    # Certificate Generation Section
    st.subheader("🎓 Generate Your Certificate")
    name = st.text_input("Enter Your Name", value=user_name)
    
    if st.button("Generate Certificate"):
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer)
        c.setFont("Helvetica", 30)
        c.drawString(200, 700, f"Certificate of Achievement")
        c.setFont("Helvetica", 20)
        c.drawString(220, 650, f"Awarded to: {name}")
        c.setFont("Helvetica", 15)
        c.drawString(220, 600, f"Role: {user_role}")
        c.save()

        pdf_buffer.seek(0)
        st.download_button(label="📄 Download Certificate", data=pdf_buffer, file_name="certificate.pdf", mime="application/pdf")
