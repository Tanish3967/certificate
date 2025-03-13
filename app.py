import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

# Sample inbuilt data
data = {
    "12345": {"name": "John Doe", "role": "Student", "cert_type": "Bonafide"},
    "67890": {"name": "Jane Smith", "role": "Employee", "cert_type": "NOC"},
}

def generate_certificate(user_id):
    if user_id not in data:
        return None

    user = data[user_id]
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    pdf.setFont("Helvetica", 16)
    pdf.drawString(100, 700, f"{user['cert_type']} Certificate")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 650, f"This is to certify that {user['name']} ({user_id})")
    pdf.drawString(100, 630, f"is a {user['role']}.")
    
    pdf.save()
    buffer.seek(0)
    return buffer

st.title("AI Certificate Generator")
user_id = st.text_input("Enter User ID:")

if st.button("Generate Certificate"):
    pdf_buffer = generate_certificate(user_id)
    if pdf_buffer:
        st.success("Certificate Generated Successfully!")
        st.download_button(
            label="Download Certificate",
            data=pdf_buffer,
            file_name=f"{user_id}_certificate.pdf",
            mime="application/pdf"
        )
    else:
        st.error("User ID not found!")
