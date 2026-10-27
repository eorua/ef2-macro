# -*- coding: utf-8 -*-
"""patch295: cp949 파이프에서도 hexa.log 가 예외를 내지 않는지 (➜ 🎯 등)"""
import io, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hexa


class T(unittest.TestCase):
    def test_log_cp949(self):
        old_p, old_o = hexa.LOG_PATH, sys.stdout
        hexa.LOG_PATH = os.path.join(tempfile.mkdtemp(), "l.txt")
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp949", errors="strict")
        try:
            hexa.log("둘 곳 없음 ➜ 망치 🎯 ★10")
        finally:
            sys.stdout = old_o
        txt = open(hexa.LOG_PATH, encoding="utf-8").read()
        hexa.LOG_PATH = old_p
        self.assertIn("➜", txt)


if __name__ == "__main__":
    unittest.main()
