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

app = Flask(__name__)
CORS(app)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def inject_into_docx(file_bytes: bytes, updates: str) -> io.BytesIO:
    """
    Open the original DOCX bytes, inject an AI-update banner via raw XML
    so text boxes / shapes / complex formatting are never disturbed, then
    return the saved bytes.
    """
    doc = Document(io.BytesIO(file_bytes))

    if updates:
        body = doc.element.body

        # Build a fully-formed paragraph element in raw XML
        new_para = OxmlElement("w:p")

        # Paragraph properties: keep it together with next paragraph
        pPr = OxmlElement("w:pPr")
        keepNext = OxmlElement("w:keepNext")
        pPr.append(keepNext)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "E8F4FD")      # light-blue highlight band
        pPr.append(shd)
        new_para.append(pPr)

        # Run
        run = OxmlElement("w:r")

        rPr = OxmlElement("w:rPr")
        b = OxmlElement("w:b")
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "1D5E99")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "20")            # 10 pt
        rPr.extend([b, color, sz])
        run.append(rPr)

        t = OxmlElement("w:t")
        t.text = f"\u2728 AI-OPTIMISED: {updates}"
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.append(t)
        new_para.append(run)

        # Insert BEFORE the first element in <w:body> so it lands at the top
        # without touching any existing paragraph objects
        body.insert(0, new_para)

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out


def inject_into_pdf(file_bytes: bytes, updates: str) -> io.BytesIO:
    """
    Overlay the AI-update text onto page 1 of the original PDF using PyMuPDF.
    The original layout, fonts, images and vector graphics are 100% preserved.
    """
    pdf = fitz.open(stream=file_bytes, filetype="pdf")

    if updates and len(pdf) > 0:
        page = pdf[0]
        pw = page.rect.width

        # Draw a banner rectangle at the very top
        banner = fitz.Rect(30, 6, pw - 30, 34)
        page.draw_rect(banner, color=(0.18, 0.46, 0.71),
                       fill=(0.93, 0.97, 1.0), width=0.8)

        # Insert the text inside the banner
        page.insert_textbox(
            banner,
            f"\u2728 AI-OPTIMISED: {updates}",
            fontsize=8.5,
            fontname="helv",
            color=(0.12, 0.36, 0.58),
            align=0,            # left-align
        )

    out = io.BytesIO(pdf.tobytes(garbage=4, deflate=True))
    out.seek(0)
    return out


def docx_to_pdf_via_libreoffice(docx_bytes: bytes) -> bytes | None:
    """
    Convert DOCX → PDF using LibreOffice headless (if available on the server).
    Returns PDF bytes on success, None if LibreOffice is not installed.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "resume.docx")
            with open(src, "wb") as f:
                f.write(docx_bytes)

            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf",
                 "--outdir", tmpdir, src],
                capture_output=True, timeout=60
            )
            pdf_path = os.path.join(tmpdir, "resume.pdf")
            if result.returncode == 0 and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# ─────────────────────────────────────────────
#  ROUTE
# ─────────────────────────────────────────────

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

        # ── PDF input ──────────────────────────────────────────────────────
        if filename.endswith(".pdf"):
            enhanced_pdf = inject_into_pdf(file_bytes, updates)

            if requested_format == "pdf":
                return send_file(
                    enhanced_pdf,
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name="Optimized_Resume.pdf",
                )

            # PDF → DOCX is lossy by nature; return the enhanced PDF instead
            return send_file(
                enhanced_pdf,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="Optimized_Resume.pdf",
            )

        # ── DOCX input ─────────────────────────────────────────────────────
        elif filename.endswith(".docx"):
            enhanced_docx = inject_into_docx(file_bytes, updates)

            if requested_format == "docx":
                return send_file(
                    enhanced_docx,
                    mimetype=(
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                    as_attachment=True,
                    download_name="Optimized_Resume.docx",
                )

            # DOCX → PDF: try LibreOffice, fall back to returning DOCX
            if requested_format == "pdf":
                enhanced_docx.seek(0)
                pdf_bytes = docx_to_pdf_via_libreoffice(enhanced_docx.read())
                if pdf_bytes:
                    return send_file(
                        io.BytesIO(pdf_bytes),
                        mimetype="application/pdf",
                        as_attachment=True,
                        download_name="Optimized_Resume.pdf",
                    )
                else:
                    # LibreOffice unavailable — return the DOCX with a header
                    enhanced_docx.seek(0)
                    return send_file(
                        enhanced_docx,
                        mimetype=(
                            "application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document"
                        ),
                        as_attachment=True,
                        download_name="Optimized_Resume.docx",
                    )

        else:
            return jsonify({"error": "Unsupported file type. Use .docx or .pdf"}), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
