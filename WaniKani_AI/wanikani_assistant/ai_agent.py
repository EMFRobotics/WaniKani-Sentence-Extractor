# ai_agent.py (FINAL — restored + modernized + o3-safe)
import os
from typing import List, Tuple, Optional
from openai import OpenAI

# --- ENV ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

DEFAULT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "o3-mini")

SYSTEM_PROMPT = (
    "You are a friendly Japanese grammar tutor. "
    "DO NOT explain the sentence automatically. "
    "When a sentence is given, your first response must ONLY be an invitation such as: "
    "'Let's discuss this sentence. What would you like to explore first?' "
    "Then WAIT for user questions. "
    "Keep replies short unless the user asks otherwise. "
    "Stop when the user types /anki or /skip."
)

class AIAgent:
    def __init__(self, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.enabled = client is not None
        self.is_o = self.model.startswith("o")

    # =============================================================
    # Prepare payload safely (fixes o3-mini illegal params)
    # =============================================================
    def _prepare_payload(self, history):
        payload = {
            "model": self.model,
            "messages": history,
        }

        # o models cannot accept temperature or max_tokens
        if self.is_o:
            payload["max_completion_tokens"] = 2000

        else:
            payload["max_tokens"] = 2000

        return payload

    # =============================================================
    # Extract content safely
    # =============================================================
    def _extract_content(self, response):
        """
        Returns (content or "", finish_reason)
        """
        try:
            choice = response.choices[0]
            msg = choice.message
            content = msg.content or ""
            return content.strip(), choice.finish_reason
        except Exception:
            return "", "error"

    # =============================================================
    # Start conversation loop
    # =============================================================
    def start_conversation(self, sentence: str) -> Tuple[Optional[str], List[dict]]:
        """
        Returns:
            ("CREATE_CARD", history)
            ("IMAGE_PROMPT", history)
            (None, None) on skip/exit
        """
        invite = f"Let's discuss this sentence: 「{sentence}」. What would you like to explore first?"

        # Initial history preserves your original behaviour exactly
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": invite}
        ]

        # Offline mode
        if not self.enabled:
            print("\nAI (offline):", invite)
            return invite, history

        print("\nAI:", invite)
        print("\nCommands: /anki | /skip | /image")

        # =============================================================
        # INTERACTIVE LOOP
        # =============================================================
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue

            # Commands
            if user_input.lower() == "/skip":
                return None, None
            if user_input.lower() == "/image":
                return "IMAGE_PROMPT", history
            if user_input.lower() == "/anki":
                return "CREATE_CARD", history

            # Add message to history
            history.append({"role": "user", "content": user_input})

            # =========================================================
            # Call OpenAI safely
            # =========================================================
            try:
                payload = self._prepare_payload(history)
                response = client.chat.completions.create(**payload)

                content, finish = self._extract_content(response)

                if content == "":
                    print("\n[AI ERROR] Empty response from model.")
                    print("Raw response:", response)
                    continue

                print("\nAI:", content)
                history.append({"role": "assistant", "content": content})

            except Exception as e:
                print("[AIAgent] OpenAI error:", e)
                cmd = input("Type 'retry' or '/skip': ").strip().lower()
                if cmd == "retry":
                    continue
                return None, None

    # =============================================================
    # Restore your original helper EXACTLY
    # =============================================================
    def request_card_metadata(self, sentence: str) -> str:
        return (
            f"\nPreparing an Anki card for:\n\n「{sentence}」\n\n"
            "Please answer:\n"
            "1) Target Japanese word? (exact substring)\n"
            "2) English meaning?\n"
            "3) Image idea? (/skip OK)\n"
            "4) English translation? (skip if auto-detected)\n"
        )

