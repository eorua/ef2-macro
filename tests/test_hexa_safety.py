# -*- coding: utf-8 -*-
"""유물 공방 안전성 및 입력 차단 오프라인 검증 테스트"""
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


class TestHexaSafety(unittest.TestCase):
    def setUp(self):
        hexa.load_cfg()

    def test_state_none_blocks_input(self):
        """1. 상태가 None이면 게임 입력이 발생하지 않는다."""
        black_img = np.zeros((1280, 720, 3), dtype=np.uint8)
        self.assertIsNone(V.state(black_img))
        ok, st, info, shot_path = hexa.check_game_safety(black_img, "test_none")
        self.assertFalse(ok)
        self.assertIsNone(st)

    def test_state_lobby_blocks_input(self):
        """2. 상태가 lobby이면 자동 재시작이나 추가 입력이 차단된다."""
        p = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(p):
            lobby_img = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
            self.assertEqual(V.state(lobby_img), "lobby")
            ok, st, info, shot_path = hexa.check_game_safety(lobby_img, "test_lobby")
            self.assertFalse(ok)
            self.assertEqual(st, "lobby")

    def test_incomplete_board_blocks_move(self):
        """3. 보드 인식이 불완전하면 (unk > 4) 다음 수를 실행하지 않는다."""
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

    def test_normal_game_screen_allowed(self):
        """4. 정상적인 게임 상태에서만 입력 경로가 허용된다."""
        game_path = os.path.join(BASE, "shots", "hexa_after_040.png")
        if os.path.exists(game_path):
            img = cv2.cvtColor(cv2.imread(game_path), cv2.COLOR_BGR2RGB)
            self.assertEqual(V.state(img), "game")
            ok, st, info, shot_path = hexa.check_game_safety(img, "test_normal")
            self.assertTrue(ok)
            self.assertEqual(st, "game")

    def test_drag_failure_does_not_increment_move_or_repeat(self):
        """5. 드래그 후 판이 변하지 않으면 moves가 증가하지 않고 즉시 중단된다."""
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
            orig_swipe = hexa.swipe
            orig_capture = hexa.capture
            try:
                hexa.capture = lambda: img
                hexa.wait_settle = lambda timeout=15, need_tray=True, hold=None: ("game", img, r)
                swipe_called = []
                hexa.swipe = lambda *args: swipe_called.append(args)

                res = hexa.do_move(img, r)
                self.assertFalse(res)
                self.assertEqual(hexa.STATS["moves"], initial_moves)
            finally:
                hexa.wait_settle = orig_wait_settle
                hexa.swipe = orig_swipe
                hexa.capture = orig_capture

    def test_play_loop_unexpected_lobby_no_restart(self):
        """6. 게임 진행 중 lobby 감지 시 BTN_START를 다시 누르지 않고(자동 재시작 차단) 창을 닫고 종료한다."""
        lobby_path = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(lobby_path):
            lobby_img = cv2.cvtColor(cv2.imread(lobby_path), cv2.COLOR_BGR2RGB)
            orig_capture = hexa.capture
            orig_ensure = hexa.ensure_forge_open
            orig_tap = hexa.tap
            orig_claim = hexa.claim_and_close
            tap_calls = []
            claim_calls = []
            try:
                hexa.capture = lambda: lobby_img
                hexa.ensure_forge_open = lambda: (True, False)
                hexa.tap = lambda *args: tap_calls.append(args)
                hexa.claim_and_close = lambda: claim_calls.append(True)

                res = hexa.play(1)
                # 시작 1회(BTN_START)만 호출되고, 2회차 시작(재시작)은 절대 호출되지 않아야 함
                start_taps = [args for args in tap_calls if args == hexa.BTN_START]
                self.assertEqual(len(start_taps), 1)
                # 로비 복귀 시 창 닫기(claim_and_close)가 호출되었는지 확인
                self.assertGreaterEqual(len(claim_calls), 1)
            finally:
                hexa.capture = orig_capture
                hexa.ensure_forge_open = orig_ensure
                hexa.tap = orig_tap
                hexa.claim_and_close = orig_claim


if __name__ == "__main__":
    unittest.main()
