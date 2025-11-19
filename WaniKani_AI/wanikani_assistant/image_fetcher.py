# image_fetcher.py
import os
import requests
import hashlib
from urllib.parse import urlencode
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

class ImageFetcher:
    """
    Uses Google Custom Search JSON API to fetch image URLs and download the first valid image.
    Returns (url, filename) or (None, None).
    """

    def __init__(self, api_key=None, cx=None):
        self.api_key = api_key or GOOGLE_API_KEY
        self.cx = cx or GOOGLE_CX
        if not self.api_key or not self.cx:
            raise RuntimeError("Missing GOOGLE_API_KEY or GOOGLE_CX environment variables.")
        self.session = requests.Session()

    def _search_images(self, query: str, num: int = 5):
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "searchType": "image",
            "num": num,
            "safe": "high"
        }
        url = "https://www.googleapis.com/customsearch/v1?" + urlencode(params)
        r = self.session.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("items", [])

    def _download_image(self, url: str):
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGBA")
            h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
            filename = f"img_{h}.png"
            path = os.path.join(MEDIA_DIR, filename)
            img.save(path, format="PNG")
            return path, filename
        except Exception:
            return None, None

    def search_and_download(self, query: str, seed_sentence: str = None):
        try:
            items = self._search_images(query, num=5)
            for it in items:
                link = it.get("link")
                if not link:
                    continue
                path, filename = self._download_image(link)
                if path and filename:
                    return link, filename
            return None, None
        except Exception as e:
            print("[ImageFetcher] error:", e)
            return None, None
