import unittest

from cards.domain.model import SUPPORTED_LANGUAGES, Grade
from cards.presentation.catalog import GRADE_BUTTONS, LANGUAGES, WORD_FIELDS


class CatalogTest(unittest.TestCase):
    def test_every_language_has_a_name_and_hints_for_every_field(self):
        self.assertEqual(tuple(info.code for info in LANGUAGES), SUPPORTED_LANGUAGES)
        fields = {spec.attribute for spec in WORD_FIELDS}
        for info in LANGUAGES:
            self.assertEqual(set(info.hints), fields, info.code)

    def test_every_grade_has_a_button(self):
        self.assertEqual({button.grade for button in GRADE_BUTTONS}, set(Grade))


if __name__ == "__main__":
    unittest.main()
