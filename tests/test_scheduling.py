import unittest
from datetime import timedelta

from cards.domain.model import Grade, Review, Word
from cards.domain.scheduling import SchedulingPolicy
from tests.helpers import DAY0

A, H, G = Grade.AGAIN, Grade.HARD, Grade.GOOD


def simulate(steps):
    """Прогнать ответы (день, оценка) по одному слову и вернуть получившиеся интервалы."""
    policy = SchedulingPolicy()
    word = Word.create("en", "word", "слово", "", DAY0)
    history, intervals = [], []
    for day, grade in steps:
        today = DAY0 + timedelta(days=day)
        recent = [r for r in history if r.day >= policy.history_start(today)]
        interval = policy.next_interval(word, grade, recent, today)
        review = Review(grade, today)
        word.schedule_after(review, interval)
        history.append(review)
        intervals.append(interval)
    return intervals


class SchedulingPolicyTest(unittest.TestCase):
    def test_three_good_in_15_days_postpone_for_a_month_then_interval_doubles(self):
        steps = [(0, G), (5, G), (10, G), (40, G), (100, G), (220, G), (460, G), (825, G)]
        self.assertEqual(simulate(steps), [5, 5, 30, 60, 120, 240, 365, 365])

    def test_good_answers_older_than_15_days_do_not_count(self):
        self.assertEqual(simulate([(0, G), (7, G), (16, G), (21, G)]), [5, 5, 5, 30])

    def test_again_resets_the_streak(self):
        steps = [(0, G), (5, G), (10, A), (10, G), (15, G), (20, G)]
        self.assertEqual(simulate(steps), [5, 5, 0, 5, 5, 30])

    def test_hard_does_not_reset_the_streak(self):
        self.assertEqual(simulate([(0, G), (5, H), (6, G), (11, G)]), [5, 1, 5, 30])

    def test_several_good_answers_on_one_day_count_once(self):
        self.assertEqual(simulate([(0, G), (0, G), (0, G), (5, G)]), [5, 5, 5, 5])

    def test_hard_after_long_break_starts_a_new_streak(self):
        steps = [(0, G), (5, G), (10, G), (40, H), (41, G), (46, G), (51, G)]
        self.assertEqual(simulate(steps), [5, 5, 30, 1, 5, 5, 30])


class WordTest(unittest.TestCase):
    def test_schedule_after_review_updates_counters(self):
        word = Word.create("en", " word ", " слово ", "", DAY0)
        self.assertEqual((word.text, word.translation), ("word", "слово"))
        word.schedule_after(Review(A, DAY0), 0)
        word.schedule_after(Review(G, DAY0), 5)
        self.assertEqual(word.next_review, DAY0 + timedelta(days=5))
        self.assertEqual((word.reviews, word.lapses, word.last_review), (2, 1, DAY0))
        self.assertFalse(word.is_due(DAY0))
        word.reset(DAY0)
        self.assertTrue(word.is_due(DAY0))
        self.assertEqual(word.interval_days, 0)


if __name__ == "__main__":
    unittest.main()
