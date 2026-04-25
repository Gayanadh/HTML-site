import os
import io
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from docx import Document
import fitz

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get("PORT", 10000))

# ====================================================
# HEALTH
# ====================================================

@app.route("/")
def home():
    return jsonify({"status": "GK Resume Hub API Running"})

@app.route("/api/health")
def health():
    return jsonify({"status": "online"})

# ====================================================
# ATS SCORE
# ====================================================

@app.route("/api/ats-score", methods=["POST"])
def ats_score():
    data = request.json
    text = data.get("text", "").lower()

    score = 30

    keywords = [
        "python", "excel", "sales", "team",
        "leadership", "analytics", "management",
        "communication", "sql"
    ]

    for word in keywords:
        if word in text:
            score += 6

    if "%" in text:
        score += 10

    score = min(score, 100)

    return jsonify({
        "score": score
    })

# ====================================================
# AI POLISH
# ====================================================

@app.route("/api/polish", methods=["POST"])
def polish():

    data = request.json
    text = data.get("text", "")

    polished = f"Improved performance by delivering {text.lower()} with measurable business impact."

    return jsonify({
        "polished_text": polished
    })

# ====================================================
# DOCX MODIFY
# ====================================================

def modify_docx(file_bytes, line):
    doc = Document(io.BytesIO(file_bytes))
    doc.add_paragraph("")
    doc.add_heading("Achievements", level=1)
    doc.add_paragraph(f"• {line}")

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output

# ====================================================
# PDF MODIFY
# ====================================================

def modify_pdf(file_bytes, line):
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    page = pdf[0]

    page.insert_text(
        (40, 760),
        f"• {line}",
        fontsize=10
    )

    output = io.BytesIO(pdf.tobytes())
    output.seek(0)
    return output

# ====================================================
# UPGRADE RESUME
# ====================================================

@app.route("/api/upgrade", methods=["POST"])
def upgrade():

    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["resume"]

    updates = request.form.get("updates", "")
    file_bytes = file.read()

    if file.filename.lower().endswith(".docx"):

        output = modify_docx(file_bytes, updates)

        return send_file(
            output,
            as_attachment=True,
            download_name="Optimized_Resume.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    elif file.filename.lower().endswith(".pdf"):

        output = modify_pdf(file_bytes, updates)

        return send_file(
            output,
            as_attachment=True,
            download_name="Optimized_Resume.pdf",
            mimetype="application/pdf"
        )

    return jsonify({"error": "Unsupported format"}), 400

# ====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
