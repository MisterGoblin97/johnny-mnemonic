import unittest

from cards.application.dictionary import Dictionary
from cards.domain.model import DuplicateWordError, Grade, InvalidWordError, Review, WordNotFoundError
from tests.helpers import DAY0, FakeClock, memory_repository


class DictionaryTest(unittest.TestCase):
    def setUp(self):
        self.words = memory_repository(self)
        self.clock = FakeClock()
        self.dictionary = Dictionary(self.words, self.clock)

    def test_add_trims_text_and_puts_word_into_todays_queue(self):
        word = self.dictionary.add("en", "  apple ", " яблоко ", " An apple a day ")
        self.assertIsNotNone(word.id)
        stored = self.dictionary.get(word.id)
        self.assertEqual((stored.text, stored.translation, stored.example),
                         ("apple", "яблоко", "An apple a day"))
        self.assertTrue(stored.is_due(DAY0))

    def test_word_and_translation_are_required(self):
        with self.assertRaises(InvalidWordError):
            self.dictionary.add("en", "  ", "яблоко")
        with self.assertRaises(InvalidWordError):
            self.dictionary.add("en", "apple", "")
        with self.assertRaises(ValueError):
            self.dictionary.add("de", "Apfel", "яблоко")

    def test_duplicates_are_case_insensitive_within_a_language(self):
        self.dictionary.add("fr", "Ёлка", "ель")
        self.dictionary.add("fr", "Straße", "улица")
        for text in ("ёЛКА", "STRASSE"):
            with self.assertRaises(DuplicateWordError):
                self.dictionary.add("fr", text, "x")
        self.dictionary.add("en", "ёлка", "fir tree")  # в другом языке — можно

    def test_edit_can_move_word_to_another_language(self):
        word = self.dictionary.add("fr", "table", "стол")
        self.dictionary.edit(word.id, "fr", "Table", "стол", "")  # то же слово — не дубликат
        self.dictionary.edit(word.id, "en", "table", "стол", "a wooden table")
        self.assertEqual(self.dictionary.count("fr"), 0)
        self.assertEqual(self.dictionary.get(word.id).example, "a wooden table")
        other = self.dictionary.add("fr", "table", "стол")
        with self.assertRaises(DuplicateWordError):
            self.dictionary.edit(other.id, "en", "TABLE", "стол")
        with self.assertRaises(WordNotFoundError):
            self.dictionary.edit(9999, "en", "x", "y")

    def test_repeat_today_resets_progress(self):
        word = self.dictionary.add("en", "apple", "яблоко")
        word.schedule_after(Review(Grade.GOOD, DAY0), 30)
        self.words.save_review(word, Review(Grade.GOOD, DAY0))
        self.clock.advance(3)
        self.dictionary.repeat_today([word.id])
        stored = self.dictionary.get(word.id)
        self.assertEqual((stored.interval_days, stored.next_review), (0, self.clock.today))

    def test_delete_removes_history_too(self):
        word = self.dictionary.add("en", "apple", "яблоко")
        self.words.save_review(word, Review(Grade.GOOD, DAY0))
        self.dictionary.delete([word.id])
        self.assertIsNone(self.dictionary.get(word.id))
        self.assertEqual(self.words.history(word.id, DAY0), [])

    def test_search_ignores_case_and_special_characters(self):
        for text, translation in (("apple", "Яблоко"), ("100%", "сто процентов"), ("pear", "груша")):
            self.dictionary.add("en", text, translation)
        self.assertEqual([w.text for w in self.dictionary.search("en", "ЯБЛ")], ["apple"])
        self.assertEqual([w.text for w in self.dictionary.search("en", "%")], ["100%"])
        self.assertEqual([w.text for w in self.dictionary.search("en")], ["100%", "apple", "pear"])


if __name__ == "__main__":
    unittest.main()
