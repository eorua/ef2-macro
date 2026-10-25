# -*- coding: utf-8 -*-
"""사전 포석(CLUST: 8성 1~2개 결합 / HUB7: 7성 허브 밑그림) 벤치마크 실험.
현재 실전 설정(HUB 60, TENB 100) 대비 10성 확률 및 생존률 비교.
실전 설정(hexa_cfg.json)을 건드리지 않고 결과만 기록합니다.
사용: py bench_prehub.py [판수] (기본 600판)
"""
import os, re, sys, subprocess, time

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(TR, "search11.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
OUT = os.path.join(TR, "bench_prehub_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 600
TH = min(12, max(2, (os.cpu_count() or 4) - 4))   # PC/에뮬 여유를 위해 4코어 제외
SEED = "3107"

ARMS = [
    ("A (기준)", dict(HUB=60, TENB=100, CLUST=0, HUB7=0)),
    ("B (CLUST 0.5)", dict(HUB=60, TENB=100, CLUST=0.5, HUB7=0)),
    ("C (CLUST 1.0)", dict(HUB=60, TENB=100, CLUST=1.0, HUB7=0)),
    ("D (HUB7 30)", dict(HUB=60, TENB=100, CLUST=0, HUB7=30)),
    ("E (CLUST+HUB7)", dict(HUB=60, TENB=100, CLUST=0.5, HUB7=20)),
]

def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")

def run(name, extra):
    env = dict(os.environ, RMODE="1", CRN="0", K2="0", B2="0", EXACT="0", TENB="10", CLUST="0", HUB="0", HUB7="0")
    for k in ("DEADP", "GATEP", "DUMP", "FIVEB", "CALIB"):
        env.pop(k, None)
    for k, v in extra.items():
        env[k] = str(v)
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(GAMES), "3", "8", "8", str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    lines = (r.stdout or "").strip().splitlines() or [(r.stderr or "").strip()]
    desc = " ".join("%s %s" % kv for kv in extra.items())
    say("  %s: %s (%.1f분)" % (name, desc, (time.time() - t0) / 60))
    ten = mv = sc = best = None
    for l in lines:
        if l.startswith("SIM") or l.startswith("TEN"):
            say("     " + l)
        m = re.search(r"games with star10 ([\d.]+)%", l)
        if m: ten = float(m.group(1))
        m = re.search(r"moves ([\d.]+)", l)
        if m and l.startswith("SIM"): mv = float(m.group(1))
        m = re.search(r"score (\d+)", l)
        if m: sc = int(m.group(1))
        m = re.search(r"best: (.+)", l)
        if m: best = m.group(1).strip()
    return dict(ten=ten, mv=mv, sc=sc, best=best)

def main():
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    say("=" * 60)
    say("사전 포석(CLUST / HUB7) 벤치마크 시작: %d판씩, 3수 B8 K8, 스레드 %d, seed %s" % (GAMES, TH, SEED))
    res = {}
    for name, extra in ARMS:
        res[name] = run(name, extra)

    say("-" * 60)
    say("요약 (A 기준 대비):")
    a_ten = res["A (기준)"]["ten"] or 1.0
    a_mv = res["A (기준)"]["mv"] or 1.0
    for name, _ in ARMS:
        r = res[name]
        d_ten = (r["ten"] - a_ten) if r["ten"] is not None else 0
        p_mv = (r["mv"] - a_mv) / a_mv * 100 if r["mv"] is not None else 0
        say("  %-16s: ★10 %5.1f%% (%+4.1f%%p) | 판길이 %5.1f수 (%+5.1f%%) | 점수 %s | %s" %
            (name, r["ten"] or 0, d_ten, r["mv"] or 0, p_mv, r["sc"] or 0, r["best"] or ""))
    say("=" * 60)

if __name__ == "__main__":
    main()
