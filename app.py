import streamlit as st
from weasyprint import HTML
from io import BytesIO

# Sample inbuilt data (mock database)
data = {
    "12345": {"name": "John Doe", "role": "Student", "cert_type": "Bonafide"},
    "67890": {"name": "Jane Smith", "role": "Employee", "cert_type": "NOC"},
}

# Function to generate PDF using WeasyPrint
def generate_certificate(user_id):
    if user_id not in data:
        return None

    user = data[user_id]

    # HTML template for the certificate
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; }}
            .title {{ font-size: 24px; font-weight: bold; }}
            .content {{ font-size: 18px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="title">{user['cert_type']} Certificate</div>
        <div class="content">
            This is to certify that <b>{user['name']}</b> <br>
            holding ID <b>{user_id}</b> is a <b>{user['role']}</b>.
        </div>
    </body>
    </html>
    """

    # Convert HTML to PDF
    pdf_bytes = HTML(string=html_content).write_pdf()

    return BytesIO(pdf_bytes)

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
