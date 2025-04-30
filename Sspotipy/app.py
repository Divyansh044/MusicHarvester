from flask import Flask, request, redirect, url_for, send_file, jsonify, render_template
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import zipfile
import shutil
import logging
from googleapiclient.discovery import build
from dotenv import load_dotenv
import uuid
import yt_dlp
# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24))
origins = os.getenv("ALLOWED_ORIGINS", "").split(",")

CORS(app, resources={r"/*": {"origins": origins}})
# Constants
SPOTIFY_REDIRECT_URI = os.environ.get('SPOTIFY_REDIRECT_URI')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')

# Session and status storage
user_sessions = {}
download_status = {}

@app.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')

@app.route('/authorize', methods=['POST'])
def authorize():
    """Initiate Spotify authorization flow."""
    try:
        data = request.json
        client_id = data.get('client_id')
        client_secret = data.get('client_secret')
        
        if not client_id or not client_secret:
            return jsonify({"error": "Spotify client ID and secret are required"}), 400
        
        # Create a unique session ID for this user
        session_id = str(uuid.uuid4())
        
        # Initialize SpotifyOAuth
        sp_oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="user-library-read",
            state=session_id  # Pass session_id as state parameter
        )
        
        # Get authorization URL
        auth_url = sp_oauth.get_authorize_url()
        
        # Store credentials in session
        user_sessions[session_id] = {
            'client_id': client_id,
            'client_secret': client_secret,
            'sp_oauth': sp_oauth
        }
        
        return jsonify({
            "session_id": session_id,
            "auth_url": auth_url
        })
    
    except Exception as e:
        logger.error(f"Authorization error: {str(e)}")
        return jsonify({"error": f"Authorization failed: {str(e)}"}), 500

@app.route('/callback')
def callback():
    """Handle Spotify OAuth callback."""
    code = request.args.get('code')
    session_id = request.args.get('state')  # Using state parameter to pass session_id
    
    if not session_id or session_id not in user_sessions:
        return render_template('index.html', error="Session expired. Please try again.")
    
    try:
        sp_oauth = user_sessions[session_id]['sp_oauth']
        token_info = sp_oauth.get_access_token(code)
        access_token = token_info['access_token']
        
        # Store access token in session
        user_sessions[session_id]['access_token'] = access_token
        
        return render_template('success.html', session_id=session_id)
    
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        return render_template('index.html', error=f"Authorization failed: {str(e)}")

