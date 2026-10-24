# -*- coding: utf-8 -*-
"""patch249: 5개 이상 합치기(+2등급) 보너스 비교 (큰 두뇌, PC).
1단계: 보너스 0/0.2/0.5/1/2 x 300판 (조각 전부 끔, 빠른 비교, 약 10분)
2단계: 1단계 최고가 보너스 0보다 2% 이상 나으면, 실전 설정(조각 전부 켬)으로 0 vs 그 값 300판씩 재확인(약 35분)
       → 거기서도 2% 이상 나으면 hexa_cfg.json c_fiveb 적용 (예전 설정 hexa_cfg.json.bak249)
사용: py bench_five.py [판수]   (bench_five.bat 이 실행)"""
import os, sys, json, subprocess, time, re, shutil

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(MAC, "hexa_search_v4.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
CFG = os.path.join(MAC, "hexa_cfg.json")
OUT = os.path.join(TR, "bench_five_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 300
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2499"
BONUS = [0, 0.2, 0.5, 1, 2]


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def run(fb, exact):
    env = dict(os.environ, RMODE="1", CRN="0", K2="0", B2="0", EXACT=str(exact), FIVEB=str(fb))
    for k in ("DEADP", "GATEP", "DUMP"):
        env.pop(k, None)
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(GAMES), "3", "8", "8", str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    lines = (r.stdout or "").strip().splitlines() or [(r.stderr or "").strip()]
    say("  보너스 %s%s (%.0f분)" % (fb, " [조각 전부]" if exact else "", (time.time() - t0) / 60))
    for l in lines:
        if not l.startswith("DEAD"):
            say("     " + l)
    m = re.search(r"moves ([\d.]+)", lines[0])
    return float(m.group(1)) if m else None


def main():
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    say("1단계: 보너스 %s x %d판, 3수 B8 K8 (조각 전부 끔), 스레드 %d, seed %s" % (BONUS, GAMES, TH, SEED))
    res = [(b, run(b, 0)) for b in BONUS]
    base = res[0][1]
    if base is None:
        say("비교 실패 - 바꾸지 않음")
        return
    best = max((r for r in res if r[1] is not None), key=lambda r: r[1])
    if best[0] == 0 or best[1] < base * 1.02:
        say("보너스 없는 지금보다 2%% 이상 나은 게 없어 그대로 둠 (지금 평균 %.1f수)" % base)
        return
    say("2단계: 실전 설정(조각 전부)으로 보너스 0 vs %s 재확인" % best[0])
    a = run(0, 1)
    b = run(best[0], 1)
    if a is None or b is None or b < a * 1.02:
        say("재확인에서 2%% 이상 낫지 않아 그대로 둠 (%.1f -> %.1f)" % (a or 0, b or 0))
        return
    cfg = json.load(open(CFG, encoding="utf-8")) if os.path.exists(CFG) else {}
    if os.path.exists(CFG):
        shutil.copyfile(CFG, CFG + ".bak249")
    cfg["c_fiveb"] = best[0]
    json.dump(cfg, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("적용: 보너스 %s  평균 %.1f -> %.1f수 (%+.1f%%). 예전 설정 hexa_cfg.json.bak249. 다음 공방 판부터" %
        (best[0], a, b, (b / a - 1) * 100))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
