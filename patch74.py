# patch74.py - 양궁: 과녁 속도를 '이번 라운드에서 잰 값'으로 예측 (C:\macro 에서 py patch74.py)
#   * 영상(30fps) 분석 결과: 과녁 속도가 라운드마다 달라서(약 146~323 px/s, 순서대로 빨라지지 않음) '예상 속도'가 섞이면 빗나감
#   * 수정 1: 속도 추정에서 라운드 시작 때 잰 값(2번 이상 읽었을 때)을 그대로 씀 (예전엔 예상값을 30~60% 섞었음)
#   * 수정 2: 과녁을 한 번만 읽은 상태에서는 쏘지 않고, 두 번째 읽기를 기다림
#   * 한계: 아주 빠른 라운드(약 300px/s 이상)는 화면 캡처 한 번에 0.3~0.5초가 걸려서 여전히 늦을 수 있음
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ARCH = os.path.join(HERE, "arch.py")
O1 = "                w = 1.0 if (n >= 4 and span >= 0.4) else (0.7 if span >= 0.25 else 0.4)\n"
N1 = "                w = 1.0 if span >= 0.15 else 0.4\n"
O2 = "            v = est_speed(samples, prior)\n            tl, xl = samples[-1]\n"
N2 = "            if len(samples) < 2:\n                continue\n            v = est_speed(samples, prior)\n            tl, xl = samples[-1]\n"


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    s = open(ARCH, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if "span >= 0.15 else 0.4" in s:
        print("arch.py 는 이미 최신"); return 0
    if s.count(O1) != 1 or s.count(O2) != 1:
        print("arch.py 앵커 불일치", s.count(O1), s.count(O2), "-> arch.py 를 올려 주세요"); return 1
    print("arch.py 백업:", backup(ARCH))
    s = s.replace(O1, N1, 1).replace(O2, N2, 1)
    open(ARCH, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("arch.py 패치 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
