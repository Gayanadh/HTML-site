import os
import io
import tempfile
import subprocess
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import fitz  # PyMuPDF
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

def inject_into_docx(file_bytes, updates):
    doc = Document(io.BytesIO(file_bytes))
    if updates:
        body = doc.element.body
        new_para = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), "E8F4FD")
        pPr.append(shd)
        new_para.append(pPr)
        run = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        b = OxmlElement("w:b")
        rPr.append(b)
        run.append(rPr)
        t = OxmlElement("w:t")
        t.text = f"\u2728 AI-OPTIMISED: {updates}"
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.append(t)
        new_para.append(run)
        body.insert(0, new_para)
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

def inject_into_pdf(file_bytes, updates):
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    if updates and len(pdf) > 0:
        page = pdf[0]
        pw = page.rect.width
        banner = fitz.Rect(30, 6, pw - 30, 34)
        page.draw_rect(banner, color=(0.18, 0.46, 0.71), fill=(0.93, 0.97, 1.0), width=0.8)
        page.insert_textbox(banner, f"\u2728 AI-OPTIMISED: {updates}", fontsize=8.5,
                            fontname="helv", color=(0.12, 0.36, 0.58), align=0)
    out = io.BytesIO(pdf.tobytes(garbage=4, deflate=True))
    out.seek(0)
    return out

def docx_to_pdf_via_libreoffice(docx_bytes):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "resume.docx")
            with open(src, "wb") as f:
                f.write(docx_bytes)
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, src],
                capture_output=True, timeout=60
            )
            pdf_path = os.path.join(tmpdir, "resume.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()
    except Exception:
        pass
    return None

@app.route("/polish", methods=["POST"])
def polish():
    if not API_KEY:
        return jsonify({"polished_text": "Error: GEMINI_API_KEY is not set on the server."}), 500
    try:
        data = request.json
        text = data.get("text", "")
        template = data.get("template", "google")

        prompts = {
            "google": "Rewrite as a Google XYZ achievement: 'Accomplished [X] as measured by [Y], by doing [Z]'. One sentence, no preamble.",
            "apple": "Rewrite for Apple focusing on elegant product/user impact. One sentence, no preamble.",
            "amazon": "Rewrite for Amazon using metrics and Leadership Principle language. One sentence, no preamble."
        }
        prompt = prompts.get(template, prompts["google"])

        # FIX 1: Use gemini-2.0-flash (stable, works on v1 and v1beta)
        # FIX 2: No 'models/' prefix
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(f"{prompt}\n\nInput: {text}")

        if response and response.text:
            return jsonify({"polished_text": response.text.strip()})
        return jsonify({"polished_text": "AI returned empty result. Try again."})

    except Exception as e:
        # Fallback: try gemini-1.5-flash if 2.0 fails
        try:
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            response = model.generate_content(f"{prompt}\n\nInput: {text}")
            if response and response.text:
                return jsonify({"polished_text": response.text.strip()})
        except Exception:
            pass
        return jsonify({"polished_text": f"AI Error: {str(e)}"}), 200

@app.route("/upgrade", methods=["POST"])
def upgrade():
    try:
        file = request.files.get("resume")
        updates = request.form.get("updates", "").strip()
        requested_format = request.form.get("format", "docx").lower()

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        file_bytes = file.read()
        filename = file.filename.lower()

        if filename.endswith(".pdf"):
            enhanced_pdf = inject_into_pdf(file_bytes, updates)
            return send_file(enhanced_pdf, mimetype="application/pdf",
                             as_attachment=True, download_name="Optimized_Resume.pdf")

        elif filename.endswith(".docx"):
            enhanced_docx = inject_into_docx(file_bytes, updates)

            if requested_format == "docx":
                return send_file(
                    enhanced_docx,
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    as_attachment=True, download_name="Optimized_Resume.docx"
                )

            enhanced_docx.seek(0)
            pdf_bytes = docx_to_pdf_via_libreoffice(enhanced_docx.read())
            if pdf_bytes:
                return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                                 as_attachment=True, download_name="Optimized_Resume.pdf")

            enhanced_docx.seek(0)
            return send_file(
                enhanced_docx,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True, download_name="Optimized_Resume.docx"
            )

        return jsonify({"error": "Unsupported file type. Use .docx or .pdf"}), 400

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
