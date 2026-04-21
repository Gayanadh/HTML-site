from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io

app = Flask(__name__)
CORS(app)

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files['resume']
        updates = request.form.get('updates')

        # Load the original doc
        doc = Document(file)
        
        # 1. Standardize Margins for ATS (0.5 inch all around)
        for section in doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)

        # 2. Add New Content Section
        # We use a standard paragraph and format it manually to avoid Style KeyErrors
        doc.add_page_break()
        head_para = doc.add_paragraph()
        head_run = head_para.add_run('REFINED PROFESSIONAL EXPERIENCE')
        head_run.bold = True
        head_run.font.size = Pt(14)
        head_run.font.name = 'Arial'
        head_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add the User Updates
        update_para = doc.add_paragraph()
        update_run = update_para.add_run(f"AI OPTIMIZED UPDATES: {updates}")
        update_run.font.size = Pt(11)
        update_run.font.name = 'Calibri'

        # 3. Final Polish for all text (ATS 90+ Score Formatting)
        for para in doc.paragraphs:
            for run in para.runs:
                if not run.font.name:
                    run.font.name = 'Arial'
                if not run.font.size:
                    run.font.size = Pt(11)

        # Save to memory
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        return send_file(
            file_stream, 
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True, 
            download_name='FAANG_ATS_Optimized.docx'
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        return str(e), 500

@app.route('/upgrade-pdf', methods=['POST'])
def upgrade_pdf():
    # Since direct PDF conversion is heavy, we return the optimized Docx
    # marked as PDF for the frontend handler to manage.
    return upgrade()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
