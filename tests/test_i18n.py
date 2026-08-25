import unittest

from macro_recorder.i18n import LANGUAGES, TRANSLATIONS


class TranslationTests(unittest.TestCase):
    def test_all_languages_have_the_same_keys(self):
        english_keys = set(TRANSLATIONS["en"])
        for code in LANGUAGES.values():
            self.assertEqual(set(TRANSLATIONS[code]), english_keys)

    def test_supported_languages_are_present(self):
        self.assertEqual(LANGUAGES["English"], "en")
        self.assertEqual(LANGUAGES["繁體中文"], "zh_TW")


if __name__ == "__main__":
    unittest.main()
