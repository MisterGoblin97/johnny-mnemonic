import unittest

from cards.application.dictionary import Dictionary
from cards.application.study import StudySession
from cards.domain.model import Grade
from cards.domain.scheduling import SchedulingPolicy
from tests.helpers import FakeClock, keep_order, memory_repository


class StudySessionTest(unittest.TestCase):
    def setUp(self):
        self.words = memory_repository(self)
        self.clock = FakeClock()
        self.dictionary = Dictionary(self.words, self.clock)
        self.session = StudySession(self.words, SchedulingPolicy(), "en", self.clock, keep_order)

    def add(self, *texts, language="en"):
        return [self.dictionary.add(language, text, f"перевод {text}") for text in texts]

    def test_again_returns_card_to_the_end_of_todays_queue(self):
        self.add("one", "two")
        self.session.reload()
        self.assertEqual((self.session.current.text, self.session.remaining), ("one", 2))
        self.assertEqual(self.session.grade(Grade.AGAIN), 0)
        self.assertEqual([self.session.current.text, self.session.remaining], ["two", 2])
        self.session.grade(Grade.GOOD)
        self.assertEqual(self.session.current.text, "one")
        self.session.grade(Grade.GOOD)
        self.assertIsNone(self.session.current)
        self.assertEqual(self.session.reviewed, 3)

    def test_preview_matches_the_real_answer_and_third_good_gives_a_month(self):
        self.add("word")
        for expected in (5, 5, 30):
            self.session.reload()
            self.assertEqual(self.session.preview(Grade.GOOD), expected)
            self.assertEqual(self.session.grade(Grade.GOOD), expected)
            self.clock.advance(expected)
        stats = self.session.stats()
        self.assertEqual((stats.total, stats.learned), (1, 1))

    def test_reload_keeps_current_card_first(self):
        self.add("one", "two", "three")
        self.session.reload()
        self.session.grade(Grade.GOOD)  # «one» ушла, на экране «two»
        self.add("four")
        self.session.invalidate()
        self.assertTrue(self.session.refresh())
        self.assertEqual(self.session.current.text, "two")
        self.assertEqual(self.session.remaining, 3)
        self.assertFalse(self.session.refresh())  # ничего не менялось

    def test_empty_queue_is_refilled_on_a_new_day(self):
        self.add("word")
        self.session.reload()
        self.session.grade(Grade.HARD)
        self.assertIsNone(self.session.current)
        self.assertEqual(self.session.next_review_date(), self.clock.today.replace(day=2))
        self.clock.advance(1)
        self.assertTrue(self.session.refresh())
        self.assertEqual(self.session.current.text, "word")

    def test_deleted_word_is_skipped(self):
        one, _two = self.add("one", "two")
        self.session.reload()
        self.session.grade(Grade.AGAIN)  # «one» снова в конце очереди
        self.dictionary.delete([one.id])
        self.session.grade(Grade.GOOD)
        self.assertIsNone(self.session.current)

    def test_languages_have_separate_queues(self):
        self.add("apple")
        self.add("pomme", "poire", language="fr")
        self.session.reload()
        self.assertEqual(self.session.remaining, 1)
        self.assertEqual(self.session.due_in_other_languages(), {"fr": 2})
        self.session.switch_language("fr")
        self.assertEqual(self.session.remaining, 2)
        self.assertEqual(self.session.due_in_other_languages(), {"en": 1})


if __name__ == "__main__":
    unittest.main()
