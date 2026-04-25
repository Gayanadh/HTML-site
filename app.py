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

# --- BRANDING COLORS ---
NAVY = RGBColor(27, 38, 59)    # Midnight Navy
SLATE = RGBColor(65, 90, 119)   # Slate Grey
OFF_BLACK = RGBColor(13, 15, 20)

# ─────────────────────────────────────────────
#  EXECUTIVE DESIGN ENGINE
# ─────────────────────────────────────────────

def set_narrow_margins(doc):
    for section in doc.sections:
        section.top_margin = Inches(0.4)
        section.bottom_margin = Inches(0.4)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
    return doc

def add_executive_header(doc, name, info_line):
    """Creates a centered, high-impact header."""
    header_p = doc.add_paragraph()
    header_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = header_p.add_run(name.upper())
    name_run.bold = True
    name_run.font.size = Pt(22)
    name_run.font.color.rgb = NAVY
    
    info_p = doc.add_paragraph()
    info_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info_run = info_p.add_run(info_line)
    info_run.font.size = Pt(9)
    info_run.font.color.rgb = SLATE
    
    # Add a thick bottom border after the header
    border_p = doc.add_paragraph()
    border_run = border_p.add_run("-" * 105)
    border_run.font.size = Pt(2)
    border_run.font.color.rgb = NAVY
    border_p.paragraph_format.space_after = Pt(12)

def build_high_class_docx(ai_content: str) -> io.BytesIO:
    doc = Document()
    doc = set_narrow_margins(doc)
    
    # Extract Name/Contact for Header (AI usually puts these first)
    lines = ai_content.split('\n')
    header_data = [l for l in lines[:5] if l.strip() and not l.startswith('#')]
    name = header_data[0] if header_data else "RESUME"
    contact = " | ".join(header_data[1:3]) if len(header_data) > 1 else ""
    
    add_executive_header(doc, name, contact)

    for line in lines:
        line = line.strip()
        if not line or line in header_data: continue
        
        if line.startswith('# '):
            # MAJOR SECTION (Blue Bar Style)
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            run = p.add_run(line.replace('# ', '').upper())
            run.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = NAVY
            
            # Subtle Underline
            p_line = doc.add_paragraph()
            run_line = p_line.add_run("_" * 90)
            run_line.font.size = Pt(1)
            run_line.font.color.rgb = RGBColor(200, 200, 200)
            p_line.paragraph_format.space_after = Pt(6)

        elif line.startswith('## '):
            # SUBHEADING (Bold/Italic Job Title)
            p = doc.add_paragraph()
            run = p.add_run(line.replace('## ', ''))
            run.bold = True
            run.font.size = Pt(10.5)
            p.paragraph_format.space_before = Pt(4)

        elif line.startswith('- ') or line.startswith('* '):
            # ATS-OPTIMIZED BULLETS
            p = doc.add_paragraph(line[2:].strip(), style='List Bullet')
            p.paragraph_format.space_after = Pt(1.5)

        else:
            # BODY TEXT
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(4)
            run = p.runs[0] if p.runs else p.add_run(line)
            run.font.size = Pt(9.5)
            
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# ─────────────────────────────────────────────
#  REBUILD & POLISH ROUTES
# ─────────────────────────────────────────────

@app.route("/rebuild", methods=["POST"])
def rebuild():
    if not groq_client: return jsonify({"error": "GROQ_API_KEY Missing"}), 500
    try:
        file = request.files.get("resume")
        jd = request.form.get("jobDesc", "")
        template = request.form.get("template", "google")
        
        # 1. READ
        file_bytes = file.read()
        if file.filename.lower().endswith(".pdf"):
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            resume_text = "\n".join([page.get_text() for page in pdf])
        else:
            doc = Document(io.BytesIO(file_bytes))
            resume_text = "\n".join([p.text for p in doc.paragraphs])

        # 2. AI INTELLIGENCE (70B MODEL)
        prompt = f"""You are a Master Executive Resume Architect. 
        Reconstruct this resume to perfectly align with the target Job Description.
        
        INSTRUCTIONS:
        - Use '# SECTION NAME' for major headers.
        - Use '## Role | Company | Location | Dates' for subheaders.
        - Use the {template.upper()} impact-style for bullets.
        - Ensure keyword density for ATS optimization.
        
        TARGET JD: {jd}
        USER RESUME: {resume_text}
        """
        
        response = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000, temperature=0.2
        )
        ai_output = response.choices[0].message.content.strip()

        # 3. BUILD & EXPORT
        final_docx = build_high_class_docx(ai_output)
        
        # Try PDF Export via LibreOffice
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                src = os.path.join(tmpdir, "res.docx")
                with open(src, "wb") as f: f.write(final_docx.read())
                subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, src], timeout=60)
                pdf_path = os.path.join(tmpdir, "res.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f: return send_file(io.BytesIO(f.read()), mimetype="application/pdf", as_attachment=True, download_name="Executive_Rebuild.pdf")
        except: pass

        final_docx.seek(0)
        return send_file(final_docx, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", as_attachment=True, download_name="Executive_Rebuild.docx")

    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
