import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pytube import YouTube
import os 
import time
from googleapiclient.discovery import build

# Spotify authentication
scope = "user-library-read"
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id='YOUR_CLIENT_ID', client_secret='YOUR_CLIENT_SECRET'))
liked_tracks = sp.current_user_saved_tracks()

# Function to search for a song on YouTube and extract video URLs
def search_on_youtube(song_name, api_key):
    youtube = build('youtube', 'v3', developerKey=api_key)
    request = youtube.search().list(q=song_name, part='snippet', type='video', maxResults=1)
    response = request.execute()
    video_urls = []
    for item in response['items']:
        video_id = item['id']['videoId']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_urls.append(video_url)
        time.sleep(1)  # Add a delay between requests
    return video_urls

# Function to extract song names from Spotify tracks
def extract_song_names(liked_tracks):
    if liked_tracks is None:
        return []
    return [item['track']['name'] for item in liked_tracks['items']]

# Function to download audio from YouTube
def download_audio(video_urls, output_directory):
    try:
        yt = YouTube(video_urls)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if audio_stream:
            audio_stream.download(output_directory)
            print("Audio downloaded successfully.")
        else:
            print("No audio stream available for the provided URL.")
    except Exception as e:
        print("An error occurred:", str(e))



liked_songs = extract_song_names(liked_tracks)
for song_name in liked_songs:
    print(f"Searching for '{song_name}' on YouTube...")
    video_urls = search_on_youtube(song_name, 'YOUTUBE_API')
    output_directory = "audio_files"
    if video_urls:
        print("Found the following videos:")
        for url in video_urls:
            print(url)
            if not os.path.exists(output_directory):
              os.makedirs(output_directory)
            download_audio(url, output_directory)
    else:
        print("No videos found.")
    print()


