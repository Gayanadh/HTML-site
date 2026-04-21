import os
from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
from fpdf import FPDF
import io

app = Flask(__name__)
CORS(app)

@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files.get('resume')
        updates = request.form.get('updates', '')
        requested_format = request.form.get('format', 'docx')

        if not file:
            return "No file uploaded", 400

        # OPEN your existing document (Preserves all boxes, fonts, and margins)
        doc = Document(file)

        # SURGICAL INJECTION: Add the AI updates at the very beginning
        # This keeps the rest of the document exactly as you designed it.
        if updates:
            # We insert a new paragraph at the very top (index 0)
            p = doc.paragraphs[0].insert_paragraph_before()
            run = p.add_run(f"AI-OPTIMIZED UPDATE: {updates}")
            run.bold = True
            p.add_run("\n" + "="*30 + "\n") # Visual separator

        # --- EXPORT AS WORD (100% Perfect Layout) ---
        if requested_format == 'docx':
            file_stream = io.BytesIO()
            doc.save(file_stream)
            file_stream.seek(0)
            return send_file(
                file_stream,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name="Optimized_Resume.docx"
            )

        # --- EXPORT AS PDF ---
        elif requested_format == 'pdf':
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=10)
            
            # We pull the text content out of your formatted doc
            for para in doc.paragraphs:
                if para.text.strip():
                    # Clean special characters that crash PDF generators
                    clean_text = para.text.encode('latin-1', 'ignore').decode('latin-1')
                    pdf.multi_cell(0, 8, txt=clean_text)
                    pdf.ln(2)
            
            pdf_stream = io.BytesIO()
            pdf_bytes = pdf.output(dest='S')
            pdf_stream.write(pdf_bytes)
            pdf_stream.seek(0)
            
            return send_file(
                pdf_stream,
                mimetype='application/pdf',
                as_attachment=True,
                download_name="Optimized_Resume.pdf"
            )

    except Exception as e:
        print(f"Error: {e}")
        return f"Server Error: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
