import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import marker

PLACE_URL = (
    "https://www.google.com/maps/place/%EA%B8%88%EA%B0%81%EC%82%AC/"
    "@35.0393791,135.7266146,17z/data=!3m1!4b1!4m6!3m5!1s0x6001a8195ec95eb1:0x1b0a4fa3f3a4a1d3"
    "!8m2!3d35.0393747!4d135.7291895!16zL20vMDFkNTRq"
)


class ParseTest(unittest.TestCase):
    def test_pin_coords_preferred_over_viewport(self):
        self.assertEqual(marker.parse_coords(PLACE_URL), (35.0393747, 135.7291895))

    def test_place_name(self):
        self.assertEqual(marker.parse_name(PLACE_URL), "금각사")

    def test_viewport_only(self):
        url = "https://www.google.com/maps/@37.5665,126.978,15z"
        self.assertEqual(marker.parse_coords(url), (37.5665, 126.978))

    def test_query_coords(self):
        url = "https://maps.google.com/?q=-33.8568,151.2153"
        self.assertEqual(marker.parse_coords(url), (-33.8568, 151.2153))
        self.assertIsNone(marker.parse_name(url))

    def test_query_name_without_coords(self):
        url = "https://maps.google.com/maps?q=Tokyo+Tower,+Minato&ftid=0x0:0x1"
        self.assertIsNone(marker.parse_coords(url))
        self.assertEqual(marker.parse_name(url), "Tokyo Tower")


class AddTest(unittest.TestCase):
    def test_add_and_skip_duplicate(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "places.csv"
            self.assertTrue(marker.add(PLACE_URL, path, None, "첫 방문"))
            self.assertTrue(marker.add(PLACE_URL, path, None, ""))
            rows = marker.load_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["이름"], "금각사")
            self.assertEqual(rows[0]["메모"], "첫 방문")
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_missing_coords_fails(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "places.csv"
            url = "https://www.google.com/maps/place/Somewhere/"
            self.assertFalse(marker.add(url, path, None, ""))
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
