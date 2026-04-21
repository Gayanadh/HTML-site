from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from docx.shared import Pt
import PyPDF2
import io

app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(file):
    try:
        reader = PyPDF2.PdfReader(file)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except:
        return ""

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        # Safety check for file
        if 'resume' not in request.files:
            return "No file uploaded", 400
            
        file = request.files['resume']
        updates = request.form.get('updates', '').strip()
        template = request.form.get('template', 'google')
        
        # 1. Load Content
        if file.filename.endswith('.pdf'):
            raw_text = extract_text_from_pdf(file)
            doc = Document()
            for line in raw_text.split('\n'):
                doc.add_paragraph(line)
        else:
            doc = Document(file)

        # 2. AI Section Injection Logic
        target_sections = ['EXPERIENCE', 'WORK', 'HISTORY', 'ACHIEVEMENTS', 'PROJECTS', 'SUMMARY']
        success = False
        
        # Try to find a place to inject the bullet point
        for i, para in enumerate(doc.paragraphs):
            text_upper = para.text.upper()
            if any(section in text_upper for section in target_sections):
                # Insert achievement 1 paragraph after the header
                target_idx = min(i + 1, len(doc.paragraphs))
                new_p = doc.paragraphs[target_idx].insert_paragraph_before(f"• {updates}")
                new_p.runs[0].font.bold = True
                success = True
                break
        
        # 3. Fallback: If no headers found, put at top
        if not success:
            top_p = doc.paragraphs[0].insert_paragraph_before(f"KEY ACHIEVEMENT: {updates}")
            top_p.runs[0].bold = True

        # 4. Global Styling (ATS Font Standards)
        font_name = 'Arial' if template == 'amazon' else 'Calibri'
        for para in doc.paragraphs:
            for run in para.runs:
                run.font.name = font_name
                run.font.size = Pt(11)

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        return send_file(
            file_stream, 
            as_attachment=True, 
            download_name='AI_FAANG_Resume.docx'
        )
    except Exception as e:
        print(f"Error encountered: {str(e)}")
        return f"Internal Server Error: {str(e)}", 500

@app.route('/upgrade-pdf', methods=['POST'])
def upgrade_pdf():
    return upgrade()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
