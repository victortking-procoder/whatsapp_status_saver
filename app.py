from flask import Flask, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
import yt_dlp
import os
import uuid
import logging # Import logging for better error messages

app = Flask(__name__)
# Enable CORS for all origins in development. For production, specify your frontend's domain.
CORS(app) 

# Configure logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO) # Set Flask's logger level

# --- Configuration (using absolute paths) ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__)) # Get the directory where app.py resides
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt") # Absolute path to your cookies file

# Create download directory if it doesn't exist
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
    app.logger.info(f"Created download directory: {DOWNLOAD_DIR}")

# Check if the cookies file exists (crucial for debugging auth issues)
if not os.path.exists(COOKIE_FILE):
    app.logger.warning(f"WARNING: Cookies file not found at '{COOKIE_FILE}'. "
                       "Authentication with YouTube may fail. Please ensure it exists "
                       "in the same directory as app.py and is readable.")
else:
    app.logger.info(f"Cookies file found at: {COOKIE_FILE}")

# --- API Endpoint for Download ---
@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    video_url = data.get("url")

    if not video_url:
        app.logger.error("No URL provided in the request.")
        return jsonify({"success": False, "error": "No URL provided"}), 400

    app.logger.info(f"Received download request for URL: {video_url}")

    try:
        # Generate a unique identifier as a prefix for the output file
        unique_file_prefix = str(uuid.uuid4())
        # Use a template that includes unique_id, video title, and video ID for clarity and uniqueness
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique_file_prefix}_%(title)s-%(id)s.%(ext)s")

        # yt-dlp options
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # Prioritize MP4, combine best audio/video
            'cookiefile': COOKIE_FILE, # **CORRECTED OPTION: Use 'cookiefile' for path**
            'noplaylist': True,        # Ensure only single video is downloaded
            'verbose': True,           # **IMPORTANT: Enable verbose output for debugging!**
                                       # This will print yt-dlp's detailed logs to your Flask console.
            'retries': 3,              # Retry downloads a few times on network issues
            # Your original headers were already good, yt-dlp can use these directly or via http_headers
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'accept_language': 'en-US,en;q=0.9', # Directly supported yt-dlp option
            'buffersize': 1048576,     # 1MB buffer, can sometimes help with performance
        }

        app.logger.info(f"Starting yt-dlp download for: {video_url} with options: {ydl_opts}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            # Extract the actual downloaded file path
            # yt-dlp returns the path in 'requested_downloads' for combined formats
            # or directly in 'filepath' for single-file downloads.
            final_downloaded_path = None
            if info.get('requested_downloads'):
                final_downloaded_path = info['requested_downloads'][0].get('filepath')
            elif info.get('filepath'):
                final_downloaded_path = info['filepath']

            if not final_downloaded_path or not os.path.exists(final_downloaded_path):
                raise Exception("Downloaded file path could not be determined or file not found after download.")

            # Get just the basename (filename) to use in the URL
            filename_for_url = os.path.basename(final_downloaded_path)

        # Construct the download URL for the frontend using url_for
        # This will map to the new /files/<filename> route below
        download_url = url_for('serve_downloaded_file', filename=filename_for_url, _external=True)

        app.logger.info(f"Download successful. File: {filename_for_url}. Serving URL: {download_url}")
        return jsonify({"success": True, "download_url": download_url, "title": info.get('title', 'Video')})

    except yt_dlp.utils.DownloadError as e:
        app.logger.error(f"yt-dlp Download Error for {video_url}: {e}")
        error_message = str(e)
        if "confirm you're not a bot" in error_message or "sign in" in error_message.lower():
            # Provide a more specific message if it looks like a cookie/bot issue
            return jsonify({"success": False, "error": "Authentication required or bot detection triggered. "
                                                       "Please ensure your cookies.txt is fresh and valid."}), 500
        return jsonify({"success": False, "error": f"Download failed: {error_message}"}), 500
    except yt_dlp.utils.ExtractorError as e:
        app.logger.error(f"yt-dlp Extractor Error for {video_url}: {e}")
        return jsonify({"success": False, "error": f"Could not extract video information: {e}"}), 500
    except Exception as e:
        app.logger.error(f"An unexpected server error occurred during download of {video_url}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {e}"}), 500

# --- New Route to Serve Downloaded Files ---
# This is a dedicated endpoint to serve the dynamically generated video files.
@app.route("/files/<path:filename>", methods=["GET"])
def serve_downloaded_file(filename):
    """
    Serves files from the DOWNLOAD_DIR securely using send_from_directory.
    """
    try:
        app.logger.info(f"Attempting to serve file: {filename} from {DOWNLOAD_DIR}")
        # as_attachment=True will prompt the browser to download the file
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        app.logger.error(f"File not found: {filename} in {DOWNLOAD_DIR}")
        return jsonify({"success": False, "error": "File not found."}), 404
    except Exception as e:
        app.logger.error(f"Error serving file {filename}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Error serving file."}), 500


if __name__ == "__main__":
    # For local testing, run Flask in debug mode.
    # In production, use a WSGI server like Gunicorn or uWSGI.
    # IMPORTANT: This setup blocks the server during download. For production,
    # consider the Celery/Redis solution provided previously.
    app.run(debug=True, host='0.0.0.0', port=5000)