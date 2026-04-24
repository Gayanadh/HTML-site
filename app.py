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

# --- AI CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)

# --- HELPERS ---

def inject_into_docx(file_bytes: bytes, updates: str) -> io.BytesIO:
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
        t.text = f"✨ AI-OPTIMISED: {updates}"
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.append(t)
        new_para.append(run)
        body.insert(0, new_para)
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

def inject_into_pdf(file_bytes: bytes, updates: str) -> io.BytesIO:
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    if updates and len(pdf) > 0:
        page = pdf[0]
        pw = page.rect.width
        banner = fitz.Rect(30, 6, pw - 30, 34)
        page.draw_rect(banner, color=(0.18, 0.46, 0.71), fill=(0.93, 0.97, 1.0), width=0.8)
        page.insert_textbox(banner, f"✨ AI-OPTIMISED: {updates}", fontsize=8.5, fontname="helv", color=(0.12, 0.36, 0.58), align=0)
    out = io.BytesIO(pdf.tobytes(garbage=4, deflate=True))
    out.seek(0)
    return out

def docx_to_pdf_via_libreoffice(docx_bytes: bytes) -> bytes | None:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "resume.docx")
            with open(src, "wb") as f:
                f.write(docx_bytes)
            subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, src], capture_output=True, timeout=60)
            pdf_path = os.path.join(tmpdir, "resume.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()
    except:
        pass
    return None

# --- ROUTES ---

@app.route("/polish", methods=["POST"])
def polish():
    if not API_KEY:
        return jsonify({"polished_text": "Error: GEMINI_API_KEY is missing."}), 500
    
    try:
        data = request.json
        text = data.get("text", "")
        template = data.get("template", "google")
        
        prompts = {
            "google": "Rewrite this as a Google-style achievement (XYZ formula): 'Accomplished [X] as measured by [Y], by doing [Z]'. One sentence.",
            "apple": "Rewrite this for Apple. Focus on product-centric storytelling and elegant user impact. One sentence.",
            "amazon": "Rewrite this for Amazon. Use high-scale metrics and Leadership Principle language. One sentence."
        }
        
        prompt = prompts.get(template, prompts["google"])
        
        # CRITICAL FIX: Use the full string path to force the stable v1 model
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(f"{prompt}\n\nInput: {text}")
        
        if response and response.text:
            return jsonify({"polished_text": response.text})
        else:
            return jsonify({"polished_text": "AI returned empty results. Try again."})

    except Exception as e:
        return jsonify({"polished_text": f"AI Error: {str(e)}"}), 200

@app.route("/upgrade", methods=["POST"])
def upgrade():
    try:
        file = request.files.get("resume")
        updates = request.form.get("updates", "").strip()
        requested_format = request.form.get("format", "docx").lower()
        if not file: return jsonify({"error": "No file"}), 400
        
        file_bytes = file.read()
        filename = file.filename.lower()

        if filename.endswith(".pdf"):
            enhanced_pdf = inject_into_pdf(file_bytes, updates)
            return send_file(enhanced_pdf, mimetype="application/pdf", as_attachment=True, download_name="Optimized_Resume.pdf")

        elif filename.endswith(".docx"):
            enhanced_docx = inject_into_docx(file_bytes, updates)
            if requested_format == "docx":
                return send_file(enhanced_docx, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", as_attachment=True, download_name="Optimized_Resume.docx")
            
            pdf_bytes = docx_to_pdf_via_libreoffice(enhanced_docx.read())
            if pdf_bytes:
                return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name="Optimized_Resume.pdf")
            return send_file(enhanced_docx, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", as_attachment=True, download_name="Optimized_Resume.docx")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
