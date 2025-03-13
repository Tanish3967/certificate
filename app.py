import streamlit as st
import sqlite3
import requests
from requests_oauthlib import OAuth2Session
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, landscape
from datetime import datetime
import pytz

# Initialize session state variables
if "role" not in st.session_state:
    st.session_state.role = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "show_leave_form" not in st.session_state:
    st.session_state.show_leave_form = False
if "show_cert_form" not in st.session_state:
    st.session_state.show_cert_form = False
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
    
    # Update session state with new balance
    st.session_state.leave_balance = new_leave_balance
    
    return f"✅ Leave request submitted! {new_leave_balance} leaves remaining."

# Generate certificate based on type with IST timestamp
def generate_certificate(user_name, user_role, cert_type):
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=landscape(A4))
    
    # Get current IST timestamp
    ist_timezone = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist_timezone)
    formatted_date = current_time.strftime("%B %d, %Y, %I:%M %p IST")
    
    # Set up the certificate based on type
    if cert_type == "NOC":
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(420, 400, "No Objection Certificate")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"This is to certify that")
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(420, 320, f"{user_name}")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 290, f"has no objection from the institution")
        c.drawCentredString(420, 260, f"to pursue further studies or employment.")
    
    elif cert_type == "Bonafide":
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(420, 400, "Bonafide Certificate")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"This is to certify that")
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(420, 320, f"{user_name}")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 290, f"is a bonafide student of this institution")
        c.drawCentredString(420, 260, f"for the academic year 2024-2025.")
    
    elif cert_type == "Leaving":
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(420, 400, "Leaving Certificate")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"This is to certify that")
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(420, 320, f"{user_name}")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 290, f"has completed all requirements")
        c.drawCentredString(420, 260, f"and is permitted to leave the institution.")
    
    else:  # Achievement Certificate (default)
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(420, 400, "Certificate of Achievement")
        c.setFont("Helvetica", 20)
        c.drawCentredString(420, 350, f"Awarded to:")
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(420, 320, f"{user_name}")
        c.setFont("Helvetica", 18)
        c.drawCentredString(420, 290, f"Role: {user_role}")
    
    # Add date and signature with IST timestamp
    c.setFont("Helvetica", 12)
    c.drawCentredString(420, 200, f"Date: {formatted_date}")
    c.drawCentredString(420, 150, "____________________")
    c.drawCentredString(420, 130, "Principal's Signature")
    
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer

# Initialize database
initialize_db()

# Reset function
def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()
    st.rerun()

# UI Title
st.title("🎓 Role-Based Sign-In & Leave System")

# Add reset button
if st.sidebar.button("Reset Session"):
    reset_app()

# Create a placeholder for the info bar
info_placeholder = st.empty()

# Check for OAuth code in URL
if "code" in st.query_params and not st.session_state.authenticated:
    try:
        # Create OAuth session
        google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
        
        # Exchange code for token
        token = google.fetch_token(
            TOKEN_URL,
            client_secret=CLIENT_SECRET,
            code=st.query_params["code"]
        )
        
        # Get user info
        user_info = requests.get(
            USER_INFO_URL,
            headers={"Authorization": f"Bearer {token['access_token']}"}
        ).json()
        
        # Store in session state
        st.session_state.user = user_info
        st.session_state.authenticated = True
        
        # Clear the URL parameters
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"OAuth Error: {e}")
        st.query_params.clear()

# Role Selection - Only show if not authenticated
if not st.session_state.authenticated and not st.session_state.admin_logged_in:
    if st.session_state.role is None:
        role_options = ["Student", "Teacher", "Admin"]
        selected_role = st.selectbox("Select your role:", role_options)
        
        if st.button("Continue"):
            st.session_state.role = selected_role
            st.rerun()
    
    # Show appropriate login method based on role
    if st.session_state.role == "Admin":
        # Admin Manual Login
        with st.form("admin_login"):
            st.subheader("Admin Login")
            admin_username = st.text_input("Username")
            admin_password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
        
        if submit:
            if admin_username == "admin" and admin_password == "admin123":
                st.session_state.admin_logged_in = True
                st.success("✅ Admin login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid admin credentials")
    
    elif st.session_state.role in ["Student", "Teacher"]:
        # Google OAuth Login - with fixes for invalid_grant error
        flow = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=["openid", "email", "profile"])
        authorization_url, state = flow.authorization_url(
            AUTHORIZATION_BASE_URL,
            access_type="offline",
            prompt="consent",  # Force to show the consent screen every time
            include_granted_scopes="true"
        )
        
        st.markdown(f"[🔑 Login with Google]({authorization_url})", unsafe_allow_html=True)

