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

    def test_low_tier_prefers_3merge_over_2pair(self):
        """1~7성 하위 등급에서는 2+2 쌍을 모으는 것보다 3합으로 터뜨려 빈칸을 확보하는 것이 더 유리함을 검증"""
        # 보드 1: 4성 2개 덩어리가 남아 있어 빈칸이 8개인 보드
        b_pair = [0] * 23
        b_pair[8] = 4
        b_pair[9] = 4
        for i in range(10, 23):
            b_pair[i] = 5

        # 보드 2: 4성 2개가 3합으로 터져 5성이 되고 빈칸이 9개로 늘어난 보드
        b_merged = [0] * 23
        b_merged[9] = 5
        for i in range(10, 23):
            b_merged[i] = 5

        sc_pair = E.evaluate(b_pair, unlocked=8)
        sc_merged = E.evaluate(b_merged, unlocked=8)

        # 3합으로 공간을 확보한 보드가 더 높은 평가를 받아야 함
        self.assertGreater(sc_merged, sc_pair)


if __name__ == "__main__":
    unittest.main()
