"""Dependency-free tests for the AI brain (no network, no API key)."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from ai_brain import (
    AIResult,
    LLMModelUnavailable,
    MusicAI,
    _parse_json_object,
    build_youtube_query,
    clean_query,
    local_think,
)
from config import Settings


def settings(**env) -> Settings:
    with patch("config.load_dotenv"), patch.dict(os.environ, env, clear=True):
        return Settings.from_env()


class ConfigTests(unittest.TestCase):
    def test_no_key_means_local(self):
        cfg = settings()
        self.assertEqual(cfg.resolved_provider(), "local")
        self.assertEqual(MusicAI(cfg).provider, "local")

    def test_provider_specific_key_autodetected(self):
        for key, expected in (
            ("GEMINI_API_KEY", "gemini"),
            ("GROQ_API_KEY", "groq"),
            ("OPENAI_API_KEY", "openai"),
        ):
            with self.subTest(key=key):
                self.assertEqual(settings(**{key: "secret"}).resolved_provider(), expected)

    def test_explicit_local_wins_over_key(self):
        cfg = settings(AI_PROVIDER="local", AI_API_KEY="secret")
        self.assertEqual(cfg.resolved_provider(), "local")

    def test_generic_key_defaults_to_gemini(self):
        self.assertEqual(settings(AI_API_KEY="secret").resolved_provider(), "gemini")

    def test_custom_provider_and_aliases(self):
        self.assertEqual(settings(AI_API_KEY="x", AI_PROVIDER="openrouter").resolved_provider(), "openrouter")
        self.assertEqual(settings(AI_API_KEY="x", AI_PROVIDER="google").resolved_provider(), "gemini")
        self.assertEqual(settings(AI_API_KEY="x", AI_PROVIDER="my-server").resolved_provider(), "custom")

    def test_bot_link_and_id(self):
        cfg = settings(BOT_TOKEN="123456789:FAKE", BOT_USERNAME="@GoiiMusicBot")
        self.assertEqual(cfg.bot_username, "GoiiMusicBot")
        self.assertEqual(cfg.bot_link, "https://t.me/GoiiMusicBot")
        self.assertEqual(cfg.bot_id, "123456789")
        self.assertEqual(settings().bot_link, "")

    def test_result_limits(self):
        self.assertLessEqual(settings(MAX_SEARCH_RESULTS="99").max_results, 8)


class LocalBrainTests(unittest.TestCase):
    def test_plain_song_is_a_search(self):
        result = local_think("Taylor Swift blank space")
        self.assertEqual(result.intent, "search")
        self.assertEqual(result.search_query, "Taylor Swift blank space")
        self.assertTrue(result.wants_search)
        self.assertEqual(result.source, "local")

    def test_english_fillers_removed(self):
        self.assertEqual(clean_query("Please play Coldplay Yellow official audio"), "Coldplay Yellow")
        self.assertEqual(clean_query("please play some songs by eminem"), "Eminem")

    def test_burmese_fillers_removed_but_titles_kept(self):
        self.assertEqual(
            clean_query("စိုင်းထီးဆိုင် မိုးသီချင်း ဖွင့်ပေးပါ"),
            "စိုင်းထီးဆိုင် မိုးသီချင်း",
        )
        self.assertEqual(clean_query("cold play ရဲ့ သီချင်းလေး ဖွင့်ပေးပါဗျ"), "Coldplay")

    def test_artist_typo_correction(self):
        self.assertEqual(clean_query("cold play"), "Coldplay")
        self.assertEqual(clean_query("billie eilish bad guy"), "Billie Eilish bad guy")

    def test_mood_becomes_recommendation(self):
        result = local_think("စိတ်ပျက်နေတယ် သီချင်းလေးညွှန်းပေးပါ")
        self.assertEqual(result.intent, "recommend")
        self.assertEqual(len(result.suggestions), 3)
        self.assertIn("sad", result.search_query)

    def test_mood_in_english(self):
        self.assertEqual(local_think("I need a chill playlist").intent, "recommend")

    def test_question_is_info_and_still_offers_a_search(self):
        result = local_think("ဒီသီချင်းကို ဘယ်သူဆိုတာလဲ?")
        self.assertEqual(result.intent, "info")
        self.assertTrue(result.search_query)
        self.assertIn("AI_API_KEY", result.reply)

    def test_greeting_is_chat(self):
        self.assertEqual(local_think("မင်္ဂလာပါ").intent, "chat")
        self.assertEqual(local_think("hello").intent, "chat")

    def test_force_chat_never_searches_directly(self):
        result = local_think("Coldplay Yellow", force_chat=True)
        self.assertEqual(result.intent, "info")
        self.assertFalse(result.wants_search)

    def test_specific_song_is_not_a_recommendation(self):
        result = local_think("please play some songs by eminem")
        self.assertEqual(result.intent, "search")
        self.assertEqual(result.search_query, "Eminem")


class ParsingTests(unittest.TestCase):
    def test_fenced_json(self):
        raw = '```json\n{"intent": "search", "reply": "ok"}\n```'
        self.assertEqual(_parse_json_object(raw)["intent"], "search")

    def test_chatty_preamble(self):
        raw = 'Sure! Here is the answer: {"intent":"info","reply":"hello"} Hope it helps.'
        self.assertEqual(_parse_json_object(raw)["intent"], "info")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            _parse_json_object("no json here")

    def test_from_llm_normalises_intent_and_clamps(self):
        data = {
            "intent": "search_song",
            "search_query": "  **Coldplay Yellow**  ",
            "reply": "**ရှာပေးနေပါတယ်**",
            "suggestions": ["a", "b", "c", "d"],
        }
        result = AIResult.from_llm(data, "gemini", "fallback query")
        self.assertEqual(result.intent, "search")
        self.assertEqual(result.search_query, "Coldplay Yellow")
        self.assertEqual(len(result.suggestions), 3)
        self.assertNotIn("*", result.reply)
        self.assertEqual(result.source, "gemini")

    def test_from_llm_falls_back_to_user_text(self):
        result = AIResult.from_llm({"intent": "search", "search_query": ""}, "gemini", "original words")
        self.assertEqual(result.search_query, "original words")


class QueryHelperTests(unittest.TestCase):
    def test_latin_query_gets_hint(self):
        self.assertEqual(build_youtube_query("Coldplay Yellow"), "Coldplay Yellow official audio")

    def test_burmese_query_is_untouched(self):
        self.assertEqual(build_youtube_query("စိုင်းထီးဆိုင်"), "စိုင်းထီးဆိုင်")

    def test_existing_hint_is_not_duplicated(self):
        self.assertEqual(build_youtube_query("Coldplay live"), "Coldplay live")

    def test_pages_give_different_results(self):
        self.assertNotEqual(build_youtube_query("Coldplay", 0), build_youtube_query("Coldplay", 1))


class CloudBrainTests(unittest.IsolatedAsyncioTestCase):
    def _gemini_response(self, payload: dict) -> dict:
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}

    async def test_gemini_returns_structured_result(self):
        cfg = settings(AI_API_KEY="fake", AI_PROVIDER="gemini")
        payload = {
            "intent": "info",
            "search_query": "Sai Htee Saing",
            "reply": "သူက ရှမ်းအဆိုတော်တစ်ယောက်ပါ။",
            "suggestions": ["Sai Htee Saing songs"],
        }
        with patch("ai_brain._post_json", return_value=self._gemini_response(payload)):
            result = await MusicAI(cfg).think("စိုင်းထီးဆိုင်က ဘယ်သူလဲ")
        self.assertEqual(result.source, "gemini")
        self.assertEqual(result.intent, "info")
        self.assertEqual(result.search_query, "Sai Htee Saing")

    async def test_api_failure_falls_back_to_local(self):
        cfg = settings(AI_API_KEY="fake", AI_PROVIDER="gemini")
        with patch("ai_brain._post_json", side_effect=OSError("offline")):
            result = await MusicAI(cfg).think("မင်္ဂလာပါ")
        self.assertEqual(result.source, "local")
        self.assertEqual(result.intent, "chat")

    async def test_retired_model_falls_through_to_next(self):
        cfg = settings(AI_API_KEY="fake", AI_PROVIDER="gemini")
        good = self._gemini_response({"intent": "search", "search_query": "Coldplay", "reply": "ok"})
        calls = []

        def fake_post(url, headers, payload, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise LLMModelUnavailable(404, "model not found")
            return good

        with patch("ai_brain._post_json", side_effect=fake_post):
            result = await MusicAI(cfg).think("Coldplay")
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.source, "gemini")

    async def test_recommend_gets_default_suggestions_if_llm_omits_them(self):
        cfg = settings(AI_API_KEY="fake", AI_PROVIDER="gemini")
        payload = {"intent": "recommend", "reply": "ဒီလေးတွေ နားထောင်ကြည့်ပါ", "suggestions": []}
        with patch("ai_brain._post_json", return_value=self._gemini_response(payload)):
            result = await MusicAI(cfg).think("သီချင်းညွှန်းပေးပါ")
        self.assertEqual(len(result.suggestions), 3)
        self.assertTrue(result.search_query)


if __name__ == "__main__":
    unittest.main()
