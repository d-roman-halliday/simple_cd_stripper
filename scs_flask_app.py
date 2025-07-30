from scs_core import extract_discogs_id, fetch_release_data, generate_pdf
from flask import Flask, request, jsonify, send_file, render_template

# Flask frontend
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return render_template('main_page.html'), 200

@app.route("/generate-label", methods=["POST"])
def generate_label():
    try:
        url = request.form.get("url") or (request.json and request.json.get("url"))
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        id_type, discogs_id = extract_discogs_id(url)
        data = fetch_release_data(id_type, discogs_id)
        pdf_buf = generate_pdf(data)

        return send_file(pdf_buf, mimetype='application/pdf', as_attachment=True, download_name="jukebox_labels.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500