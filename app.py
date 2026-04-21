@app.route('/upgrade', methods=['POST'])
def upgrade():
    try:
        file = request.files['resume']
        updates = request.form.get('updates', '')
        template = request.form.get('template', 'google')
        
        doc = Document(file) if not file.filename.endswith('.pdf') else Document()
        
        # 5. Dynamic Profile Summary Generator
        summary_title = doc.add_heading('PROFESSIONAL SUMMARY', level=1)
        summary_para = doc.add_paragraph("Dynamic, results-driven professional with a track record of scaling operations. Expert at leveraging data to drive efficiency and cross-functional team success in high-pressure FAANG environments.")

        # 4. Template Selection Styling
        font_size = 10 if template == 'amazon' else 11 # Amazon template is more dense
        
        # 3. Job Match Injection
        target_found = False
        for para in doc.paragraphs:
            if "EXPERIENCE" in para.text.upper():
                new_p = para.insert_paragraph_before(f"• {updates}")
                target_found = True
                break
        
        if not target_found:
            doc.add_heading('NOTABLE ACHIEVEMENTS', level=1)
            doc.add_paragraph(f"• {updates}")

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        return send_file(file_stream, as_attachment=True, download_name='AI_Resume.docx')
    except Exception as e:
        return str(e), 500
