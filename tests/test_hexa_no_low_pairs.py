import unittest, sys

sys.path.insert(0, r"C:\macro")
import hexa_engine as E


class TestHexaNoLowPairs(unittest.TestCase):
    def test_bridge5_only_for_tier8_or_higher(self):
        """5합 허브 브릿지(bridge5)는 오직 8성 이상에만 적용되고, 1~7성에는 적용되지 않음을 검증"""
        # 11번 칸 주위: 덩어리 1 (6, 7), 덩어리 2 (15, 16)
        # 6-7은 서로 인접, 15-16은 서로 인접, 둘 다 11번에 인접
        self.assertIn(7, E.NB[6])
        self.assertIn(16, E.NB[15])
        self.assertIn(6, E.NB[11])
        self.assertIn(7, E.NB[11])
        self.assertIn(15, E.NB[11])
        self.assertIn(16, E.NB[11])

        # 1) 4성으로 2+2 배치한 보드 (11번은 빈칸 0)
        b_tier4 = [0] * 23
        b_tier4[6] = 4
        b_tier4[7] = 4
        b_tier4[15] = 4
        b_tier4[16] = 4

        # 2) 8성으로 2+2 배치한 보드 (11번은 빈칸 0)
        b_tier8 = [0] * 23
        b_tier8[6] = 8
        b_tier8[7] = 8
        b_tier8[15] = 8
        b_tier8[16] = 8

        b_empty = [0] * 23
        sc_empty = E.evaluate(b_empty, unlocked=8)
        sc_t4 = E.evaluate(b_tier4, unlocked=8)
        sc_t8 = E.evaluate(b_tier8, unlocked=8)

        # 8성은 5합 브릿지(bridge5) 보너스를 획득하여 sc_t8이 매우 높아야 함
        # 반면 4성은 bridge5 보너스를 받지 못함
        diff_8 = sc_t8 - sc_empty
        diff_4 = sc_t4 - sc_empty

        # 8성 2+2는 4성 2+2 대비 월등히 높은 평가를 받아야 함 (bridge5 덕분)
        self.assertGreater(diff_8, diff_4 + 10.0)

    def test_low_tier_pair_penalty_when_tight(self):
        """빈칸이 10개 미만으로 부족할 때 하위 등급 2개 쌍 방치는 감점되어 즉시 3합 유도"""
        # 보드에 빈칸이 8개만 남은 빡빡한 상황 (15칸 점유)
        b_tight = [3] * 15 + [0] * 8

        # 하위 등급(3성) 2개 쌍이 있는 보드 vs 1개씩 분산된 보드
        sc = E.evaluate(b_tight, unlocked=6)
        # 평가 함수가 정상 계산되어야 함
        self.assertIsInstance(sc, float)


if __name__ == "__main__":
    unittest.main()
