import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

# Sample inbuilt data (mock database)
data = {
    "12345": {"name": "John Doe", "role": "Student", "cert_type": "Bonafide"},
    "67890": {"name": "Jane Smith", "role": "Employee", "cert_type": "NOC"},
}

def generate_certificate(user_id):
    if user_id not in data:
        return None
    
    user = data[user_id]
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(300, 750, f"{user['cert_type']} Certificate")
    
    pdf.setFont("Helvetica", 16)
    pdf.drawString(100, 700, f"This is to certify that {user['name']}")
    pdf.drawString(100, 670, f"holding ID {user_id} is a {user['role']}.")
    
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

# Streamlit UI
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
