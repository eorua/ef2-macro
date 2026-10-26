# -*- coding: utf-8 -*-
"""유물 공방 안전성 및 입력 차단 오프라인 검증 테스트 (완전 Mock 적용)"""
import os
import sys
import unittest
import numpy as np
import cv2

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import hexa
import hexa_vision as V


class MockProcessResult:
    stdout = b"emulator-5586 device\n"
    returncode = 0


class TestHexaSafety(unittest.TestCase):
    def setUp(self):
        hexa.load_cfg()
        hexa.SERIAL = "emulator-5586"
        # 모든 실제 기기 입력 및 외부 프로세스 호출을 안전하게 Mock 처리
        self._orig_tap = hexa.tap
        self._orig_swipe = hexa.swipe
        self._orig_adb = hexa.adb
        self._orig_run = hexa._run
        self.mock_taps = []
        self.mock_swipes = []
        self.mock_adbs = []
        hexa.tap = lambda *args: self.mock_taps.append(args)
        hexa.swipe = lambda *args: self.mock_swipes.append(args)
        hexa.adb = lambda *args, **kw: self.mock_adbs.append(args)
        hexa._run = lambda *args, **kw: MockProcessResult()

    def tearDown(self):
        hexa.tap = self._orig_tap
        hexa.swipe = self._orig_swipe
        hexa.adb = self._orig_adb
        hexa._run = self._orig_run

    def test_state_none_blocks_input(self):
        """1. 상태가 None이면 게임 입력이 발생하지 않는다."""
        black_img = np.zeros((1280, 720, 3), dtype=np.uint8)
        self.assertIsNone(V.state(black_img))
        ok, st, info, shot_path = hexa.check_game_safety(black_img, "test_none")
        self.assertFalse(ok)
        self.assertIsNone(st)
        self.assertEqual(len(self.mock_taps), 0)
        self.assertEqual(len(self.mock_swipes), 0)

    def test_state_lobby_blocks_input(self):
        """2. 상태가 lobby이면 게임 입력 경로가 차단된다."""
        p = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(p):
            lobby_img = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
            self.assertEqual(V.state(lobby_img), "lobby")
            ok, st, info, shot_path = hexa.check_game_safety(lobby_img, "test_lobby")
            self.assertFalse(ok)
            self.assertEqual(st, "lobby")
            self.assertEqual(len(self.mock_taps), 0)
            self.assertEqual(len(self.mock_swipes), 0)

    def test_state_popup_blocks_input(self):
        """3. '공방 마감' 화면을 popup으로 정상 인식하고 게임 입력이 차단된다."""
        p = os.path.join(BASE, "shots", "hexa_unknown_1027_024358.png")
        if os.path.exists(p):
            popup_img = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
            self.assertEqual(V.state(popup_img), "popup")
            ok, st, info, shot_path = hexa.check_game_safety(popup_img, "test_popup")
            self.assertFalse(ok)
            self.assertEqual(st, "popup")
            self.assertEqual(len(self.mock_taps), 0)
            self.assertEqual(len(self.mock_swipes), 0)

    def test_incomplete_board_blocks_move(self):
        """4. 보드 인식이 불완전하면 (unk > 4) 다음 수를 실행하지 않는다."""
        game_path = os.path.join(BASE, "shots", "hexa_after_040.png")
        if os.path.exists(game_path):
            img = cv2.cvtColor(cv2.imread(game_path), cv2.COLOR_BGR2RGB)
            for idx in [0, 1, 2, 3, 4, 5]:
                cx, cy = hexa.E.pix(idx)
                img[cy - 20:cy + 20, cx - 50:cx + 20] = [255, 0, 255]
            b, unk = V.read_board(img)
            self.assertGreater(len(unk), 4)
            ok, st, info, shot_path = hexa.check_game_safety(img, "test_incomplete")
            self.assertFalse(ok)
            self.assertEqual(st, "low_confidence")
            self.assertEqual(len(self.mock_taps), 0)
            self.assertEqual(len(self.mock_swipes), 0)

    def test_normal_game_screen_allowed(self):
        """5. 정상적인 게임 상태에서만 입력 경로가 허용된다."""
        game_path = os.path.join(BASE, "shots", "hexa_after_040.png")
        if os.path.exists(game_path):
            img = cv2.cvtColor(cv2.imread(game_path), cv2.COLOR_BGR2RGB)
            self.assertEqual(V.state(img), "game")
            ok, st, info, shot_path = hexa.check_game_safety(img, "test_normal")
            self.assertTrue(ok)
            self.assertEqual(st, "game")

    def test_drag_failure_does_not_increment_move_or_repeat(self):
        """6. 드래그 후 판이 변하지 않으면 moves가 증가하지 않고 즉시 중단된다."""
        game_path = os.path.join(BASE, "shots", "hexa_after_040.png")
        if os.path.exists(game_path):
            img = cv2.cvtColor(cv2.imread(game_path), cv2.COLOR_BGR2RGB)
            r = hexa.read_all(img)
            p = V.Piece([((0, 0), 1)])
            p.dot_idx = 0
            r["tray"] = p
            initial_moves = 10
            hexa.STATS["moves"] = initial_moves

            orig_wait_settle = hexa.wait_settle
            orig_capture = hexa.capture
            try:
                hexa.capture = lambda: img
                hexa.wait_settle = lambda timeout=15, need_tray=True, hold=None: ("game", img, r)

                res = hexa.do_move(img, r)
                # 판이 변하지 않았으므로 do_move는 False 반환해야 함
                self.assertFalse(res)
                # 이동 횟수는 절대 증가하지 않아야 함
                self.assertEqual(hexa.STATS["moves"], initial_moves)
            finally:
                hexa.wait_settle = orig_wait_settle
                hexa.capture = orig_capture

    def test_mismatch_result_blocks_move_increment(self):
        """7. 드래그 결과가 예상과 불일치(hit is None)하면 moves 증가 없이 안전 중단된다."""
        game_path = os.path.join(BASE, "shots", "hexa_after_040.png")
        if os.path.exists(game_path):
            img = cv2.cvtColor(cv2.imread(game_path), cv2.COLOR_BGR2RGB)
            r = hexa.read_all(img)
            p = V.Piece([((0, 0), 1)])
            p.dot_idx = 0
            r["tray"] = p
            initial_moves = 10
            hexa.STATS["moves"] = initial_moves

            # 다른 임의의 보드(불일치 보드) 생성
            r_diff = dict(r)
            b_diff = list(r["board"])
            b_diff[0] = 99  # 완전히 엉뚱한 보드 결과
            r_diff["board"] = b_diff

            orig_wait_settle = hexa.wait_settle
            orig_capture = hexa.capture
            orig_check_result = hexa.check_result
            try:
                hexa.capture = lambda: img
                hexa.wait_settle = lambda timeout=15, need_tray=True, hold=None: ("game", img, r_diff)
                hexa.check_result = lambda *args: None  # hit is None 강제

                res = hexa.do_move(img, r)
                self.assertFalse(res)
                # 불일치 시 이동 성공으로 기록하지 않아야 함
                self.assertEqual(hexa.STATS["moves"], initial_moves)
            finally:
                hexa.wait_settle = orig_wait_settle
                hexa.capture = orig_capture
                hexa.check_result = orig_check_result

    def test_play_loop_breaks_on_move_failure(self):
        """8. do_move가 실패(False)를 반환하면 play 루프가 무한 반복하지 않고 즉시 종료된다."""
        game_path = os.path.join(BASE, "shots", "hexa_after_040.png")
        if os.path.exists(game_path):
            img = cv2.cvtColor(cv2.imread(game_path), cv2.COLOR_BGR2RGB)
            r = hexa.read_all(img)
            orig_capture = hexa.capture
            orig_ensure = hexa.ensure_forge_open
            orig_wait_settle = hexa.wait_settle
            orig_do_move = hexa.do_move
            do_move_calls = []
            try:
                hexa.capture = lambda: img
                hexa.ensure_forge_open = lambda: (True, False)
                hexa.wait_settle = lambda timeout=12, need_tray=True, hold=None: ("game", img, r)
                hexa.do_move = lambda *args: (do_move_calls.append(True), False)[1]  # False 반환

                res = hexa.play(1)
                # do_move가 False를 반환했으므로 1회만 호출되고 무한 루프 없이 break 되어야 함
                self.assertEqual(len(do_move_calls), 1)
            finally:
                hexa.capture = orig_capture
                hexa.ensure_forge_open = orig_ensure
                hexa.wait_settle = orig_wait_settle
                hexa.do_move = orig_do_move

    def test_play_loop_unexpected_lobby_no_restart(self):
        """9. 게임 진행 중 lobby 감지 시 BTN_START를 다시 누르지 않고 안전하게 창 닫기 후 종료된다."""
        lobby_path = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(lobby_path):
            lobby_img = cv2.cvtColor(cv2.imread(lobby_path), cv2.COLOR_BGR2RGB)
            orig_capture = hexa.capture
            orig_ensure = hexa.ensure_forge_open
            orig_claim = hexa.claim_and_close
            claim_calls = []
            try:
                hexa.capture = lambda: lobby_img
                hexa.ensure_forge_open = lambda: (True, False)
                hexa.claim_and_close = lambda: claim_calls.append(True)

                res = hexa.play(1)
                # 시작 1회(BTN_START)만 호출되고, 2회차 시작은 절대 호출되지 않아야 함
                start_taps = [args for args in self.mock_taps if args == hexa.BTN_START]
                self.assertEqual(len(start_taps), 1)
                # 로비 복귀 시 창 닫기(claim_and_close)가 호출되었는지 확인
                self.assertGreaterEqual(len(claim_calls), 1)
            finally:
                hexa.capture = orig_capture
                hexa.ensure_forge_open = orig_ensure
                hexa.claim_and_close = orig_claim


if __name__ == "__main__":
    unittest.main()
