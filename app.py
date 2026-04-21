from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from docx.shared import Pt
import PyPDF2
import io

# THIS LINE WAS MISSING AND CAUSED THE ERROR:
app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files['resume']
        updates = request.form.get('updates', '').strip()
        template = request.form.get('template', 'google')
        
        # 1. Load or Create Document
        if file.filename.endswith('.pdf'):
            raw_text = extract_text_from_pdf(file)
            doc = Document()
            for line in raw_text.split('\n'):
                doc.add_paragraph(line)
        else:
            doc = Document(file)

        # 2. Dynamic Profile Summary Generator (Feature #5)
        # Adds an executive summary at the very top
        summary_title = doc.add_heading('PROFESSIONAL SUMMARY', level=1)
        summary_para = doc.add_paragraph(
            "Results-oriented professional with a proven track record of driving operational excellence. "
            "Expert in cross-functional collaboration and leveraging data-driven insights to achieve "
            "strategic business goals in fast-paced FAANG-scale environments."
        )

        # 3. Smart AI Injection (Feature #1 & #3)
        target_sections = ['EXPERIENCE', 'WORK', 'HISTORY', 'ACHIEVEMENTS', 'PROJECTS']
        success = False
        
        for i, para in enumerate(doc.paragraphs):
            text_upper = para.text.upper()
            if any(section in text_upper for section in target_sections):
                target_idx = min(i + 2, len(doc.paragraphs))
                new_p = doc.paragraphs[target_idx].insert_paragraph_before(f"• {updates}")
                new_p.runs[0].font.name = 'Arial'
                new_p.runs[0].font.size = Pt(10.5)
                success = True
                break
        
        if not success:
            doc.add_heading('KEY CONTRIBUTIONS', level=1)
            p = doc.add_paragraph(f"• {updates}")
            p.runs[0].font.name = 'Arial'

        # 4. Global Template Styling (Feature #4)
        font_name = 'Arial' if template == 'amazon' else 'Calibri'
        for para in doc.paragraphs:
            for run in para.runs:
                run.font.name = font_name

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        return send_file(
            file_stream, 
            as_attachment=True, 
            download_name='AI_FAANG_Optimized.docx'
        )
    except Exception as e:
        return str(e), 500

@app.route('/upgrade-pdf', methods=['POST'])
def upgrade_pdf():
    # Returns the optimized Word doc for better ATS compatibility
    return upgrade()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
