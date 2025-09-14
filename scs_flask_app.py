from typing import List
from scs_core import extract_discogs_id, fetch_release_data, generate_pdf
from flask import Flask, request, jsonify, send_file, render_template
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return render_template('main_page.html'), 200

@app.route("/generate-label", methods=["POST"])
def generate_label():
    try:
        ########################################################################
        # Handle inputs
        ########################################################################
        # Handle both single URL and multiple URLs
        urls: List[str] = []

        if request.form:
            # Handle form data
            url_input = request.form.get("url")
            if url_input:
                urls = [u.strip() for u in url_input.split(',')]

        elif request.json:
            # Handle JSON data
            url_input = request.json.get("url")
            if isinstance(url_input, list):
                urls = url_input
            elif isinstance(url_input, str):
                urls = [u.strip() for u in url_input.split(',')]

        if not urls:
            return jsonify({"error": "No URLs provided"}), 400

        # Determine whether to show the yellow background for title/artist
        show_title_bg = bool(request.form.get('title_bg')=='true')

        # Determine whether to show the ruler (checking printout is not scaled incorrectly)
        show_ruler = bool(request.form.get('show_ruler') == 'true')

        ########################################################################
        # Process
        ########################################################################
        all_disc_data = []
        errors = []

        # ... fetch/prepare DiscData objects into discs list ...
        for url in urls:
            try:
                id_type, discogs_id = extract_discogs_id(url)
                disc_data = fetch_release_data(id_type, discogs_id)
                all_disc_data.extend(disc_data)
            except Exception as e:
                errors.append({"url": url, "error": str(e)})
                continue

        if not all_disc_data:
            return jsonify({
                "error": "No valid data was retrieved from any of the URLs",
                "details": errors
            }), 400

        pdf_buf = generate_pdf(all_disc_data,
                               show_title_bg=show_title_bg,
                               show_ruler=show_ruler
                              )

        # Send PDF
        response = send_file(
            pdf_buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name="jukebox_labels.pdf"
        )

        # Add warnings about any failed URLs if there were partial failures
        if errors:
            response.headers['X-Processing-Warnings'] = str(errors)

        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500