# Display appropriate dashboard based on authentication status
if st.session_state.authenticated and st.session_state.user:
    # Student/Teacher Dashboard
    user = st.session_state.user
    user_email = user.get("email", "")
    user_name = user.get("name", "")
    
    # Determine role based on email pattern
    role = "Student" if user_email.startswith("220") and "@kiit.ac.in" in user_email else "Teacher"
    
    # Save user to database
    save_user(user_name, user_email, role)
    
    # Get updated user info
    user_role, leave_balance = get_user_info(user_email)
    st.session_state.leave_balance = leave_balance
    
    # Display user info using the placeholder
    info_placeholder.info(f"**Role: {user_role}** | 🏖 **Remaining Leave Balance: {st.session_state.leave_balance} days**")
    
    # Show different features based on role
    if user_role == "Teacher":
        # For Teachers, only show leave application
        st.subheader("📅 Leave Application Form")
        
        with st.form("leave_request"):
            leave_type = st.selectbox("Leave Type", ["Sick Leave", "Casual Leave", "Vacation"])
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
            reason = st.text_area("Reason for Leave")
            submit_leave = st.form_submit_button("Submit Leave Request")
        
        if submit_leave:
            if end_date < start_date:
                st.error("❌ Invalid date range")
            else:
                result = request_leave(user_email, leave_type, start_date, end_date, reason)
                st.success(result)
                # Update the info bar with new balance
                info_placeholder.info(f"**Role: {user_role}** | 🏖 **Remaining Leave Balance: {st.session_state.leave_balance} days**")
    
    else:  # For Students, show both certificate and leave application
        # Certificate Generation with toggle behavior
        if st.button("Generate Certificate"):
            st.session_state.show_cert_form = not st.session_state.show_cert_form
        
        if st.session_state.show_cert_form:
            st.subheader("📄 Certificate Generation")
            
            cert_type = st.selectbox(
                "Select Certificate Type:", 
                ["Achievement Certificate", "NOC", "Bonafide", "Leaving"]
            )
            
            if st.button("Download Certificate"):
                pdf_buffer = generate_certificate(user_name, user_role, cert_type)
                st.download_button(
                    label="📄 Download Certificate", 
                    data=pdf_buffer, 
                    file_name=f"{cert_type.lower().replace(' ', '_')}_certificate.pdf", 
                    mime="application/pdf"
                )
        
        # Leave Application
        if st.button("🏖 Apply for Leave"):
            st.session_state.show_leave_form = not st.session_state.show_leave_form
        
        if st.session_state.show_leave_form:
            st.subheader("📅 Leave Application Form")
            
            with st.form("leave_request"):
                leave_type = st.selectbox("Leave Type", ["Sick Leave", "Casual Leave", "Vacation"])
                start_date = st.date_input("Start Date")
                end_date = st.date_input("End Date")
                reason = st.text_area("Reason for Leave")
                submit_leave = st.form_submit_button("Submit Leave Request")
            
            if submit_leave:
                if end_date < start_date:
                    st.error("❌ Invalid date range")
                else:
                    result = request_leave(user_email, leave_type, start_date, end_date, reason)
                    st.success(result)
                    # Update the info bar with new balance
                    info_placeholder.info(f"**Role: {user_role}** | 🏖 **Remaining Leave Balance: {st.session_state.leave_balance} days**")

elif st.session_state.admin_logged_in:
    # Admin Dashboard
    st.subheader("👨‍💼 Admin Dashboard")
    
    # Create tabs for different admin functions
    tab1, tab2 = st.tabs(["📋 Leave Requests", "👥 User Management"])
    
    with tab1:
        st.write("### Pending Leave Requests")
        
        # Fetch leave requests
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lr.id, u.name, lr.email, lr.leave_type, lr.start_date, lr.end_date, lr.reason, lr.status
            FROM leave_requests lr
            JOIN users u ON lr.user_id = u.id
            ORDER BY lr.id DESC
        """)
        requests = cursor.fetchall()
        conn.close()
        
        if requests:
            for req in requests:
                with st.expander(f"Request #{req[0]} - {req[1]} ({req[2]})"):
                    st.write(f"**Type:** {req[3]}")
                    st.write(f"**Period:** {req[4]} to {req[5]}")
                    st.write(f"**Reason:** {req[6]}")
                    st.write(f"**Status:** {req[7]}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Approve", key=f"approve_{req[0]}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE leave_requests SET status = 'Approved' WHERE id = ?", (req[0],))
                            conn.commit()
                            conn.close()
                            st.success("Request approved!")
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ Reject", key=f"reject_{req[0]}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE leave_requests SET status = 'Rejected' WHERE id = ?", (req[0],))
                            conn.commit()
                            conn.close()
                            st.success("Request rejected!")
                            st.rerun()
        else:
            st.info("No leave requests found.")
    
    with tab2:
        st.write("### User Management")
        
        # Fetch users
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role, leave_balance FROM users ORDER BY id")
        users = cursor.fetchall()
        conn.close()
        
        if users:
            for user in users:
                with st.expander(f"{user[1]} ({user[2]})"):
                    st.write(f"**Role:** {user[3]}")
                    st.write(f"**Leave Balance:** {user[4]} days")
                    
                    # Leave balance adjustment
                    new_balance = st.number_input("Adjust Leave Balance", min_value=0, value=user[4], key=f"balance_{
