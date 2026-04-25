import os
import io
import re
import json
import tempfile
import subprocess
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import fitz
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ─────────────────────────────────────────────
#  ATS-STANDARD HEADING MAP
#  Maps AI-chosen category → canonical heading
#  and where it should sit in a resume (order)
# ─────────────────────────────────────────────
ATS_HEADING_ORDER = [
    "Professional Summary",
    "Key Strengths",
    "Technical Skills",
    "Achievements",
    "Certifications",
    "Professional History",
    "Education",
    "Projects",
    "Awards",
    "Languages",
    "Volunteer Experience",
]

ATS_CATEGORY_MAP = {
    "achievement":          "Achievements",
    "accomplishment":       "Achievements",
    "award":                "Awards",
    "certification":        "Certifications",
    "license":              "Certifications",
    "skill":                "Technical Skills",
    "technical skill":      "Technical Skills",
    "strength":             "Key Strengths",
    "language":             "Languages",
    "project":              "Projects",
    "volunteer":            "Volunteer Experience",
    "summary":              "Professional Summary",
    "objective":            "Professional Summary",
    "experience":           "Professional History",
}

# ─────────────────────────────────────────────
#  STEP 1 — AI: classify + polish the sentence
# ─────────────────────────────────────────────
def classify_and_polish(text: str, template: str) -> dict:
    """
    Ask Groq to:
      1. Choose the correct ATS heading for this sentence
      2. Rewrite it in the right style for the chosen template
    Returns { "heading": str, "polished": str }
    """
    system_prompt = f"""You are an expert ATS resume writer.
Given a sentence from a job applicant, do two things:
1. Decide which ATS-standard resume heading this sentence belongs under.
   Choose ONLY from this list:
   {json.dumps(ATS_HEADING_ORDER)}
2. Rewrite the sentence to be ATS-optimised for a {template.upper()} job application.
   - Google: use the XYZ formula (Accomplished X as measured by Y by doing Z)
   - Apple: product-centric, elegant impact language
   - Amazon: metrics-driven, Leadership Principles language
   - Default: strong action verb, quantified result, concise

Respond ONLY with valid JSON in this exact format, nothing else:
{{"heading": "<chosen heading from the list>", "polished": "<rewritten 

sentence>"}}"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text}
            ],
            max_tokens=200,
            temperature=0.4,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        heading = result.get("heading", "Achievements")
        polished = result.get("polished", text)
        # Validate heading is in our list
        if heading not in ATS_HEADING_ORDER:
            heading = "Achievements"
        return {"heading": heading, "polished": polished}
    except Exception as e:
        return {"heading": "Achievements", "polished": text}

# ─────────────────────────────────────────────
#  PDF HELPERS
# ─────────────────────────────────────────────
def get_pdf_text_map(page):
    """Return list of {text, y, size, bold} for every span."""
    items = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for span in line["spans"]:
                items.append({
                    "text": span["text"].strip(),
                    "y":    span["origin"][1],
                    "size": span["size"],
                    "bold": bool(span["flags"] & 2**4),
                })
    return sorted(items, key=lambda x: x["y"])

def find_heading_y_in_pdf(items, heading: str):
    """Find Y position of a heading in the PDF (fuzzy match)."""
    needle = heading.lower()
    for item in items:
        if needle in item["text"].lower() and (item["bold"] or item["size"] >= 11):
            return item["y"]
    return None

def find_insert_position_pdf(items, target_heading: str):
    """
    Returns (insert_y, found_existing):
    - If heading exists: Y just after the heading line
    - If not: Y just before the next lower-priority heading
    """
    heading_idx = ATS_HEADING_ORDER.index(target_heading) if target_heading 

in ATS_HEADING_ORDER else 99

    # Try to find the exact heading
    target_y = find_heading_y_in_pdf(items, target_heading)
    if target_y:
        return target_y + 16, True  # insert right after existing heading

    # Find the next heading that comes after our target in ATS order
    for next_heading in ATS_HEADING_ORDER[heading_idx + 1:]:
        y = find_heading_y_in_pdf(items, next_heading)
        if y:
            return y - 6, False  # insert just above the next heading

    # Last resort: find the last item on the page
    if items:
        return items[-1]["y"] + 20, False
    return 200, False

def inject_into_pdf(file_bytes: bytes, updates: str, heading: str) -> io.BytesIO:
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    if not updates or len(pdf) == 0:
        return io.BytesIO(pdf.tobytes(garbage=4, deflate=True))

    page = pdf[0]
    pw = page.rect.width
    items = get_pdf_text_map(page)
    insert_y, heading_exists = find_insert_position_pdf(items, heading)

    HEADER_H = 16
    CONTENT_H = 30
    BLOCK_H = (CONTENT_H if heading_exists else HEADER_H + 

CONTENT_H)

    y = insert_y

    if not heading_exists:
        # Draw new heading bar
        hdr_rect = fitz.Rect(30, y, pw - 30, y + HEADER_H)
        page.draw_rect(hdr_rect, color=(0.15, 0.33, 0.60),
                       fill=(0.15, 0.33, 0.60), width=0)
        page.insert_textbox(
            fitz.Rect(34, y + 1, pw - 34, y + HEADER_H - 1),
            heading,
            fontsize=9, fontname="hebo",
            color=(1, 1, 1), align=0
        )
        y += HEADER_H

    # Draw content block
    content_rect = fitz.Rect(30, y, pw - 30, y + CONTENT_H)
    page.draw_rect(content_rect,
                   color=(0.75, 0.85, 0.95),
                   fill=(0.93, 0.96, 1.0), width=0.5)
    page.insert_textbox(
        fitz.Rect(36, y + 4, pw - 36, y + CONTENT_H - 2),
        f"\u2022  {updates}",
        fontsize=9, fontname="helv",
        color=(0.08, 0.18, 0.38), align=0
    )

    out = io.BytesIO(pdf.tobytes(garbage=4, deflate=True))
    out.seek(0)
    return out

# ─────────────────────────────────────────────
#  DOCX HELPERS
# ─────────────────────────────────────────────
def get_docx_heading_map(doc):
    """Return dict of {heading_text_lower: paragraph_index}."""
    mapping = {}
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if t:
            mapping[t.lower()] = i
    return mapping

def find_insert_index_docx(doc, target_heading: str):
    """
    Returns (paragraph_index, found_existing).
    Searches for target heading; if not found, finds the next
    lower-priority ATS heading and inserts before it.
    """
    paras = doc.paragraphs
    heading_idx = ATS_HEADING_ORDER.index(target_heading) if target_heading 

in ATS_HEADING_ORDER else 99
    needle = target_heading.lower()

    # Exact / fuzzy match for existing heading
    for i, p in enumerate(paras):
        if needle in p.text.strip().lower():
            return i, True  # insert after this paragraph

    # Find next lower-priority heading as anchor
    for next_heading in ATS_HEADING_ORDER[heading_idx + 1:]:
        for i, p in enumerate(paras):
            if next_heading.lower() in p.text.strip().lower():
                return i, False  # insert before this paragraph

    # Fallback: before last paragraph
    return max(len(paras) - 1, 1), False

def _make_xml_para(fill_color, text, bold=False, text_color="1A3A6B", 

font_size="20", indent=False):
    """Build a fully-specified <w:p> element."""
    para = OxmlElement("w:p")

    pPr = OxmlElement("w:pPr")
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill_color)
    shd.set(qn("w:color"), "auto")
    pPr.append(shd)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "60")
    spacing.set(qn("w:after"), "60")
    pPr.append(spacing)
    if indent:
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), "280")
        pPr.append(ind)
    para.append(pPr)

    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    if bold:
        rPr.append(OxmlElement("w:b"))
    color_el = OxmlElement("w:color")
    color_el.set(qn("w:val"), text_color)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), font_size)
    rPr.extend([color_el, sz])
    run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run.append(t)
    para.append(run)
    return para

def inject_into_docx(file_bytes: bytes, updates: str, heading: str) -> io.BytesIO:
    doc = Document(io.BytesIO(file_bytes))
    if not updates:
        out = io.BytesIO(); doc.save(out); out.seek(0); return out

    insert_idx, heading_exists = find_insert_index_docx(doc, heading)
    anchor_para = doc.paragraphs[insert_idx]

    if heading_exists:
        # Insert bullet right after the existing heading
        bullet = _make_xml_para(
            fill_color="EEF4FF",
            text=f"\u2022  {updates}",
            bold=False,
            text_color="1A3A6B",
            font_size="20",
            indent=True
        )
        anchor_para._element.addnext(bullet)
    else:
        # Insert before the anchor: heading + bullet (insert bullet first, then heading 

before it)
        bullet = _make_xml_para(
            fill_color="EEF4FF",
            text=f"\u2022  {updates}",
            bold=False,
            text_color="1A3A6B",
            font_size="20",
            indent=True
        )
        anchor_para._element.addprevious(bullet)

        heading_para = _make_xml_para(
            fill_color="2E5C9E",
            text=heading,
            bold=True,
            text_color="FFFFFF",
            font_size="22",
            indent=False
        )
        bullet.addprevious(heading_para)

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# ─────────────────────────────────────────────
#  LibreOffice
# ─────────────────────────────────────────────
def docx_to_pdf_via_libreoffice(docx_bytes):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "resume.docx")
            with open(src, "wb") as f: f.write(docx_bytes)
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf",
                 "--outdir", tmpdir, src],
                capture_output=True, timeout=60
            )
            pdf_path = os.path.join(tmpdir, "resume.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f: return f.read()
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────
@app.route("/polish", methods=["POST"])
def polish():
    if not groq_client:
        return jsonify({"polished_text": "Error: GROQ_API_KEY not set.", 

"heading": "Achievements"}), 500
    try:
        data = request.json
        text = data.get("text", "")
        template = data.get("template", "google")
        result = classify_and_polish(text, template)
        return jsonify({
            "polished_text": result["polished"],
            "heading":       result["heading"]    # send heading back to frontend
        })
    except Exception as e:
        return jsonify({"polished_text": f"AI Error: {str(e)}", "heading": 

"Achievements"}), 200


@app.route("/upgrade", methods=["POST"])
def upgrade():
    try:
        file = request.files.get("resume")
        updates = request.form.get("updates", "").strip()
        requested_format = request.form.get("format", "docx").lower()
        # Heading can be sent from frontend (after /polish), or we classify now
        heading = request.form.get("heading", "").strip()

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        # If no heading was provided, classify the raw text now
        if updates and not heading and groq_client:
            result = classify_and_polish(updates, request.form.get("template", 

"google"))
            heading  = result["heading"]
            updates  = result["polished"]
        elif not heading:
            heading = "Achievements"

        file_bytes = file.read()
        filename   = file.filename.lower()

        if filename.endswith(".pdf"):
            out = inject_into_pdf(file_bytes, updates, heading)
            return send_file(out, mimetype="application/pdf",
                             as_attachment=True, download_name="Optimized_Resume.pdf")

        elif filename.endswith(".docx"):
            enhanced = inject_into_docx(file_bytes, updates, heading)
            if requested_format == "docx":
                return send_file(
                    enhanced,
                    mimetype="application/vnd.openxmlformats-

officedocument.wordprocessingml.document",
                    as_attachment=True, download_name="Optimized_Resume.docx"
                )
            enhanced.seek(0)
            pdf_bytes = docx_to_pdf_via_libreoffice(enhanced.read())
            if pdf_bytes:
                return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                                 as_attachment=True, 

download_name="Optimized_Resume.pdf")
            enhanced.seek(0)
            return send_file(
                enhanced,
                mimetype="application/vnd.openxmlformats-

officedocument.wordprocessingml.document",
                as_attachment=True, download_name="Optimized_Resume.docx"
            )

        return jsonify({"error": "Unsupported file type"}), 400

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
