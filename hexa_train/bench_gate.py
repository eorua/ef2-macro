# -*- coding: utf-8 -*-
"""patch248: '단계 넘어가기 전에 곧 죽을 등급(1~3성) 지우기' 측정·비교 (큰 두뇌, PC).
- 단계(★5/★6/★7 첫 생성)마다 새로 죽은 칸 수, 죽은 칸 수별 판 길이
- GATEP(진짜 죽은 칸 벌점) 0 / 3 / 1000(사실상 금지) 비교. 자동 적용 없음(결과만 기록).
사용: py bench_gate.py [판수]   (bench_gate.bat 이 실행)"""
import os, sys, subprocess, time, re, collections

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(TR, "search6.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
OUT = os.path.join(TR, "bench_gate_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 300
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2488"


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def run(gp):
    env = dict(os.environ, RMODE="1", CRN="0", K2="0", B2="0", EXACT="0", GATEP=str(gp), DUMP="1")
    env.pop("DEADP", None)
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(GAMES), "3", "8", "8", str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    lines = (r.stdout or "").strip().splitlines()
    say("  벌점 %s (%.0f분)" % (gp, (time.time() - t0) / 60))
    for l in lines:
        say("     " + l)
    d = collections.defaultdict(list)
    for l in (r.stderr or "").splitlines():
        p = l.split()
        if len(p) == 3 and p[0] == "G":
            d[min(int(p[2]), 4)].append(int(p[1]))
    if d:
        say("     죽은 칸 수별 판 길이: " + ", ".join(
            "%s칸 %d판 %.1f수" % ("4+" if k == 4 else k, len(v), sum(v) / len(v)) for k, v in sorted(d.items())))


def main():
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    say("비교 시작: %d판, 3수 B8 K8 (조각 전부 끔, 빠른 비교), 스레드 %d, seed %s" % (GAMES, TH, SEED))
    for gp in (0, 3, 1000):
        run(gp)
    say("끝 (설정 변경 없음)")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
