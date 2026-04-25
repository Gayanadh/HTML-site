import os
import io
import re
import json
import tempfile
import subprocess
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import fitz  # PyMuPDF
from groq import Groq

app = Flask(__name__)
CORS(app)

# --- AI CONFIGURATION ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ATS-Standard Heading Order for logic
ATS_HEADING_ORDER = [
    "Professional Summary", "Key Strengths", "Technical Skills", "Achievements",
    "Certifications", "Professional History", "Education", "Projects", "Awards",
    "Languages", "Volunteer Experience",
]

# ─────────────────────────────────────────────
#  STYLING & REBUILD ENGINE
# ─────────────────────────────────────────────

def build_styled_docx(ai_markdown: str) -> io.BytesIO:
    """
    Takes raw AI text and builds a professionally formatted 
    document with colors, borders, and margins.
    """
    doc = Document()
    
    # Set Professional Margins (Narrow)
    for section in doc.sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)

    # Process AI Markdown-style lines
    for line in ai_markdown.split('\n'):
        line = line.strip()
        if not line: continue
        
        if line.startswith('# '):
            # SECTION HEADERS (e.g., EXPERIENCE) - Blue & Bold
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(line.replace('# ', '').upper())
            run.bold = True
            run.font.size = Pt(13)
            run.font.color.rgb = RGBColor(46, 116, 181) # Professional Blue
            
            # Add a thin grey horizontal line under the header
            p_border = doc.add_paragraph()
            run_border = p_border.add_run("-" * 85)
            run_border.font.color.rgb = RGBColor(200, 200, 200)
            p_border.paragraph_format.space_after = Pt(4)

        elif line.startswith('## '):
            # JOB TITLES / COMPANIES - Dark & Bold
            p = doc.add_paragraph()
            run = p.add_run(line.replace('## ', ''))
            run.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(30, 30, 30)
            p.paragraph_format.space_before = Pt(6)

        elif line.startswith('- ') or line.startswith('* '):
            # BULLET POINTS
            text = line[2:].strip()
            p = doc.add_paragraph(text, style='List Bullet')
            p.paragraph_format.space_after = Pt(2)

        else:
            # BODY TEXT
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(4)
            
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

def extract_raw_text(file_bytes: bytes, filename: str) -> str:
    """Extracts text from PDF or DOCX so the AI can read it."""
    try:
        if filename.endswith(".pdf"):
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            return "\n".join([page.get_text() for page in pdf])
        elif filename.endswith(".docx"):
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([p.text for p in doc.paragraphs])
    except:
        return ""
    return ""

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.route("/rebuild", methods=["POST"])
def rebuild():
    """Route for the AI Complete Rebuild feature."""
    if not groq_client: 
        return jsonify({"error": "GROQ_API_KEY is not configured on Render."}), 500
    
    try:
        file = request.files.get("resume")
        jd = request.form.get("jobDesc", "")
        template = request.form.get("template", "google")
        
        if not file: return jsonify({"error": "No file uploaded"}), 400

        # 1. Extract Text
        file_bytes = file.read()
        resume_text = extract_raw_text(file_bytes, file.filename.lower())
        
        if not resume_text.strip():
            return jsonify({"error": "Could not read text from your file."}), 400

        # 2. AI Generation
        prompt = f"""You are a FAANG Resume Expert. Rewrite the following resume to perfectly match this Job Description.
STYLE: {template.upper()}
FORMATTING RULES:
- Use '# SECTION NAME' for main headers.
- Use '## Title | Company | Dates' for experience.
- Use '- ' for bullet points.
- Do NOT use bold ** or italics.

JOB DESCRIPTION:
{jd}

CURRENT RESUME DATA:
{resume_text}
"""
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.3
        )
        ai_content = response.choices[0].message.content.strip()

        # 3. Build Styled DOCX
        styled_docx = build_styled_docx(ai_content)
        
        # 4. Convert to PDF via LibreOffice (Since you are using Docker)
        pdf_bytes = None
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                src = os.path.join(tmpdir, "resume.docx")
                with open(src, "wb") as f: f.write(styled_docx.read())
                subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, src], timeout=60)
                pdf_path = os.path.join(tmpdir, "resume.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f: pdf_bytes = f.read()
        except:
            pass

        if pdf_bytes:
            return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name="AI_Rebuilt_Resume.pdf")
        else:
            styled_docx.seek(0)
            return send_file(styled_docx, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", as_attachment=True, download_name="AI_Rebuilt_Resume.docx")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/polish", methods=["POST"])
def polish():
    # Keep your existing polish logic here...
    try:
        data = request.json
        text = data.get("text", "")
        template = data.get("template", "google")
        prompt = f"Rewrite this resume bullet point using the {template} style: {text}"
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        return jsonify({"polished_text": response.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
