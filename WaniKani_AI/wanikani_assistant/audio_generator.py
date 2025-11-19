# audio_generator.py
import os
import random
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# gTTS fallback
try:
    from gtts import gTTS
except Exception:
    gTTS = None


def _parse_voices():
    raw = os.getenv("OPENAI_TTS_VOICES", "")
    voices = [v.strip() for v in raw.split(",") if v.strip()]
    return voices or ["alloy", "verse", "lyric"]


DEFAULT_VOICES = _parse_voices()


class AudioGenerator:
    """
    generate_audio(sentence) -> filename (relative to MEDIA_DIR) or None
    Uses OpenAI TTS if key available; falls back to gTTS.
    """

    def __init__(self, voices=None):
        self.voices = voices or DEFAULT_VOICES
        self.openai_available = client is not None

    def _safe_filename(self, sentence: str):
        safe = str(abs(hash(sentence)))[:12]
        return f"audio_{safe}.mp3"

    def generate_audio(self, sentence: str) -> str | None:
        filename = self._safe_filename(sentence)
        fullpath = os.path.join(MEDIA_DIR, filename)

        # already exists
        if os.path.exists(fullpath):
            return filename

        # ---------- OpenAI TTS ----------
        if self.openai_available:
            try:
                voice = random.choice(self.voices)

                resp = client.audio.speech.create(
                    model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                    voice=voice,
                    input=sentence,
                )

                # Correct: save using stream_to_file (2025 API)
                resp.stream_to_file(fullpath)

                return filename

            except Exception as e:
                print("[AudioGenerator] OpenAI TTS failed, falling back. Err:", e)

        # ---------- gTTS fallback ----------
        if gTTS:
            try:
                tts = gTTS(text=sentence, lang="ja")
                tts.save(fullpath)
                return filename
            except Exception as e:
                print("[AudioGenerator] gTTS failed:", e)

        return None
