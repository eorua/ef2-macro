# -*- coding: utf-8 -*-
"""patch250: ★10 만들기 보너스 비교 (큰 두뇌, PC). 판 길이를 얼마나 내주고 ★10 을 얼마나 더 만드는지 + ★10 경로(8성 5개 / 9성 3개).
보너스 0/10/30/100/300 x 300판 (조각 전부 끔, 빠른 비교, 약 10~15분). 자동 적용 없음 - 결과 보고 사용자가 정함.
bench_five 가 돌고 있으면 끝날 때까지 기다림.
사용: py bench_ten.py [판수]   (bench_ten.bat 이 실행)"""
import os, sys, subprocess, time

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(MAC, "hexa_search_v5.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
OUT = os.path.join(TR, "bench_ten_result.txt")
FIVE_OUT = os.path.join(TR, "bench_five_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 300
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2510"
BONUS = [0, 10, 30, 100, 300]


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def five_busy():
    try:
        last = open(FIVE_OUT, encoding="utf-8").read().strip().splitlines()[-1]
    except Exception:
        return False
    if any(k in last for k in ("적용:", "그대로 둠", "오류", "실패", "없음")):
        return False
    return time.time() - os.path.getmtime(FIVE_OUT) < 3 * 3600


def run(tb):
    env = dict(os.environ, RMODE="1", CRN="0", K2="0", B2="0", EXACT="0", TENB=str(tb))
    for k in ("DEADP", "GATEP", "DUMP", "FIVEB"):
        env.pop(k, None)
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(GAMES), "3", "8", "8", str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    lines = (r.stdout or "").strip().splitlines() or [(r.stderr or "").strip()]
    say("  ★10 보너스 %s (%.0f분)" % (tb, (time.time() - t0) / 60))
    for l in lines:
        if l.startswith("SIM") or l.startswith("TEN"):
            say("     " + l)


def main():
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    if five_busy():
        say("bench_five 가 도는 중 -> 끝날 때까지 기다림 (2분마다 확인, 이 창은 최소화해 두세요)")
        while five_busy():
            time.sleep(120)
    say("비교 시작: ★10 보너스 %s x %d판, 3수 B8 K8 (조각 전부 끔), 스레드 %d, seed %s" % (BONUS, GAMES, TH, SEED))
    for tb in BONUS:
        run(tb)
    say("끝 (설정 변경 없음 - 결과 보고 정하기)")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
