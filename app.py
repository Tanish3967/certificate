import streamlit as st
import sqlite3
import requests
from requests_oauthlib import OAuth2Session
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from datetime import datetime
import pytz

# Initialize session state variables
if "role" not in st.session_state:
    st.session_state.role = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "leave_balance" not in st.session_state:
    st.session_state.leave_balance = 0

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

# Initialize database tables if they don't exist
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

# Save user details to the database
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

# Get user role and leave balance from the database
def get_user_info(email):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT role, leave_balance FROM users WHERE email = ?", (email,))
    user_info = cursor.fetchone()
    conn.close()

    return user_info if user_info else ("Unknown", 0)

# Apply for leave and update leave balance in the database
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

    # Calculate number of leave days requested
    leave_days = (end_date - start_date).days + 1

    if available_leaves < leave_days:
        conn.close()
        return f"❌ Not enough leaves! Only {available_leaves} left."

    # Deduct leaves from the user's balance and update the database
    new_leave_balance = available_leaves - leave_days
    cursor.execute("UPDATE users SET leave_balance = ? WHERE email = ?", (new_leave_balance, email))

    # Insert the leave request into the database
    cursor.execute(
        "INSERT INTO leave_requests (user_id, email, leave_type, start_date, end_date, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, email, leave_type, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), reason),
    )

    conn.commit()
    conn.close()

    # Update session state with new balance for dynamic UI updates
    st.session_state.leave_balance = new_leave_balance

    return f"✅ Leave request submitted! {new_leave_balance} leaves remaining."

# Generate a certificate with IST timestamp based on type
def generate_certificate(user_name, user_role, cert_type):
    pdf_buffer = BytesIO()
    
    c = canvas.Canvas(pdf_buffer, pagesize=landscape(A4))
    
    # Get current IST timestamp
    ist_timezone = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist_timezone)
    
    formatted_date = current_time.strftime("%B %d, %Y at %I:%M %p IST")
    
    # Certificate content based on type
    c.setFont("Helvetica-Bold", 30)
    
    if cert_type == "NOC":
        c.drawCentredString(420, 400, "No Objection Certificate")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"This is to certify that {user_name}")
        c.drawCentredString(420, 320, f"has no objection from this institution")
        c.drawCentredString(420, 290, f"to pursue further studies or employment.")
    
    elif cert_type == "Bonafide":
        c.drawCentredString(420, 400, "Bonafide Certificate")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"This is to certify that {user_name}")
        c.drawCentredString(420, 320, f"is a bonafide student of this institution.")
    
    elif cert_type == "Leaving":
        c.drawCentredString(420, 400, "Leaving Certificate")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"This is to certify that {user_name}")
        c.drawCentredString(420, 320, f"has completed all requirements and is permitted to leave.")
    
    else:  # Default: Achievement Certificate
        c.drawCentredString(420, 400, "Certificate of Achievement")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"Awarded to: {user_name}")
    
    # Add date and signature section to all certificates
    c.setFont("Helvetica", 12)
    
