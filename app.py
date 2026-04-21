from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from docx.shared import Pt
import PyPDF2
import io

app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join([page.extract_text() for page in reader.pages])

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files['resume']
        new_achievement = request.form.get('updates', '').strip()
        
        # 1. Initialize Document Logic
        if file.filename.endswith('.pdf'):
            raw_text = extract_text_from_pdf(file)
            doc = Document()
            for line in raw_text.split('\n'):
                doc.add_paragraph(line)
        else:
            doc = Document(file)

        # 2. AI Section Discovery & Injection
        # We target professional sections to blend the update in naturally
        target_sections = ['EXPERIENCE', 'WORK', 'HISTORY', 'ACHIEVEMENTS', 'PROJECTS']
        success = False
        
        # Scan paragraphs to find the 'Work Experience' or 'Achievements' block
        for i, para in enumerate(doc.paragraphs):
            text_upper = para.text.upper()
            if any(section in text_upper for section in target_sections):
                # We found a section! Insert the bullet point 2 paragraphs down 
                # (usually where the first or second bullet of that section sits)
                target_idx = min(i + 2, len(doc.paragraphs))
                new_p = doc.paragraphs[target_idx].insert_paragraph_before(f"• {new_achievement}")
                new_p.runs[0].font.name = 'Arial'
                new_p.runs[0].font.size = Pt(10.5)
                success = True
                break
        
        # 3. Fallback: If no section is found, create a professional 'Key Contributions' header
        if not success:
            doc.add_heading('KEY CONTRIBUTIONS', level=1)
            p = doc.add_paragraph(f"• {new_achievement}")
            p.runs[0].font.name = 'Arial'

        # 4. Global ATS Optimization (Font consistency)
        for para in doc.paragraphs:
            for run in para.runs:
                run.font.name = 'Arial'

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        return send_file(
            file_stream, 
            as_attachment=True, 
            download_name='AI_Optimized_Resume.docx'
        )
    except Exception as e:
        return str(e), 500

@app.route('/upgrade-pdf', methods=['POST'])
def upgrade_pdf():
    # Calling the AI logic - returns the high-fidelity .docx
    return upgrade()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
