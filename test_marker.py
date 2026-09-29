import unittest
from unittest import mock
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


MOBILE_URL = (
    "https://www.google.com/maps/place/%EC%99%80%ED%83%80%EB%82%98%EB%B2%A0%EC%B9%B4%EB%A0%88"
    "+2+Chome-2-5+Sonezakishinchi,+Kita+Ward,+Osaka/data=!4m2!3m1!1s0x6000e6f320eaaaab:0x7c1945593b9e0795"
    "!18m1!1e1?utm_source=mstt_1&entry=gps"
)
class AddTest(unittest.TestCase):
    def test_mobile_link_without_coords_fails(self):
        # 모바일 공유 링크는 좌표가 없다. 페이지 HTML에 뭐가 있든 추측해서 넣으면 안 된다.
        page = ";window.APP_INITIALIZATION_STATE=[[[3000.0,127.1365632,35.8486769]]]"
        with TemporaryDirectory() as d, mock.patch.object(marker, "fetch", return_value=(MOBILE_URL, page)):
            path = Path(d) / "places.csv"
            ok, message = marker.add("https://maps.app.goo.gl/NEecvr66Yyj8yvus6", path)
            self.assertFalse(ok)
            self.assertIn("좌표를 찾지 못했습니다", message)
            self.assertFalse(path.exists())

    def test_add_and_skip_duplicate(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "places.csv"
            self.assertTrue(marker.add(PLACE_URL, path, note="첫 방문", tag="명소/절")[0])
            ok, message = marker.add(PLACE_URL, path)
            self.assertTrue(ok)
            self.assertIn("건너뜀", message)
            rows = marker.load_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["이름"], "금각사")
            self.assertEqual(rows[0]["메모"], "첫 방문")
            self.assertEqual(rows[0]["태그"], "명소/절")
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_missing_coords_fails(self):
        url = "https://www.google.com/maps/place/Somewhere/"
        with TemporaryDirectory() as d, mock.patch.object(marker, "fetch", return_value=(url, "<html></html>")):
            path = Path(d) / "places.csv"
            self.assertFalse(marker.add(url, path)[0])
            self.assertFalse(path.exists())

    def test_fetch_error_is_reported(self):
        with TemporaryDirectory() as d, mock.patch.object(marker, "fetch", side_effect=OSError("timeout")):
            ok, message = marker.add("https://maps.app.goo.gl/x", Path(d) / "places.csv")
            self.assertFalse(ok)
            self.assertIn("timeout", message)


if __name__ == "__main__":
    unittest.main()
