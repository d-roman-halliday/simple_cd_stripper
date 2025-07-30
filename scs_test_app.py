# scs_test_app.py
import unittest
from scs_core import extract_discogs_id, fetch_release_data
import os

class TestDiscogsFunctions(unittest.TestCase):

    def test_extract_discogs_id_valid(self):
        self.assertEqual(extract_discogs_id("https://www.discogs.com/release/3992501-Example"), ("release", 3992501))
        self.assertEqual(extract_discogs_id("https://www.discogs.com/master/1326585-Example"), ("master", 1326585))

    def test_extract_discogs_id_invalid(self):
        with self.assertRaises(ValueError):
            extract_discogs_id("https://www.google.com")

    def test_fetch_release_data_invalid_type(self):
        with self.assertRaises(ValueError):
            fetch_release_data("invalid", 1234)

if __name__ == '__main__':
    unittest.main()
