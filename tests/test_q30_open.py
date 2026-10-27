# -*- coding: utf-8 -*-
"""patch296: 이미 열린 30퀘 줄은 누르지 않고 opened (실제 11:33 캡처 사용, 입력은 전부 mock)"""
import os, sys, unittest
from unittest.mock import patch
import cv2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import q30


class T(unittest.TestCase):
    def test_already_open_not_pressed(self):
        im = cv2.imread(os.path.join(ROOT, "shots", "q30_before.png"))
        if im is None:
            self.skipTest("캡처 없음")
        taps = []
        with patch.object(q30, "_to_bottom", return_value=im), \
             patch.object(q30.preset, "tap", side_effect=lambda *a, **k: taps.append(a)), \
             patch.object(q30, "_save"), patch("time.sleep"), patch.dict(sys.modules, {"closer": type("C", (), {"close_all": staticmethod(lambda *a: 0)})}):
            res = q30.open_quest30(say=lambda *a: None)
        self.assertEqual(res, "opened")
        self.assertFalse([t for t in taps if t and t[0] == (630, 1160)], "열린 줄의 레벨업 버튼을 눌렀음")


if __name__ == "__main__":
    unittest.main()
