# -*- coding: utf-8 -*-
"""patch251 (다단계 두뇌 0단계 진단): 큰 두뇌 평가값 V 가 u(해금 최고등급)별로 얼마나 맞는지 측정.
 1) D1(1수 탐욕 = 학습 때 정책) 2000판: 정책 차이 없이 '표 자체의 오차'
 2) D3 B8 K8 EXACT=1(실전 설정) 300판: 실제 봇 판에서의 오차
 search9.exe(신규) 만 사용, 실전 파일·설정 변경 없음.  사용: py bench_calib.py [실전판수]"""
import os, sys, subprocess, time

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(TR, "search9c.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
OUT = os.path.join(TR, "bench_calib_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 300
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2600"


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def run(label, n, d, exact):
    env = dict(os.environ, RMODE="1", CRN="0", K2="0", B2="0", EXACT=str(exact), CALIB="1")
    for k in ("DEADP", "GATEP", "DUMP", "FIVEB", "TENB"):
        env.pop(k, None)
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(n), str(d), "8", "8", str(TH), SEED], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env,
                       creationflags=0x00004000 if os.name == "nt" else 0)
    say("== %s (%d판, %.1f분)" % (label, n, (time.time() - t0) / 60))
    lines = (r.stdout or "").strip().splitlines() or [(r.stderr or "").strip()]
    for l in lines:
        if l.startswith(("CALIB", "SIM", "TEN")):
            say("   " + l)


def main():
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    say("진단 시작: 스레드 %d, seed %s" % (TH, SEED))
    run("1) D1 1수 탐욕(학습 정책)", 2000, 1, 0)
    run("2) D3 B8 K8 EXACT=1(실전 설정)", GAMES, 3, 1)
    say("끝 (설정 변경 없음)")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
