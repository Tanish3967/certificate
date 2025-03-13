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
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# Auto-assign role based on email
def determine_role(email):
    if email.startswith("220") and email.endswith("@kiit.ac.in"):
        return "Student"
    else:
        return "Faculty"

# Save user to database
def save_user(name, email):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute("SELECT role, leave_balance FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user:
        role = determine_role(email)
        leave_balance = 20 if role == "Student" else 30
        cursor.execute(
            "INSERT INTO users (name, email, role, leave_balance) VALUES (?, ?, ?, ?)",
            (name, email, role, leave_balance)
        )
        conn.commit()
    conn.close()

# Get user role and leave balance
def get_user_info(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, leave_balance FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user if user else ("Unknown", 0)

# Apply for leave
def request_leave(email, leave_type, start_date, end_date, reason, leave_days):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check leave balance
    cursor.execute("SELECT leave_balance FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return "⚠️ User not found!"

    available_leaves = result[0]
    
    if available_leaves < leave_days:
        conn.close()
        return f"❌ Not enough leaves! Only {available_leaves} left."

    # Deduct leave days
    new_leave_balance = available_leaves - leave_days
    cursor.execute("UPDATE users SET leave_balance = ? WHERE email = ?", (new_leave_balance, email))

    # Insert leave request
    cursor.execute(
        "INSERT INTO leave_requests (email, leave_type, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, ?, ?)",
        (email, leave_type, start_date, end_date, reason, "Pending"),
    )

    conn.commit()
    conn.close()
    return f"✅ Leave request submitted! {new_leave_balance} days remaining."

# Streamlit UI
st.title("🎓 Google Sign-In, Certificate & Leave System")

# Google OAuth Login
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

    save_user(user_name, user_email)  # Save user if not exists
    role, leave_balance = get_user_info(user_email)

    # Update session for role & leave balance
    st.session_state["role"] = role
    st.session_state["leave_balance"] = leave_balance

    # Display user info
    st.success(f"✅ Logged in as {user_name} ({user_email})")
    st.info(f"**Role: {role}** | 🏖 **Remaining Leave Balance: {leave_balance} days**")

    # Generate Certificate
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

            # **🔄 Fix UI Update: Refresh Leave Balance After Submission**
            role, updated_leave_balance = get_user_info(user_email)
            st.session_state["leave_balance"] = updated_leave_balance

    # **🔵 Display Updated Leave Balance in Blue Banner**
    st.info(f"🔹 **Updated Leave Balance: {st.session_state.get('leave_balance', leave_balance)} days**")
