from flask import Flask, request, jsonify, send_file
import sqlite3
import os
import datetime
import pandas as pd
import json
import time
import PyPDF2
import streamlit as st
from groq import Groq
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

# Load secrets from Streamlit secrets.toml
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# Initialize Flask App & Groq Client
app = Flask(__name__)
client = Groq(api_key=GROQ_API_KEY)

# Create templates directory if it doesn't exist
TEMPLATES_DIR = os.path.join(os.getcwd(), "templates")
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

# ✅ Database Connection
def get_db_connection():
    conn = sqlite3.connect("leave_management.db", timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

# ✅ Create Tables If Not Exists
def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            mentor_id TEXT,
            days INTEGER,
            start_date TEXT DEFAULT CURRENT_DATE,
            end_date TEXT,
            status TEXT CHECK(status IN ('pending', 'approved', 'rejected'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mentor_assignments (
            student_id TEXT PRIMARY KEY,
            mentor_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS academic_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT
        )
    """)

    # New table for certificate templates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS certificate_templates (
            template_type TEXT PRIMARY KEY,
            file_path TEXT
        )
    """)

    conn.commit()
    conn.close()

initialize_db()

# ✅ Assign Mentor API
@app.route("/assign-mentor", methods=["POST"])
def assign_mentor():
    data = request.json
    student_id = data["student_id"]
    mentor_id = data["mentor_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO mentor_assignments (student_id, mentor_id) VALUES (?, ?)", (student_id, mentor_id))
    conn.commit()
    conn.close()

    return jsonify({"message": f"✅ Assigned Mentor {mentor_id} to Student {student_id}."})

# ✅ Request Leave API (Auto-approve if ≤ 5 days)
@app.route("/leave", methods=["POST"])
def process_leave():
    data = request.json
    student_id = data["student_id"]
    days = data["days"]
    start_date = datetime.date.today().strftime("%Y-%m-%d")
    end_date = (datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mentor_id FROM mentor_assignments WHERE student_id = ?", (student_id,))
    mentor = cursor.fetchone()

    if days <= 5:
        status = "approved"
        mentor_id = "Auto-Approved"
    elif mentor:
        status = "pending"
        mentor_id = mentor["mentor_id"]
    else:
        conn.close()
        return jsonify({"message": "❌ No mentor found for this student."}), 400

    cursor.execute("""
        INSERT INTO leave_requests (student_id, mentor_id, days, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, mentor_id, days, start_date, end_date, status))

    conn.commit()
    conn.close()

    return jsonify({"message": f"✅ Leave request for {days} days sent to {mentor_id}. Status: {status}."})

# ✅ Fetch Student Leave Requests
@app.route("/student-leave-status", methods=["GET"])
def student_leave_status():
    student_id = request.args.get("student_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mentor_id, days, start_date, end_date, status FROM leave_requests WHERE student_id = ?", (student_id,))
    requests = cursor.fetchall()
    conn.close()

    return jsonify({"requests": [dict(req) for req in requests]})

# ✅ Fetch Mentor Leave Requests
@app.route("/mentor-leave-requests", methods=["GET"])
def mentor_leave_requests():
    mentor_id = request.args.get("mentor_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, student_id, days, start_date, end_date, status FROM leave_requests WHERE mentor_id = ? AND status = 'pending'", (mentor_id,))
    requests = cursor.fetchall()
    conn.close()

    return jsonify({"requests": [dict(req) for req in requests]})

# ✅ AI-Based Academic Query Handling
@app.route("/ask-academic-query", methods=["POST"])
def ask_academic_query():
    data = request.json
    query = data.get("query", "")
    response = client.chat_completion(query)
    return jsonify({"response": response})

# ✅ Upload Academic Document for Training AI
@app.route("/upload-academic-doc", methods=["POST"])
def upload_academic_doc():
    file = request.files["file"]
    if not file:
        return jsonify({"message": "No file uploaded."}), 400
    
    content = file.read().decode("utf-8")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO academic_docs (content) VALUES (?)", (content,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "✅ Document uploaded successfully."})

# ✅ Generate Certificate PDF
@app.route("/generate-certificate", methods=["POST"])
def generate_certificate():
    data = request.json
    student_name = data["student_name"]
    certificate_type = data["certificate_type"]
    output = io.BytesIO()
    
    c = canvas.Canvas(output, pagesize=letter)
    c.drawString(100, 700, f"Certificate of {certificate_type}")
    c.drawString(100, 650, f"Awarded to {student_name}")
    c.save()
    
    output.seek(0)
    return send_file(output, download_name=f"{certificate_type}_{student_name}.pdf", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
