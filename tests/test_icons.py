"""Tests for the icon/message styling layer."""
from __future__ import annotations

import unittest
from html.parser import HTMLParser

import icons
from icons import (
    ai_answer_text,
    brain_status_text,
    caption_text,
    download_text,
    error_text,
    esc,
    fmt_duration,
    help_text,
    no_results_text,
    prompt_text,
    recommend_text,
    results_text,
    safe_trim,
    track_label,
    welcome_text,
)


class _Parser(HTMLParser):
    """Minimal HTML well-formedness check (unclosed tags are tolerated by TG)."""

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass


class IconTests(unittest.TestCase):
    def test_escape(self):
        self.assertEqual(esc('<b>&"'), "&lt;b&gt;&amp;\"")
        self.assertEqual(esc(None), "")

    def test_safe_trim_keeps_burmese_combining_marks(self):
        text = "က" * 60
        out = safe_trim(text, 20)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 20)
        self.assertFalse(out[-2] == "\u1031")  # never cut before a vowel sign

    def test_duration(self):
        self.assertEqual(fmt_duration(0), "")
        self.assertEqual(fmt_duration(215), "3:35")
        self.assertEqual(fmt_duration(3725), "1:02:05")

    def test_track_label_has_number_and_duration(self):
        label = track_label(0, "Yellow", 260)
        self.assertIn("1️⃣", label)
        self.assertIn("4:20", label)
        self.assertIn("🎵", label)

    def test_all_templates_are_strings(self):
        templates = [
            welcome_text(),
            help_text("gemini"),
            brain_status_text("local", False, ""),
            brain_status_text("gemini", True, "gemini-2.5-flash"),
            results_text("Coldplay", 5, "local", 0),
            no_results_text("Coldplay", "local"),
            ai_answer_text("မင်္ဂလာပါ 👋", "gemini"),
            recommend_text("ဒီလေးတွေ 🎶", ["a", "b", "c"], "local"),
            caption_text("Yellow", "Coldplay", 260),
            download_text(0), download_text(1), download_text(2),
            error_text("search"), error_text("download", "boom"),
            prompt_text("search"), prompt_text("ai"),
        ]
        for text in templates:
            self.assertIsInstance(text, str)
            self.assertTrue(text.strip())
            parser = _Parser()
            parser.feed(text)

    def test_user_content_is_escaped(self):
        dangerous = "<script>alert(1)</script>"
        for text in (
            results_text(dangerous, 1, "local"),
            no_results_text(dangerous, "local"),
            caption_text(dangerous, dangerous),
            ai_answer_text(dangerous, "local"),
            recommend_text(dangerous, [dangerous], "local"),
            error_text("search", dangerous),
        ):
            self.assertNotIn("<script>", text)
            self.assertIn("&lt;script&gt;", text)

    def test_icons_are_customisable_in_one_place(self):
        original = icons.I.BOT
        try:
            icons.I.BOT = "🐱"
            self.assertEqual(icons.I.BOT, "🐱")
        finally:
            icons.I.BOT = original


if __name__ == "__main__":
    unittest.main()