@app.route('/download/<session_id>', methods=['GET'])
def download_liked_songs(session_id):
    """Download Spotify liked songs as audio from YouTube."""
    if session_id not in user_sessions:
        return jsonify({"error": "Invalid or expired session"}), 401
    
    session_data = user_sessions[session_id]
    access_token = session_data.get('access_token')
    
    if not access_token:
        return jsonify({"error": "Missing access token. Please authorize first."}), 401
    
    # Initialize status
    download_status[session_id] = {
        "status": "started",
        "total": 0,
        "completed": 0,
        "message": "Starting download process"
    }
    
    # Create unique directories for this download
    download_dir = f"audio_files_{session_id}"
    zip_filename = f"spotify_songs_{session_id}.zip"
    
    try:
        # Create Spotify client
        sp = spotipy.Spotify(auth=access_token)
        logger.debug("Spotify client created successfully.")
        
        # Fetch liked tracks with additional info
        results = sp.current_user_saved_tracks(limit=10)  # Limited to 10 for faster processing
        tracks = results['items']
        
        if not tracks:
            download_status[session_id].update({
                "status": "error",
                "message": "No liked songs found in your Spotify account"
            })
            return jsonify({"error": "No liked songs found in your Spotify account"}), 404
        
        # Process tracks to get both name and artist
        songs = []
        for item in tracks:
            track = item['track']
            artist = track['artists'][0]['name']
            name = track['name']
            songs.append({
                'name': name,
                'artist': artist,
                'query': f"{name} {artist} official audio"
            })
        
        logger.debug(f"Fetched {len(songs)} liked songs.")
        
        # Update status
        download_status[session_id].update({
            "status": "downloading",
            "total": len(songs),
            "message": f"Found {len(songs)} songs to download"
        })
        
        # Prepare download directory with unique name to avoid conflicts
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)
        os.makedirs(download_dir)
        
        # Download songs
        downloaded_count = 0
        for song in songs:
            try:
                logger.debug(f"Searching '{song['query']}' on YouTube...")
                video_url = search_on_youtube(song['query'], YOUTUBE_API_KEY)
                
                if video_url:
                    logger.debug(f"Downloading audio for {song['name']}")
                    filename = f"{song['artist']} - {song['name']}"
                    if download_audio(video_url, download_dir, filename):
                        downloaded_count += 1
                        download_status[session_id].update({
                            "completed": downloaded_count,
                            "message": f"Downloaded {downloaded_count}/{len(songs)}"
                        })
                    time.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error(f"Error downloading {song['name']}: {str(e)}")
                continue
        
        # Check if any songs were downloaded
        downloaded_files = os.listdir(download_dir)
        if not downloaded_files:
            download_status[session_id].update({
                "status": "error",
                "message": "No songs were downloaded. YouTube search or download failed."
            })
            return jsonify({"error": "No songs were downloaded. YouTube search or download failed."}), 500
        
        logger.debug(f"Successfully downloaded {downloaded_count} out of {len(songs)} songs.")
        
        # Update status for zipping
        download_status[session_id].update({
            "status": "zipping",
            "message": "Creating zip file"
        })
        
        # Create zip file
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in downloaded_files:
                    file_path = os.path.join(download_dir, file)
                    zipf.write(file_path, arcname=file)
            
            logger.debug(f"Created zip file with {len(downloaded_files)} songs.")
            
            # Update status for completion
            download_status[session_id].update({
                "status": "complete",
                "message": f"Download complete. {downloaded_count} songs downloaded."
            })
            
            # Send zip file
            return send_file(
                zip_filename, 
                as_attachment=True,
                download_name="spotify_liked_songs.zip"
            )
        
        except Exception as e:
            logger.error(f"Error creating zip: {str(e)}")
            download_status[session_id].update({
                "status": "error",
                "message": f"Zip creation failed: {str(e)}"
            })
            return jsonify({"error": f"Zip creation failed: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Download process error: {str(e)}")
        download_status[session_id].update({
            "status": "error",
            "message": f"Download process failed: {str(e)}"
        })
        return jsonify({"error": f"Download process failed: {str(e)}"}), 500
    
    finally:
        # Clean up temporary files
        try:
            if os.path.exists(download_dir):
                shutil.rmtree(download_dir)
            # We don't immediately remove the zip file to ensure it's properly sent
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

@app.route('/download-status/<session_id>', methods=['GET'])
def get_download_status(session_id):
    """Get the current status of a download."""
    if session_id not in download_status:
        return jsonify({"status": "not_started"}), 200
    
    return jsonify(download_status[session_id]), 200

@app.route('/status/<session_id>', methods=['GET'])
def check_status(session_id):
    """Check if session is valid and authorized."""
    if session_id not in user_sessions:
        return jsonify({"valid": False}), 200
    
    session_data = user_sessions[session_id]
    is_authorized = 'access_token' in session_data
    
    return jsonify({
        "valid": True,
        "authorized": is_authorized
    }), 200

def search_on_youtube(query, api_key=None):
    try:
        if api_key:
            try:
                youtube = build('youtube', 'v3', developerKey=api_key)
                request = youtube.search().list(
                    q=query,
                    part='snippet',
                    type='video',
                    maxResults=1
                )
                response = request.execute()
                
                if response.get('items'):
                    video_id = response['items'][0]['id']['videoId']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    logger.debug(f"Found video via API: {video_url}")
                    return video_url
            except Exception as e:
                logger.warning(f"YouTube API search failed: {str(e)}, falling back to pytube search")
        
        # Fallback to pytube's Search
        logger.warning(f"No YouTube results found for: {query}")
        return None
    
    except Exception as e:
        logger.error(f"YouTube search error: {str(e)}")
        return None

def download_audio(video_url, output_directory, filename_prefix):
    """Download audio from YouTube video using yt-dlp."""
    try:
        # Create a safe filename
        safe_filename = "".join([c for c in filename_prefix if c.isalpha() or c.isdigit() or c==' ' or c=='-']).rstrip()
        if len(safe_filename) > 100:
            safe_filename = safe_filename[:100]

        output_path = os.path.join(output_directory, f"{safe_filename}.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'ffmpeg_location': r'E:\MusicHarvester\Sspotipy\ffmpeg-master-latest-win64-gpl-shared\ffmpeg-master-latest-win64-gpl-shared\bin', 
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }
            ],
            'quiet': True,
            'noplaylist': True,
            'continuedl': True,
            'retries': 3,
            'fragment_retries': 3,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        logger.debug(f"Successfully downloaded: {safe_filename}")
        return True

    except Exception as e:
        logger.error(f"Audio download error with yt-dlp: {str(e)}")
        return False

# Add cleanup route for removing zip files after some time
@app.route('/cleanup/<session_id>', methods=['POST'])
def cleanup_files(session_id):
    """Clean up zip files after they've been downloaded."""
    zip_filename = f"spotify_songs_{session_id}.zip"
    
    if os.path.exists(zip_filename):
        try:
            os.remove(zip_filename)
            return jsonify({"message": "Cleanup successful"}), 200
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
            return jsonify({"error": f"Cleanup failed: {str(e)}"}), 500
    
    return jsonify({"message": "No files to clean up"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)