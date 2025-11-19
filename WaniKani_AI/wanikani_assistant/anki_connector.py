# anki_connector.py
import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

ANKI_URL = os.getenv("ANKI_CONNECT_URL", "http://localhost:8765")

def invoke(action: str, params: dict = None, timeout: int = 15):
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    try:
        r = requests.post(ANKI_URL, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e), "result": None}

def store_media_file(filename: str, filepath: str):
    """
    Upload local file into Anki media using storeMediaFile.
    filename: the name to use inside Anki (e.g. audio_x.mp3)
    filepath: local path
    """
    if not os.path.exists(filepath):
        return {"error": f"local file not found: {filepath}"}
    with open(filepath, "rb") as f:
        data_b64 = base64.b64encode(f.read()).decode("utf-8")
    return invoke("storeMediaFile", {"filename": filename, "data": data_b64})

def add_note(note: dict):
    """
    Add a note via AnkiConnect. `note` should match AnkiConnect note spec.
    """
    return invoke("addNote", {"note": note})

