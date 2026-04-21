from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from fpdf import FPDF
import PyPDF2
import io

app = Flask(__name__)
CORS(app)

def process_pdf_upload(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files['resume']
        updates = request.form.get('updates')
        
        # Handle PDF Uploads by converting to text first
        if file.filename.endswith('.pdf'):
            existing_text = process_pdf_upload(file)
            doc = Document()
            doc.add_paragraph(existing_text)
        else:
            doc = Document(file)

        doc.add_page_break()
        p = doc.add_paragraph()
        p.add_run(f"FAANG OPTIMIZED UPDATES: {updates}").bold = True
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        return send_file(file_stream, as_attachment=True, download_name='Optimized_Resume.docx')
    except Exception as e:
        return str(e), 500

@app.route('/upgrade-pdf', methods=['POST'])
def upgrade_pdf():
    try:
        file = request.files['resume']
        updates = request.form.get('updates')

        # Extract text based on file type
        if file.filename.endswith('.pdf'):
            content = process_pdf_upload(file)
        else:
            doc = Document(file)
            content = "\n".join([p.text for p in doc.paragraphs])

        # Create PDF Output
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 10, txt=content)
        pdf.ln(10)
        pdf.set_text_color(46, 116, 181) # Your theme blue
        pdf.multi_cell(0, 10, txt=f"FAANG UPDATES: {updates}")

        pdf_output = io.BytesIO(pdf.output())
        return send_file(pdf_output, mimetype='application/pdf', as_attachment=True, download_name='FAANG_Resume.pdf')
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
