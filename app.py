import os
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from docx import Document
from fpdf import FPDF
import PyPDF2  # Make sure this is in requirements.txt
import io

app = Flask(__name__)
CORS(app)

def get_pdf_text(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files.get('resume')
        updates = request.form.get('updates', '')
        requested_format = request.form.get('format', 'docx')

        if not file:
            return "No file uploaded", 400

        # --- STEP 1: LOAD CONTENT SAFELY ---
        full_text = ""
        
        if file.filename.lower().endswith('.pdf'):
            # Extract text from PDF
            full_text = get_pdf_text(file)
            doc = Document() # Create a new doc to hold the text
            doc.add_paragraph(full_text)
        else:
            # Open as Word Document
            doc = Document(file)

        # --- STEP 2: INJECT UPDATES ---
        # We add it at the top to ensure it doesn't get lost in your text boxes
        if updates:
            p = doc.paragraphs[0].insert_paragraph_before()
            run = p.add_run(f"AI-OPTIMIZED UPDATE: {updates}")
            run.bold = True
            doc.add_paragraph("-" * 30)

        # --- STEP 3: WORD EXPORT (Keeps your original formatting) ---
        if requested_format == 'docx':
            target_stream = io.BytesIO()
            doc.save(target_stream)
            target_stream.seek(0)
            return send_file(
                target_stream,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name="Optimized_Resume.docx"
            )

        # --- STEP 4: PDF EXPORT (Simple Text-Based Version) ---
        elif requested_format == 'pdf':
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=10)
            
            for para in doc.paragraphs:
                if para.text.strip():
                    # Strip special characters that crash PDF generation
                    clean_text = para.text.encode('ascii', 'ignore').decode('ascii')
                    pdf.multi_cell(0, 8, txt=clean_text)
                    pdf.ln(2)
            
            pdf_bytes = pdf.output()
            pdf_output = io.BytesIO(pdf_bytes)
            pdf_output.seek(0)

            return send_file(
                pdf_output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name="Optimized_Resume.pdf"
            )

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
