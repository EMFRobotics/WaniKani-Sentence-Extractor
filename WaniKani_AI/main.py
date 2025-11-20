#!/usr/bin/env python3
import os
import sys
import time
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

from wanikani_assistant.clipboard_listener import ClipboardListener
from wanikani_assistant.ai_agent import AIAgent
from wanikani_assistant.image_fetcher import ImageFetcher
from wanikani_assistant.audio_generator import AudioGenerator

# Config - change if you want
DECK_NAME = os.getenv("WK_DECK_NAME", "Test Script Wk deck")
SVENSKA_MODEL_NAME = os.getenv("SVENSKA_MODEL_NAME", "Basic+")
ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL", "http://localhost:8765")
MEDIA_FOLDER = "media"

os.makedirs(MEDIA_FOLDER, exist_ok=True)


def safe_input(prompt=""):
    try:
        return input(prompt)
    except EOFError:
        return ""


# ---------------------
# Anki helpers
# ---------------------
def invoke_anki(action, params=None, anki_url=ANKI_CONNECT_URL):
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    try:
        r = requests.post(anki_url, json=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("[AnkiConnect error]", e)
        return {"error": str(e), "result": None}


def store_media_file(filename, filepath):
    if not os.path.exists(filepath):
        print(f"[store_media_file] file not found: {filepath}")
        return False
    with open(filepath, "rb") as f:
        data_b64 = base64.b64encode(f.read()).decode("utf-8")
    resp = invoke_anki("storeMediaFile", {"filename": filename, "data": data_b64})
    if resp.get("error"):
        print("[store_media_file] Anki error:", resp["error"])
        return False
    return True


def add_note_to_anki(deck_name, model_name, fields: dict, tags=None):
    note = {
        "deckName": deck_name,
        "modelName": model_name,
        "fields": fields,
        "options": {"allowDuplicate": False},
        "tags": tags or []
    }
    resp = invoke_anki("addNote", {"note": note})
    if resp.get("error"):
        print("[add_note_to_anki] error:", resp["error"])
        return False, resp
    return True, resp


# ---------------------
# Main app
# ---------------------
def main():
    print("Starting WaniKani Assistant (Svenska flow). Ctrl+C to quit.\n")
    listener = ClipboardListener()
    ai = AIAgent()

    try:
        img_fetcher = ImageFetcher()
    except Exception as e:
        print("ImageFetcher unavailable:", e)
        img_fetcher = None

    tts = AudioGenerator()

    print("Listening for copied Japanese sentences...")

    try:
        for clipboard_text in listener.listen():

            # -------------------------
            # Parse clipboard
            # -------------------------
            lines = [l.strip() for l in (clipboard_text or "").split("\n") if l.strip()]
            if not lines:
                continue

            jp_sentence = lines[0]
            eng_sentence_auto = lines[1] if len(lines) >= 2 else ""

            print("\n=== New sentence detected ===")
            print("JP:", jp_sentence)
            if eng_sentence_auto:
                print("EN:", eng_sentence_auto)

            # Start conversation
            conv_result, history = ai.start_conversation(jp_sentence, eng_sentence_auto)
            if conv_result is None and history is None:
                print("No card created. Listening...\n")
                continue

            # -------------------------
            # IMAGE PROMPT flow
            # -------------------------
            if conv_result == "IMAGE_PROMPT":
                image_idea = safe_input("Enter image idea (or /skip): ").strip()
                if image_idea.lower() == "/skip" or image_idea == "":
                    image_idea = None

                target_word = None
                english_word = ""
                eng_translation = eng_sentence_auto

            # -------------------------
            # NORMAL /anki flow
            # -------------------------
            else:
                print("\nPreparing to create card. Please answer:")
                if hasattr(ai, "request_card_metadata"):
                    print(ai.request_card_metadata(jp_sentence, eng_sentence_auto))

                target_word = safe_input("1) Target Japanese word (exact substring from sentence): ").strip()
                english_word = safe_input("2) English meaning of that word: ").strip()

                image_idea = safe_input("3) Image idea (or /skip): ").strip()
                if image_idea.lower() == "/skip" or image_idea == "":
                    image_idea = None

                if eng_sentence_auto:
                    print(f"Auto-detected English translation: {eng_sentence_auto}")
                    eng_translation = eng_sentence_auto
                else:
                    eng_translation = safe_input("4) English translation of the entire sentence: ").strip()

            # -------------------------
            # IMAGE FETCH
            # -------------------------
            image_filename = None
            if image_idea and img_fetcher:
                print("Searching for image for:", image_idea)
                try:
                    url, image_filename = img_fetcher.search_and_download(image_idea, jp_sentence)
                except Exception as e:
                    print("Image fetch error:", e)
                    image_filename = None
                if image_filename:
                    print("Downloaded image:", image_filename)
                else:
                    print("No image found.")
            elif image_idea and not img_fetcher:
                print("Image idea provided but ImageFetcher unavailable.")

            # -------------------------
            # AUDIO GENERATION
            # -------------------------
            print("Generating sentence audio...")
            audio_filename = None
            try:
                audio_filename = tts.generate_audio(jp_sentence)
            except Exception as e:
                print("TTS failed:", e)
                audio_filename = None

            # -------------------------
            # BUILD CARD FIELDS
            # -------------------------
            if target_word and target_word in jp_sentence:
                highlighted_example = jp_sentence.replace(
                    target_word,
                    f'<b><span style="color:red;">{target_word}</span></b>'
                )
            else:
                highlighted_example = jp_sentence

            back_swe_value = (
                f'<b><span style="color:orange;">{target_word}</span></b>'
                if target_word else ""
            )

            STYLE_WRAPPER_START = '<div style="background:black; color:orange;">'
            STYLE_WRAPPER_END = '</div>'

            fields = {
                "Front[ENG]": f"{STYLE_WRAPPER_START}{english_word}{STYLE_WRAPPER_END}",
                "Image": "",
                "Back[SWE]": f"{STYLE_WRAPPER_START}{back_swe_value}{STYLE_WRAPPER_END}",
                "Examples": f"{STYLE_WRAPPER_START}{highlighted_example}{STYLE_WRAPPER_END}",
                "Audio": "",
                "Example English": f"{STYLE_WRAPPER_START}{eng_translation}{STYLE_WRAPPER_END}",
                "Audio Example": "",
                "Grammar": ""
            }

            # -------------------------
            # MEDIA UPLOAD
            # -------------------------
            if image_filename:
                image_path = os.path.join(MEDIA_FOLDER, image_filename)
                ok = store_media_file(image_filename, image_path)
                if ok:
                    fields["Image"] = f'<img src="{image_filename}">'

            if audio_filename:
                audio_path = os.path.join(MEDIA_FOLDER, audio_filename)
                ok = store_media_file(audio_filename, audio_path)
                if ok:
                    fields["Audio Example"] = f"[sound:{audio_filename}]"

            # Ensure no None values
            for k in fields:
                if fields[k] is None:
                    fields[k] = ""

            # -------------------------
            # ADD TO ANKI
            # -------------------------
            print("Adding card to Anki deck:", DECK_NAME)
            ok, resp = add_note_to_anki(DECK_NAME, SVENSKA_MODEL_NAME, fields, tags=["wanikani", "auto"])
            if ok:
                print("✓ Card created! Note ID:", resp.get("result"))
            else:
                print("✗ Failed to create card:", resp)

            print("\nListening for copied Japanese sentences...\n")

    except KeyboardInterrupt:
        print("\nExiting. おつかれさまでした！")
    except Exception as e:
        print("Fatal error:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()


