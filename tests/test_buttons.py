"""Tests for the button catalogue (buttons.py) — no Telegram / network."""
from __future__ import annotations

import re
import unittest

import buttons
from buttons import (
    BOT_COMMANDS,
    CATEGORIES,
    R,
    REPLY_ACTIONS,
    REPLY_ROWS,
    iter_quick_searches,
    lookup_quick_search,
    quick_search_callback,
    reply_action,
)
from icons import keyboard_text, menu_text


class QuickSearchTests(unittest.TestCase):
    def test_categories_exist_and_are_non_empty(self):
        for name in ("mood", "genre", "artists_mm", "artists_int", "browse", "popular"):
            with self.subTest(category=name):
                self.assertIn(name, CATEGORIES)
                self.assertGreaterEqual(len(CATEGORIES[name]), 4)

    def test_keys_are_short_ascii_and_unique_per_category(self):
        for category, items in CATEGORIES.items():
            keys = [item.key for item in items]
            with self.subTest(category=category):
                self.assertEqual(len(keys), len(set(keys)), "duplicate key")
                for key in keys:
                    self.assertRegex(key, r"^[a-z0-9_]+$")

    def test_labels_and_queries_are_usable(self):
        for category, item in iter_quick_searches():
            with self.subTest(button=f"{category}:{item.key}"):
                self.assertTrue(item.label.strip())
                self.assertTrue(item.query.strip())
                self.assertLessEqual(len(item.query), 120)

    def test_callback_round_trip_and_telegram_limit(self):
        for category, item in iter_quick_searches():
            data = quick_search_callback(category, item.key)
            with self.subTest(data=data):
                # Telegram rejects callback_data longer than 64 *bytes*.
                self.assertLessEqual(len(data.encode("utf-8")), 64)
                self.assertEqual(lookup_quick_search(data), item)

    def test_lookup_rejects_garbage(self):
        self.assertIsNone(lookup_quick_search(""))
        self.assertIsNone(lookup_quick_search("act_menu"))
        self.assertIsNone(lookup_quick_search("qs_mood:nope"))
        self.assertIsNone(lookup_quick_search("qs_unknown:sad"))
        self.assertIsNone(lookup_quick_search("qs_mood"))


class ReplyKeyboardTests(unittest.TestCase):
    def test_every_row_button_has_an_action(self):
        labels = [label for row in REPLY_ROWS for label in row]
        self.assertEqual(len(labels), len(set(labels)), "duplicate label")
        for label in labels:
            with self.subTest(label=label):
                self.assertIn(label, REPLY_ACTIONS)
                self.assertEqual(reply_action(label), REPLY_ACTIONS[label])

    def test_reply_action_covers_the_menus(self):
        self.assertEqual(reply_action(R.SEARCH), "search")
        self.assertEqual(reply_action(R.POPULAR), "popular")
        self.assertEqual(reply_action(R.MOOD), "mood")
        self.assertEqual(reply_action(R.ARTISTS), "artists")
        self.assertEqual(reply_action(R.GENRE), "genre")
        self.assertEqual(reply_action(R.BROWSE), "browse")
        self.assertEqual(reply_action(R.AI), "ai")
        self.assertEqual(reply_action(R.HELP), "help")
        self.assertEqual(reply_action(R.MENU), "menu")

    def test_reply_action_is_tolerant_but_strict(self):
        # Surrounding spaces / a missing emoji variation selector still match…
        self.assertEqual(reply_action(f"  {R.HELP}  "), "help")
        self.assertEqual(reply_action(R.HELP.replace("\ufe0f", "")), "help")
        # …while free text (real song requests) is never hijacked.
        self.assertIsNone(reply_action("Coldplay Yellow"))
        self.assertIsNone(reply_action("စိုင်းထီးဆိုင် မိုးသီချင်း ဖွင့်ပေးပါ"))
        self.assertIsNone(reply_action(""))


class BotCommandTests(unittest.TestCase):
    def test_commands_are_telegram_legal(self):
        names = [name for name, _ in BOT_COMMANDS]
        self.assertEqual(len(names), len(set(names)), "duplicate command")
        for name, description in BOT_COMMANDS:
            with self.subTest(command=name):
                self.assertRegex(name, r"^[a-z0-9_]{1,32}$")  # BotFather rules
                self.assertTrue(description.strip())
                self.assertLessEqual(len(description), 256)

    def test_button_categories_have_matching_commands(self):
        names = {name for name, _ in BOT_COMMANDS}
        for expected in ("start", "search", "ai", "popular", "mood",
                         "artists", "genre", "browse", "keyboard", "help"):
            self.assertIn(expected, names)


class MenuTextTests(unittest.TestCase):
    def test_every_category_has_a_heading(self):
        for category in list(CATEGORIES) + ["artists"]:
            with self.subTest(category=category):
                text = menu_text(category)
                self.assertIsInstance(text, str)
                self.assertIn("<b>", text)

    def test_keyboard_card_mentions_how_to_restore(self):
        self.assertIn("/keyboard", keyboard_text())

    def test_no_stray_references(self):
        # REPLY_ACTIONS values must be routes main.py knows how to handle.
        allowed = set(CATEGORIES) | {"artists", "search", "ai", "help", "menu"}
        for action in REPLY_ACTIONS.values():
            self.assertIn(action, allowed)
        self.assertTrue(buttons.BOT_COMMANDS)


if __name__ == "__main__":
    unittest.main()
