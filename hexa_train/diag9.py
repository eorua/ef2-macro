# -*- coding: utf-8 -*-
"""patch251: 0단계 진단 - 두뇌 평가값 보정도(u 별). 설정 변경 없음, 결과만 기록.
- 3수 봇(실전 설정 D3 B8 K8 EXACT=1)과 1수 봇(학습 때 쓰는 정책) 각각 sim 하며
  매 수 뒤 평가값 V 와 실제로 그 뒤 받은 보상 합 G 를 u(최고 등급)별로 비교.
사용: py diag9.py [판수]   (diag9.bat 이 실행)"""
import os, sys, subprocess, time

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(TR, "search9.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
OUT = os.path.join(TR, "diag9_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 300
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2520"


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def run(name, D, exact, games):
    env = dict(os.environ, RMODE="1", CRN="0", K2="0", B2="0", EXACT=str(exact), CALIB="1")
    for k in ("DEADP", "GATEP", "FIVEB", "TENB"):
        env.pop(k, None)
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(games), str(D), "8", "8", str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    say("  %s (%.0f분)" % (name, (time.time() - t0) / 60))
    for l in (r.stdout or "").strip().splitlines():
        say("     " + l)
    if r.stderr.strip():
        say("     stderr: " + r.stderr.strip()[:300])


def main():
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    say("진단 시작: %d판, 스레드 %d, seed %s (CALIB: bias=평균(V-G), se=판 단위 표준오차, rel=RMSE/G표준편차)" % (GAMES, TH, SEED))
    run("1수 봇 (학습 정책)", 1, 0, GAMES)
    run("3수 봇 (실전 D3 B8 K8 EXACT=1)", 3, 1, GAMES)
    say("끝 (설정 변경 없음)")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
