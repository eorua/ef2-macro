import unittest, os, sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, r"C:\macro")
import cv2
import barracks


class TestBarracksKeep20(unittest.TestCase):
    def test_unit_ocr_offline(self):
        """실제 스크린샷 2종에 대해 Tesseract OCR 보유 수량 판정 검증"""
        undead_path = os.path.join(r"C:\macro\shots", "barracks_undead.png")
        golem_path = os.path.join(r"C:\macro\shots", "barracks_golem.png")
        if not os.path.exists(undead_path) or not os.path.exists(golem_path):
            self.skipTest("shots 이미지 파일 없음")

        im_u = cv2.imread(undead_path)
        im_g = cv2.imread(golem_path)

        # undead: yc=1121 -> total 19 (< 20 이므로 가용 0마리)
        tot_u, vals_u = barracks.read_unit_total(im_u, 1121)
        self.assertEqual(tot_u, 19)
        self.assertEqual(max(0, tot_u - 20), 0)

        # golem: yc=862 -> total 49 (49 - 20 = 29마리 가용)
        tot_g, vals_g = barracks.read_unit_total(im_g, 862)
        self.assertEqual(tot_g, 49)
        self.assertEqual(max(0, tot_g - 20), 29)

    @patch("barracks.open_barracks", return_value=True)
    @patch("barracks.set_races_for", return_value=True)
    @patch("barracks.capture")
    @patch("barracks.locate", return_value=900)
    @patch("barracks.tap_multi")
    @patch("barracks._sleep")
    def test_deploy_min_keep_limit(self, mock_sleep, mock_tap, mock_loc, mock_cap, mock_races, mock_open):
        """min_keep 조건에 따른 가용 수량 제한 및 생략 검증"""
        # Case 1: 보유 18마리, min_keep=20 -> 가용 0마리 -> 배치 0
        with patch("barracks.read_unit_total", return_value=(18, [18, 0, 0, 0, 0])):
            mock_cap.return_value = MagicMock()
            with patch("barracks.is_full", return_value=False):
                with patch("barracks.unit_score", return_value=0.9):
                    got = barracks.deploy("hand", 4, min_keep=20)
                    self.assertEqual(got, 0)
                    mock_tap.assert_not_called()

        mock_tap.reset_mock()

        # Case 2: 보유 23마리, min_keep=20 -> 가용 3마리 -> 4명 요청해도 3명만 배치
        with patch("barracks.read_unit_total", return_value=(23, [23, 0, 0, 0, 0])):
            mock_cap.return_value = MagicMock()
            with patch("barracks.is_full", side_effect=[False, False, True]):
                with patch("barracks.unit_score", return_value=0.9):
                    got = barracks.deploy("hand", 4, min_keep=20)
                    self.assertEqual(got, 3)

    @patch("barracks.release_tail", return_value=True)
    @patch("barracks.close_barracks", return_value=True)
    @patch("barracks.snap", return_value=MagicMock())
    @patch("barracks.capture", return_value=MagicMock())
    @patch("barracks.barracks_open", return_value=False)
    @patch("barracks.is_full", return_value=True)
    def test_phase1_mixed_allocation(self, mock_full, mock_bk_open, mock_cap, mock_snap, mock_close, mock_rel):
        """phase1 골렘 & 죽음의 손 혼합 및 부족분 대체 로직 검증"""
        # Case 1: 둘 다 넉넉할 때 (골렘 4 + 죽손 4)
        def mock_deploy_rich(key, n, min_keep=0):
            return n

        with patch("barracks.deploy", side_effect=mock_deploy_rich) as m_dep:
            ok = barracks.phase1()
            self.assertTrue(ok)
            # golem 4 -> hand 4
            calls = m_dep.call_args_list
            self.assertEqual(calls[0][0], ("golem", 4))
            self.assertEqual(calls[1][0], ("hand", 4))

        # Case 2: 죽음의 손이 부족할 때 (골렘 4 -> 죽손 0 -> 골렘 4 추가)
        def mock_deploy_hand_empty(key, n, min_keep=0):
            if key == "hand":
                return 0
            return n

        with patch("barracks.deploy", side_effect=mock_deploy_hand_empty) as m_dep:
            ok = barracks.phase1()
            self.assertTrue(ok)
            calls = m_dep.call_args_list
            # 1: golem 4
            self.assertEqual(calls[0][0], ("golem", 4))
            # 2: hand 4 -> 0 반환
            self.assertEqual(calls[1][0], ("hand", 4))
            # 3: golem 추가 4 시도
            self.assertEqual(calls[2][0], ("golem", 4))


if __name__ == "__main__":
    unittest.main()
