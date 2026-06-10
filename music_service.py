import os
from pathlib import Path
# CHANGE: Import OAuthCredentials alongside the base class
from ytmusicapi import YTMusic, OAuthCredentials
from dotenv import load_dotenv
import yt_dlp

# Initialize local environment state settings
load_dotenv()

class YouTubeMusicService:
    def __init__(self):
        self.api = None
        
        browser_path = Path("./browser.json")
        if browser_path.exists():
            try:
                self.api = YTMusic(str(browser_path))
                # Validate browser authentication by getting your profile name
                account_details = self.api.get_account_info()
                print("\n=============================================")
                print("   CONNECTED YOUTUBE MUSIC ACCOUNT PROFILE")
                print(f"   Name:   {account_details.get('accountName')}")
                print(f"   Handle: {account_details.get('channelHandle')}")
                print("=============================================\n")
                print("YouTube Music Service initialized successfully via Browser Session.")
                return
            except Exception as e:
                print(f"Browser authentication session read failed, checking OAuth: {e}")

        # 2. FALLBACK: Attempt Google Cloud Console OAuth Handshake
        auth_path = os.getenv("YTMUSIC_AUTH_JSON", "./oauth.json")
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if auth_path and Path(auth_path).exists() and client_id and client_secret:
            try:
                oauth_creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
                self.api = YTMusic(auth_path, oauth_credentials=oauth_creds)
                print("YouTube Music Service initialized with OAuth (Warning: may encounter server 400 errors).")
            except Exception as e:
                print(f"Failed to authenticate with YouTube Music API: {e}")
                self.api = YTMusic()
        else:
            print("Warning: Running YouTube Music in unauthenticated public mode.")
            self.api = YTMusic()

    def get_playlist_tracks(self, playlist_id):
        """Fetches tracks belonging to a given playlist profile identification string."""
        if not playlist_id: return []
        try:
            playlist_info = self.api.get_playlist(playlist_id)
            return playlist_info.get("tracks", [])
        except Exception as e:
            print(f"Error fetching tracks for playlist {playlist_id}: {e}")
            return []

    def create_playlist_for_page(self, title, description="DND Campaign Playlist"):
        """Creates a fresh cloud playlist profile returning its structural ID string."""
        if not self.api or isinstance(self.api, YTMusic) and not os.getenv("YTMUSIC_AUTH_JSON"):
            return None
        try:
            return self.api.create_playlist(title, description)
        except Exception as e:
            print(f"Error creating playlist '{title}': {e}")
            return None

    def add_track_to_playlist(self, playlist_id, video_id):
        """Appends a track element securely into a target remote cloud collection."""
        try:
            return self.api.add_playlist_items(playlist_id, [video_id])
        except Exception as e:
            print(f"Failed appending track entry {video_id} to {playlist_id}: {e}")
            return False
        
    def get_stream_url(self, video_id):
        """Uses yt-dlp to safely extract the direct, raw audio streaming URL

        from a given YouTube video identification token without downloading the file.
        """
        import yt_dlp
        if not video_id: return None
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'skip_download': True
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return info.get('url')
        except Exception as e:
            print(f"Audio stream url extraction failed for {video_id}: {e}")
            return None