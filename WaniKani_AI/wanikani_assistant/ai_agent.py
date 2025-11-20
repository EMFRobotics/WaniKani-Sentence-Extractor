# ai_agent.py
# Minimal, robust: embed the user's English into the system prompt and force JP->EN mapping.

import os
from typing import List, Tuple, Optional
from openai import OpenAI

# --- ENV ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

DEFAULT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

# Base system instructions (kept minimal and strict)
SYSTEM_PROMPT_BASE = (
    "You are a helpful, literal Japanese→English mapping assistant.\n\n"
    "RULES (CRITICAL & NON-NEGOTIABLE):\n"
    "- The English sentence provided by the user is the authoritative meaning for this Japanese sentence.\n"
    "- You MUST NOT paraphrase, rewrite, substitute, or improve the English sentence in any way.\n"
    "- You MUST NOT output any alternative English translation.\n"
    "- Your ONLY task is to explain exactly which Japanese word(s) or phrase(s) correspond to which exact word(s) or phrase(s) in the provided English sentence.\n"
    "- Output a clear, concise mapping list (Japanese token/phrase -> exact substring(s) from the user's English), and a one-line reason for each mapping.\n"
    "- Ask the user to confirm the mapping at the end: 'Does this mapping match your intention?'\n"
    "- Keep output short and literal unless the user explicitly requests more detail.\n"
)

class AIAgent:
    def __init__(self, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.enabled = client is not None
        # o-series (gpt-4o, o3-mini, etc.) usually disallow temperature or max_tokens — detect by leading 'o'
        self.is_o = bool(self.model and self.model.lower().startswith("o"))

    # =============================================================
    # Build a single strict system message embedding the user English (no separate context block)
    # =============================================================
    def _build_system_message(self, jp_sentence: str, eng_translation: str) -> str:
        # embed both JP and EN, with a final strict instruction. Do not include any extra suggestions.
        return (
            SYSTEM_PROMPT_BASE
            + "\n\n"
            f"JAPANESE SENTENCE (DO NOT ALTER): {jp_sentence}\n"
            f"ENGLISH SENTENCE (AUTHORITATIVE — DO NOT ALTER): {eng_translation}\n\n"
            "INSTRUCTIONS FOR THE ASSISTANT:\n"
            "1) Produce a numbered list of mappings in the exact form:\n"
            "   1) 「<Japanese substring>」 -> \"<exact substring from the provided English>\" — <one-line reason>\n"
            "2) Only include mappings where the Japanese substring actually appears in the JP sentence and the English substring exactly appears in the provided English sentence.\n"
            "3) If a Japanese substring corresponds to multiple words in English, include the exact contiguous substring from the provided English. Never invent words.\n"
            "4) If there is no direct correspondence for a particular Japanese token, explicitly state: 'No direct English substring; relates to overall meaning.'\n"
            "5) End with the single question: 'Does this mapping match your intention?'\n"
        )

    # =============================================================
    # Prepare payload safely (o-series compatibility + low temperature for non-o models)
    # =============================================================
    def _prepare_payload(self, history):
        payload = {
            "model": self.model,
            "messages": history,
        }

        # configure deterministic/low-temperature behaviour for non-o models
        if not self.is_o:
            # small temperature -> deterministic answers
            payload["temperature"] = 0.0
            payload["max_tokens"] = 800

        # for o-series, use max_completion_tokens instead (and do not include temperature)
        if self.is_o:
            payload["max_completion_tokens"] = 800

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
            return content.strip(), getattr(choice, "finish_reason", None)
        except Exception:
            return "", "error"

    # =============================================================
    # Start conversation loop (JP+EN embedded into system prompt)
    # =============================================================
    def start_conversation(self, sentence: str, english: str) -> Tuple[Optional[str], List[dict]]:
        """
        Returns:
            ("CREATE_CARD", history)
            ("IMAGE_PROMPT", history)
            (None, None) on skip/exit
        """
        # Build the strict system message that includes the exact user English
        system_message = self._build_system_message(sentence, english)

        invite = f"Let's discuss this sentence: 「{sentence}」. What would you like to explore first?"

        # Start history with the strict system message and an assistant invitation
        history = [
            {"role": "system", "content": system_message},
            {"role": "assistant", "content": invite}
        ]

        # Offline mode: just print and return minimal history so tests can proceed
        if not self.enabled:
            print("\nAI (offline):", invite)
            return invite, history

        print("\nAI:", invite)
        print("\nCommands: /anki | /skip | /image")

        # Simple interactive loop — user drives the conversation
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue

            # Commands
            cmd = user_input.lower()
            if cmd == "/skip":
                return None, None
            if cmd == "/image":
                return "IMAGE_PROMPT", history
            if cmd == "/anki":
                return "CREATE_CARD", history

            # Append user message and call the API
            history.append({"role": "user", "content": user_input})

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
                retry = input("Type 'retry' or '/skip': ").strip().lower()
                if retry == "retry":
                    continue
                return None, None

    # =============================================================
    # Prepare metadata for Anki card — now includes EN context parameter
    # =============================================================
    def request_card_metadata(self, sentence: str, english: str) -> str:
        return (
            f"\nPreparing an Anki card for:\n\n"
            f"JP: 「{sentence}」\n"
            f"EN: {english}\n\n"
            "Please answer:\n"
            "1) Target Japanese word? (exact substring)\n"
            "2) English meaning?\n"
            "3) Image idea? (/skip OK)\n"
            "4) English translation? (skip if auto-detected)\n"
        )


