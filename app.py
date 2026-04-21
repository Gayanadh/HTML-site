import os
from flask import Flask, request, send_file, jsonify
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

        # Load the existing Word Document
        # This keeps your original margins, fonts, and text boxes intact
        doc = Document(file)

        # Inject updates at the very top
        if updates:
            p = doc.paragraphs[0].insert_paragraph_before()
            run = p.add_run(f"AI-OPTIMIZED UPDATE: {updates}")
            run.bold = True
            doc.add_paragraph("-" * 30)

        # --- WORD EXPORT ---
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

        # --- PDF EXPORT ---
        elif requested_format == 'pdf':
            pdf = FPDF()
            pdf.add_page()
            # Using 'Helvetica' as it is a core font that doesn't require external files
            pdf.set_font("Helvetica", size=10)
            
            # Transfer text from Word to PDF
            for para in doc.paragraphs:
                if para.text.strip():
                    # This line cleans symbols that usually cause 500 errors
                    clean_text = para.text.encode('ascii', 'ignore').decode('ascii')
                    pdf.multi_cell(0, 8, txt=clean_text)
                    pdf.ln(2)
            
            pdf_output = io.BytesIO()
            # In fpdf2, dest='S' returns the byte string
            pdf_content = pdf.output() 
            pdf_output.write(pdf_content)
            pdf_output.seek(0)

            return send_file(
                pdf_output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name="Optimized_Resume.pdf"
            )

    except Exception as e:
        # This prints the REAL error to your Render Logs
        print(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
