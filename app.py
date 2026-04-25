import io
import json
import tempfile
import subprocess

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

import fitz

# Optional AI
try:
    from groq import Groq
except:
    Groq = None

# =====================================================
# APP
# =====================================================

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get("PORT", 10000))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

groq_client = None
if GROQ_API_KEY and Groq:
    groq_client = Groq(api_key=GROQ_API_KEY)

# =====================================================
# HEADINGS
# =====================================================

ATS_HEADINGS = [
    "Professional Summary",
    "Key Strengths",
    "Technical Skills",
    "Achievements",
    "Certifications",
    "Professional History",
    "Education",
    "Projects",
    "Awards",
    "Languages"
]

# =====================================================
# AI POLISH
# =====================================================

def classify_and_polish(text, template):

    if not text.strip():
        return {
            "heading": "Achievements",
            "polished": text
        }

    if not groq_client:
        return {
            "heading": "Achievements",
            "polished": text
        }

    prompt = f"""
You are an ATS resume expert.

Choose best heading from:
{ATS_HEADINGS}

Then rewrite professionally.

Template:
{template}

Return JSON:

{{
"heading":"Achievements",
"polished":"text"
}}

Input:
{text}
"""

    try:
        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=180,
            response_format={"type": "json_object"}
        )

        data = json.loads(res.choices[0].message.content)

        heading = data.get("heading", "Achievements")
        polished = data.get("polished", text)

        if heading not in ATS_HEADINGS:
            heading = "Achievements"

        return {
            "heading": heading,
            "polished": polished
        }

    except:
        return {
            "heading": "Achievements",
            "polished": text
        }

# =====================================================
# DOCX HELPERS
# =====================================================

def make_para(text, fill="EEF4FF", bold=False):

    para = OxmlElement("w:p")

    pPr = OxmlElement("w:pPr")
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    pPr.append(shd)

    para.append(pPr)

    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    if bold:
        rPr.append(OxmlElement("w:b"))

    run.append(rPr)

    t = OxmlElement("w:t")
    t.text = text
    run.append(t)

    para.append(run)

    return para

def inject_docx(file_bytes, heading, line):

    doc = Document(io.BytesIO(file_bytes))

    doc.add_paragraph("")
    doc.add_heading(heading, level=1)
    doc.add_paragraph(f"• {line}")

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)

    return out

# =====================================================
# PDF HELPERS
# =====================================================

def inject_pdf(file_bytes, heading, line):

    pdf = fitz.open(stream=file_bytes, filetype="pdf")

    page = pdf[0]

    page.insert_text(
        (40, 710),
        heading,
        fontsize=11
    )

    page.insert_text(
        (40, 730),
        f"• {line}",
        fontsize=10
    )

    out = io.BytesIO(pdf.tobytes())
    out.seek(0)

    return out

# =====================================================
# DOCX TO PDF
# =====================================================

def docx_to_pdf(docx_bytes):

    try:
        with tempfile.TemporaryDirectory() as tmp:

            src = os.path.join(tmp, "resume.docx")

            with open(src, "wb") as f:
                f.write(docx_bytes)

            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmp,
                    src
                ],
                timeout=60
            )

            pdf_path = os.path.join(tmp, "resume.pdf")

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()

    except:
        return None

# =====================================================
# ROUTES
# =====================================================

@app.route("/")
def home():
    return jsonify({
        "status": "Resume Hub Backend Running"
    })

# -----------------------------------------------------

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "ai": bool(groq_client)
    })

# -----------------------------------------------------

@app.route("/polish", methods=["POST"])
def polish():

    try:
        data = request.json

        text = data.get("text", "")
        template = data.get("template", "google")

        result = classify_and_polish(text, template)

        return jsonify({
            "polished_text": result["polished"],
            "heading": result["heading"]
        })

    except Exception as e:
        return jsonify({
            "polished_text": text,
            "heading": "Achievements"
        })

# -----------------------------------------------------

@app.route("/upgrade", methods=["POST"])
def upgrade():

    try:

        file = request.files.get("resume")

        if not file:
            return jsonify({
                "error": "No file uploaded"
            }), 400

        updates = request.form.get("updates", "").strip()
        template = request.form.get("template", "google")
        requested_format = request.form.get("format", "docx")

        result = classify_and_polish(updates, template)

        heading = result["heading"]
        polished = result["polished"]

        file_bytes = file.read()
        filename = file.filename.lower()

        # PDF Upload
        if filename.endswith(".pdf"):

            out = inject_pdf(file_bytes, heading, polished)

            return send_file(
                out,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="Optimized_Resume.pdf"
            )

        # DOCX Upload
        elif filename.endswith(".docx"):

            out = inject_docx(file_bytes, heading, polished)

            if requested_format == "docx":

                return send_file(
                    out,
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    as_attachment=True,
                    download_name="Optimized_Resume.docx"
                )

            out.seek(0)

            pdf_bytes = docx_to_pdf(out.read())

            if pdf_bytes:

                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name="Optimized_Resume.pdf"
                )

            out.seek(0)

            return send_file(
                out,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                download_name="Optimized_Resume.docx"
            )

        return jsonify({
            "error": "Unsupported file type"
        }), 400

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
