import streamlit as st
import sqlite3
import requests
from requests_oauthlib import OAuth2Session
from io import BytesIO
from reportlab.pdfgen import canvas
from datetime import datetime

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
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# Ensure users table exists
def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            role TEXT,
            leave_balance INTEGER DEFAULT 10
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT,
            leave_type TEXT,
            start_date TEXT,
            end_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'Pending'
        )
    """)

    conn.commit()
    conn.close()

# Save user
def save_user(name, email, role):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Assign leave balance based on role
    leave_balance = 20 if role == "Student" else 30
    cursor.execute(
        "INSERT OR IGNORE INTO users (name, email, role, leave_balance) VALUES (?, ?, ?, ?)",
        (name, email, role, leave_balance)
    )

    conn.commit()
    conn.close()

# Get role and leave balance
def get_user_info(email):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT role, leave_balance FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    return user if user else ("Unknown", 0)

# Apply for leave
def request_leave(email, leave_type, start_date, end_date, reason):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check current leave balance
    cursor.execute("SELECT id, leave_balance FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()

    if result is None:
        conn.close()
        return "⚠️ User not found!"

    user_id, available_leaves = result

    # Calculate leave days
    leave_days = (end_date - start_date).days + 1

    if available_leaves < leave_days:
        conn.close()
        return f"❌ Not enough leaves! Only {available_leaves} left."

    # Deduct leaves
    new_leave_balance = available_leaves - leave_days
    cursor.execute("UPDATE users SET leave_balance = ? WHERE email = ?", (new_leave_balance, email))

    # Insert leave request
    cursor.execute(
        "INSERT INTO leave_requests (user_id, email, leave_type, start_date, end_date, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, email, leave_type, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), reason),
    )

    conn.commit()
    conn.close()
    return f"✅ Leave request submitted! {new_leave_balance} leaves remaining."

# Initialize database
initialize_db()

# UI Title
st.title("🎓 Role-Based Sign-In & Leave System")

# Role Selection
if "role" not in st.session_state:
    role = st.selectbox("Select your role:", ["Student", "Teacher", "Admin"])
    st.session_state["role"] = role

# Google OAuth login for Students & Teachers
if st.session_state["role"] in ["Student", "Teacher"]:
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

# Manual Login for Admins Only
elif st.session_state["role"] == "Admin":
    admin_username = st.text_input("Admin Username")
    admin_password = st.text_input("Admin Password", type="password")

    if st.button("Login as Admin"):
        if admin_username == "admin" and admin_password == "admin123":
            st.session_state["admin_logged_in"] = True
            st.success("✅ Logged in as Admin!")
        else:
            st.error("❌ Incorrect admin credentials!")

# Display User Info or Admin Dashboard
if "user" in st.session_state or "admin_logged_in" in st.session_state:
    
    # For Students and Teachers Logged In via Google OAuth
    if "user" in st.session_state:
        user_email = st.session_state["user"]["email"]
        user_name = st.session_state["user"]["name"]
        
        # Assign role dynamically based on email pattern
        role_assigned = "Student" if user_email.startswith("220") and "@kiit.ac.in" in user_email else "Teacher"
        
        save_user(user_name, user_email, role_assigned)
        
        user_role, leave_balance = get_user_info(user_email)
        
        # Display User Info
        st.success(f"✅ Logged in as {user_name} ({user_email})")
        st.info(f"**Role: {user_role}** | 🏖 **Remaining Leave Balance: {leave_balance} days**")
        
        # Certificate Generation Option
        if st.button("Generate Certificate"):
            pdf_buffer = BytesIO()
            c = canvas.Canvas(pdf_buffer)
            c.setFont("Helvetica", 30)
            c.drawString(200, 700, "Certificate of Achievement")
            c.setFont("Helvetica", 20)
            c.drawString(220, 650, f"Awarded to: {user_name}")
            c.setFont("Helvetica", 15)
            c.drawString(220, 600, f"Role: {user_role}")
            c.save()

            pdf_buffer.seek(0)
            st.download_button(label="📄 Download Certificate", data=pdf_buffer, file_name="certificate.pdf", mime="application/pdf")

        # Leave Application Form Toggle
        if "show_leave_form" not in st.session_state:
            st.session_state["show_leave_form"] = False

        if st.button("🏖 Apply for Leave"):
            st.session_state["show_leave_form"] ^= True

        if st.session_state["show_leave_form"]:
            st.subheader("📅 Leave Application Form")
            
            leave_type = st.selectbox("Leave Type", ["Sick Leave", "Casual Leave", "Vacation"])
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
            
            reason_for_leave_request=st.text_area('Reason')
            
            

