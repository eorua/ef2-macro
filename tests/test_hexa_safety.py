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

    def test_play_loop_unexpected_lobby_blocks_all_input(self):
        """9. 게임 진행 중 예기치 않은 lobby 감지 시 추가 입력(시작, 보상, 닫기 등) 일체 없이 즉시 중단된다."""
        lobby_path = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(lobby_path):
            lobby_img = cv2.cvtColor(cv2.imread(lobby_path), cv2.COLOR_BGR2RGB)
            orig_capture = hexa.capture
            orig_ensure = hexa.ensure_forge_open
            orig_claim = hexa.claim_and_close
            claim_calls = []
            try:
                # 첫 화면은 정상 게임 화면, 그 다음 화면은 갑작스러운 로비 화면 시뮬레이션
                game_path = os.path.join(BASE, "shots", "hexa_after_040.png")
                game_img = cv2.cvtColor(cv2.imread(game_path), cv2.COLOR_BGR2RGB)
                r_game = hexa.read_all(game_img)

                hexa.ensure_forge_open = lambda: (True, False)
                hexa.claim_and_close = lambda: claim_calls.append(True)

                # 게임 진행 중 로비가 발생한 시나리오
                screens = [lobby_img]
                hexa.capture = lambda: screens[0]
                orig_wait_settle = hexa.wait_settle
                # 게임 중 wait_settle에서 예기치 않은 로비가 감지됨
                hexa.wait_settle = lambda timeout=12, need_tray=True, hold=None: ("lobby", lobby_img, None)

                res = hexa.play(1)
                # 시작 1회(BTN_START)만 호출되고, 2회차 시작이나 보상 수령/닫기 터치는 없어야 함
                start_taps = [args for args in self.mock_taps if args == hexa.BTN_START]
                self.assertEqual(len(start_taps), 1)
                # 예기치 않은 로비에서는 claim_and_close()도 호출되지 않아야 함 (요구사항 A-2)
                self.assertEqual(len(claim_calls), 0)
            finally:
                hexa.capture = orig_capture
                hexa.ensure_forge_open = orig_ensure
                hexa.claim_and_close = orig_claim
                hexa.wait_settle = orig_wait_settle

    def test_claim_and_close_already_battle_screen(self):
        """10. 이미 전투 화면인 경우 어떠한 추가 터치도 하지 않고 즉시 성공을 반환한다."""
        fake_battle_img = np.zeros((1280, 720, 3), dtype=np.uint8)
        orig_capture = hexa.capture
        orig_adb_cap = hexa._adb_capture
        orig_icon_score = hexa.icon_score
        orig_menu_forge = hexa.menu_forge
        try:
            hexa.capture = lambda: fake_battle_img
            hexa._adb_capture = lambda: fake_battle_img
            hexa.icon_score = lambda im: (0.85, (360, 200))   # 전투 화면
            hexa.menu_forge = lambda im: (0.1, (0, 0))        # 이벤트 메뉴 없음

            ok = hexa.claim_and_close()
            self.assertTrue(ok)
            # 이미 전투 화면이므로 어떤 버튼도 탭하지 않아야 함
            self.assertEqual(len(self.mock_taps), 0)
        finally:
            hexa.capture = orig_capture
            hexa._adb_capture = orig_adb_cap
            hexa.icon_score = orig_icon_score
            hexa.menu_forge = orig_menu_forge

    def test_claim_and_close_with_active_reward_and_popup(self):
        """11. 로비에 활성 보상이 있고 팝업이 뜨는 경우: 보상 탭 -> 팝업 확인 -> 창 닫기 -> 전투 화면 복귀 검증."""
        lobby_path = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(lobby_path):
            lobby_img = cv2.cvtColor(cv2.imread(lobby_path), cv2.COLOR_BGR2RGB)
            popup_img = np.zeros((1280, 720, 3), dtype=np.uint8)
            popup_img[730:770, 300:420] = [200, 200, 200]  # 중앙 확인 버튼 영역 채움
            battle_img = np.zeros((1280, 720, 3), dtype=np.uint8)

            # 프레임 전환: 1) 초기 로비(im0) -> 2) 보상 탭 후 팝업(im_pop) -> 3) 닫기 시도 1 로비 -> 4) 전투 화면
            frames = [lobby_img, popup_img, lobby_img, battle_img]
            call_idx = [0]

            def next_frame():
                idx = min(call_idx[0], len(frames) - 1)
                call_idx[0] += 1
                return frames[idx]

            orig_capture = hexa.capture
            orig_adb_cap = hexa._adb_capture
            orig_icon_score = hexa.icon_score
            orig_menu_forge = hexa.menu_forge
            orig_is_claimable = hexa.is_reward_claimable
            try:
                hexa.capture = next_frame
                hexa._adb_capture = next_frame
                hexa.is_reward_claimable = lambda im: True  # 활성 보상 있음
                hexa.icon_score = lambda im: (0.85, (360, 200)) if im is battle_img else (0.1, (0, 0))
                hexa.menu_forge = lambda im: (0.1, (0, 0))

                ok = hexa.claim_and_close()
                self.assertTrue(ok)
                # 보상 버튼(BTN_CLAIM), 팝업 확인 버튼(360, 750), 로비 닫기(BTN_CLOSE) 탭이 순서대로 발생했는지 확인
                self.assertIn(hexa.BTN_CLAIM, self.mock_taps)
                self.assertIn((360, 750), self.mock_taps)
                self.assertIn(hexa.BTN_CLOSE, self.mock_taps)
            finally:
                hexa.capture = orig_capture
                hexa._adb_capture = orig_adb_cap
                hexa.icon_score = orig_icon_score
                hexa.menu_forge = orig_menu_forge
                hexa.is_reward_claimable = orig_is_claimable

    def test_claim_and_close_no_reward_skips_claim_tap(self):
        """12. 로비에 보상이 비활성 상태이면 보상 받기 탭을 건너뛰고 창 닫기만 수행한다."""
        lobby_path = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(lobby_path):
            lobby_img = cv2.cvtColor(cv2.imread(lobby_path), cv2.COLOR_BGR2RGB)
            battle_img = np.zeros((1280, 720, 3), dtype=np.uint8)

            # 프레임 전환: 1) 초기 로비(im0) -> 2) 닫기 시도 1 로비 -> 3) 전투 화면
            frames = [lobby_img, lobby_img, battle_img]
            call_idx = [0]

            def next_frame():
                idx = min(call_idx[0], len(frames) - 1)
                call_idx[0] += 1
                return frames[idx]

            orig_capture = hexa.capture
            orig_adb_cap = hexa._adb_capture
            orig_icon_score = hexa.icon_score
            orig_menu_forge = hexa.menu_forge
            orig_is_claimable = hexa.is_reward_claimable
            try:
                hexa.capture = next_frame
                hexa._adb_capture = next_frame
                hexa.is_reward_claimable = lambda im: False  # 보상 없음
                hexa.icon_score = lambda im: (0.85, (360, 200)) if im is battle_img else (0.1, (0, 0))
                hexa.menu_forge = lambda im: (0.1, (0, 0))

                ok = hexa.claim_and_close()
                self.assertTrue(ok)
                # BTN_CLAIM은 절대 탭하지 않아야 함
                self.assertNotIn(hexa.BTN_CLAIM, self.mock_taps)
                # 창 닫기(BTN_CLOSE)는 탭해야 함
                self.assertIn(hexa.BTN_CLOSE, self.mock_taps)
            finally:
                hexa.capture = orig_capture
                hexa._adb_capture = orig_adb_cap
                hexa.icon_score = orig_icon_score
                hexa.menu_forge = orig_menu_forge
                hexa.is_reward_claimable = orig_is_claimable

    def test_claim_and_close_failure_returns_false(self):
        """13. 로비 창을 닫아도 전투 화면으로 복귀하지 못하면 무한 반복하지 않고 False를 반환한다."""
        lobby_path = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(lobby_path):
            lobby_img = cv2.cvtColor(cv2.imread(lobby_path), cv2.COLOR_BGR2RGB)
            orig_capture = hexa.capture
            orig_adb_cap = hexa._adb_capture
            orig_icon_score = hexa.icon_score
            orig_menu_forge = hexa.menu_forge
            orig_close_event = hexa.close_event
            try:
                hexa.capture = lambda: lobby_img
                hexa._adb_capture = lambda: lobby_img
                hexa.icon_score = lambda im: (0.1, (0, 0))  # 전투 화면 복귀 영구 실패
                hexa.menu_forge = lambda im: (0.1, (0, 0))
                hexa.close_event = lambda: False            # 이벤트 닫기도 실패

                ok = hexa.claim_and_close()
                # 실패를 정확히 보고해야 함
                self.assertFalse(ok)
                # 시도 횟수는 4회로 제한되어 무한 루프에 빠지지 않아야 함
                close_taps = [args for args in self.mock_taps if args == hexa.BTN_CLOSE]
                self.assertLessEqual(len(close_taps), 4)
            finally:
                hexa.capture = orig_capture
                hexa._adb_capture = orig_adb_cap
                hexa.icon_score = orig_icon_score
                hexa.menu_forge = orig_menu_forge
                hexa.close_event = orig_close_event

    def test_normal_game_over_popup_exits_and_finishes(self):
        """14. 정상 게임오버 팝업(popup) 감지 시 나가기 버튼을 눌러 정상 완료(finished 증가) 처리된다."""
        popup_path = os.path.join(BASE, "shots", "hexa_unknown_1027_024358.png")
        lobby_path = os.path.join(BASE, "shots", "hexa_after_045.png")
        if os.path.exists(popup_path) and os.path.exists(lobby_path):
            popup_img = cv2.cvtColor(cv2.imread(popup_path), cv2.COLOR_BGR2RGB)
            lobby_img = cv2.cvtColor(cv2.imread(lobby_path), cv2.COLOR_BGR2RGB)

            # 프레임 흐름:
            # 1) 루프 1: 시작 전 로비 -> 2) 루프 2: 게임오버 팝업 -> 3) 루프 3: 나가기 후 로비 -> 종료
            frames = [lobby_img, popup_img, lobby_img, lobby_img, lobby_img]
            call_idx = [0]

            def next_frame():
                idx = min(call_idx[0], len(frames) - 1)
                call_idx[0] += 1
                return frames[idx]

            orig_capture = hexa.capture
            orig_adb_cap = hexa._adb_capture
            orig_ensure = hexa.ensure_forge_open
            orig_cam = hexa._cam
            orig_fast_on = hexa.fast_on
            orig_claim_close = hexa.claim_and_close
            claim_calls = []
            try:
                hexa.capture = next_frame
                hexa._adb_capture = next_frame
                hexa.ensure_forge_open = lambda: (True, False)
                hexa._cam = lambda: None
                hexa.fast_on = lambda: False
                hexa.claim_and_close = lambda: (claim_calls.append(True), True)[1]

                finished = hexa.play(1)
                # 정상적으로 1판 완료 보고되어야 함
                self.assertEqual(finished, 1)
                # 팝업 나가기 버튼(211, y) 탭이 발생했는지 확인
                exit_taps = [args for args in self.mock_taps if args[0] == 211]
                self.assertGreaterEqual(len(exit_taps), 1)
                # 1판 완료 후 claim_and_close 호출 확인
                self.assertEqual(len(claim_calls), 1)
            finally:
                hexa.capture = orig_capture
                hexa._adb_capture = orig_adb_cap
                hexa.ensure_forge_open = orig_ensure
                hexa._cam = orig_cam
                hexa.fast_on = orig_fast_on
                hexa.claim_and_close = orig_claim_close


if __name__ == "__main__":
    unittest.main()
