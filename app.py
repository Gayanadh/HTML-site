from flask import Flask, request, send_file
from flask_cors import CORS
from docx import Document
import io

app = Flask(__name__)
CORS(app) # This allows your GitHub site to talk to this backend

@app.route('/upgrade', methods=['POST'])
def upgrade():
    file = request.files['resume']
    updates = request.form.get('updates')

    # Open the uploaded Word doc
    doc = Document(file)
    
    # Add the updates to a new page
    doc.add_page_break()
    doc.add_heading('Updates Provided:', level=1)
    doc.add_paragraph(updates)

    # Save to memory
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    return send_file(file_stream, as_attachment=True, download_name='Updated_Resume.docx')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
