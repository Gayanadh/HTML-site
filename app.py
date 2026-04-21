from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from docx.shared import Pt, Inches
import PyPDF2
import io

app = Flask(__name__)
CORS(app)

def process_pdf_upload(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files['resume']
        updates = request.form.get('updates', '')
        
        # 1. Load Content
        if file.filename.endswith('.pdf'):
            content = process_pdf_upload(file)
            doc = Document()
            for line in content.split('\n'):
                doc.add_paragraph(line)
        else:
            doc = Document(file)

        # 2. "Smart Insert" Logic (The Mini-AI)
        # We look for keywords to find the 'Professional Experience' or 'Achievements' section
        target_keywords = ['EXPERIENCE', 'ACHIEVEMENTS', 'PROJECTS', 'WORK HISTORY']
        inserted = False
        
        for paragraph in doc.paragraphs:
            para_text = paragraph.text.upper()
            if any(key in para_text for key in target_keywords):
                # Move to the next paragraph and insert the bullet point
                new_para = paragraph.insert_paragraph_before("")
                run = new_para.add_run(f"• {updates}")
                run.font.name = 'Arial'
                run.font.size = Pt(11)
                inserted = True
                break
        
        # If no standard heading is found, we create an 'ADDITIONAL ACHIEVEMENTS' section
        if not inserted:
            doc.add_heading('ADDITIONAL ACHIEVEMENTS', level=1)
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(updates).font.size = Pt(11)

        # 3. Clean up formatting for ATS (Arial/Calibri, 11pt)
        for para in doc.paragraphs:
            for run in para.runs:
                run.font.name = 'Arial'

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        return send_file(file_stream, as_attachment=True, download_name='FAANG_Optimized.docx')

    except Exception as e:
        return str(e), 500

@app.route('/upgrade-pdf', methods=['POST'])
def upgrade_pdf():
    # PDF export uses the same logic but you can use an external converter 
    # For now, let's keep the high-fidelity .docx as the main output
    return upgrade()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
