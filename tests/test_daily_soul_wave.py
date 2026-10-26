# -*- coding: utf-8 -*-
"""tests/test_daily_soul_wave.py - 영혼의 휴식 중 웨이브 6500 제한 무시 단위 테스트 (patch294h)"""
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import daily


class TestDailySoulWave(unittest.TestCase):
    def setUp(self):
        daily.IN_SOUL = False
        daily.MAX_WAVE = 6500
        # 가상 더미 이미지 (720x1280x3)
        self.dummy_img = np.zeros((1280, 720, 3), dtype=np.uint8)

    @patch("daily.blocked", return_value=False)
    @patch("daily.get_wave", return_value=7599)
    def test_normal_mode_blocks_over_6500(self, mock_wave, mock_blocked):
        """일반 모드(휴식 중 아님)에서는 웨이브 7599 >= 6500 이면 safe_wave_ok 가 False"""
        with patch("daily.is_in_soul", return_value=False):
            with patch("time.sleep"):
                res = daily.safe_wave_ok(self.dummy_img)
                self.assertFalse(res, "일반 모드에서는 6500 이상일 때 차단되어야 함")

    @patch("daily.blocked", return_value=False)
    @patch("daily.get_wave", return_value=7599)
    def test_soul_mode_allows_over_6500(self, mock_wave, mock_blocked):
        """영혼의 휴식 중에는 웨이브 7599 >= 6500 이어도 safe_wave_ok 가 True 로 통과"""
        with patch("daily.is_in_soul", return_value=True):
            res = daily.safe_wave_ok(self.dummy_img)
            self.assertTrue(res, "영혼의 휴식 중에는 6500 이상이어도 숙제 진행 허용되어야 함")

    @patch("daily.blocked", return_value=True)
    def test_soul_mode_still_blocks_if_screen_blocked(self, mock_blocked):
        """영혼의 휴식 중이라도 성 함락 등 팝업으로 차단된 상태(blocked=True)이면 False"""
        with patch("daily.is_in_soul", return_value=True):
            res = daily.safe_wave_ok(self.dummy_img)
            self.assertFalse(res, "팝업 차단(blocked)은 휴식 중이어도 안전하게 중단되어야 함")


if __name__ == "__main__":
    unittest.main()
