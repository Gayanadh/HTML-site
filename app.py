import os
from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from docx.shared import Pt
import PyPDF2
from fpdf import FPDF
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
        if 'resume' not in request.files:
            return "No file uploaded", 400
            
        file = request.files['resume']
        updates = request.form.get('updates', '').strip()
        template = request.form.get('template', 'google')
        # Check what format the user requested (pdf or docx)
        requested_format = request.form.get('format', 'docx')

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
        
        for i, para in enumerate(doc.paragraphs):
            text_upper = para.text.upper()
            if any(section in text_upper for section in target_sections):
                target_idx = min(i + 1, len(doc.paragraphs))
                new_p = doc.paragraphs[target_idx].insert_paragraph_before(f"• {updates}")
                new_p.runs[0].font.bold = True
                success = True
                break

        if not success:
            top_p = doc.paragraphs[0].insert_paragraph_before(f"KEY ACHIEVEMENT: {updates}")
            top_p.runs[0].bold = True

        # 3. Global Styling
        font_name = 'Arial' if template == 'amazon' else 'Calibri'
        for para in doc.paragraphs:
            for run in para.runs:
                run.font.name = font_name
                run.font.size = Pt(11)

        # 4. Export Logic
        if requested_format == 'pdf':
            # Create a REAL PDF from the document text
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Helvetica", size=11) # Helvetica is standard and safe
            
            for para in doc.paragraphs:
                if para.text.strip():
                    # Clean text to prevent PDF encoding errors
                    clean_text = para.text.encode('latin-1', 'ignore').decode('latin-1')
                    pdf.multi_cell(0, 10, txt=clean_text)
                    pdf.ln(2)
            
            pdf_stream = io.BytesIO()
            pdf_output = pdf.output(dest='S')
            pdf_stream.write(pdf_output)
            pdf_stream.seek(0)
            
            return send_file(
                pdf_stream, 
                mimetype='application/pdf',
                as_attachment=True, 
                download_name='AI_FAANG_Resume.pdf'
            )
        
        else:
            # Export as DOCX
            file_stream = io.BytesIO()
            doc.save(file_stream)
            file_stream.seek(0)
            return send_file(
                file_stream, 
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True, 
                download_name='AI_FAANG_Resume.docx'
            )

    except Exception as e:
        print(f"Error encountered: {str(e)}")
        return f"Internal Server Error: {str(e)}", 500

if __name__ == "__main__":
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
