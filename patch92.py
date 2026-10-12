# patch92.py - 웨이브 숫자 오독(5 를 6 으로 읽어 5400 대에서 '고레벨 단계'가 시작되던 문제) 방어
#   * 직전에 믿은 값보다 갑자기 너무 크게 오른 값은 오독으로 보고 버림 (낮아지는 값은 환생/보정이니 그대로 받음)
#   * 하루 한 번 쓰는 일이 아니라 메인 루프의 웨이브 판단(hist)과 정체 감시에 모두 적용
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")

FUNC = '''_wv = {"v": None, "t": 0.0}


def wave_sane(w):
    """연속성 검사: 직전에 믿은 웨이브보다 갑자기 너무 크게 오른 값(예: 5400 -> 6400)은 숫자 오독으로 보고 None.
    낮아지는 값은 환생이나 앞선 오독 정정이라 그대로 받음. 15분 넘게 지나면 기준을 새로 잡음"""
    if w is None:
        return None
    now = time.time()
    v, t = _wv["v"], _wv["t"]
    if v is not None and 0 <= now - t < 900 and w > v + 250 + 6 * (now - t):
        if now - _wv.get("log", 0) > 60:
            _wv["log"] = now
            log("웨이브 %s 는 직전 %s 에서 너무 급하게 올라 오독으로 보고 무시" % (w, v))
        return None
    _wv["v"], _wv["t"] = w, now
    return w


class StuckWatch:
'''
A1 = "class StuckWatch:\n"
A2 = "            if w is not None:\n                hist.append(w)\n"
B2 = "            w = wave_sane(w)\n            if w is not None:\n                hist.append(w)\n"
A3 = "            wx = wave.read_wave(img, exact=True)\n"
B3 = "            wx = wave_sane(wave.read_wave(img, exact=True))\n"


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    s = open(MAIN, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if "def wave_sane" in s:
        print("main.py 는 이미 최신"); return 0
    for a, n in ((A1, 1), (A2, 1), (A3, 1)):
        if s.count(a) != n:
            print("main.py 앵커 불일치 (%d, 기대 %d): %s" % (s.count(a), n, a.strip()[:40])); return 1
    new = s.replace(A1, FUNC).replace(A2, B2).replace(A3, B3)
    compile(new, "main.py", "exec")
    print("main.py 백업:", backup(MAIN))
    open(MAIN, "w", encoding="utf-8", newline="").write(new.replace("\n", "\r\n") if crlf else new)
    print("main.py 패치 완료 (메인 재시작 필요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
