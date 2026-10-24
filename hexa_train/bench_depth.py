# -*- coding: utf-8 -*-
"""patch242: 유물 공방 수 읽기 깊이 비교 (3수 / 4수 / 5수). PC 에서 가상 대전 후 가장 오래 버티는 설정을 hexa_cfg.json 에 적용.
사용: py bench_depth.py [판수]   (bench_depth.bat 이 실행)"""
import os, sys, json, subprocess, time, re, shutil

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(MAC, "hexa_search.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
CFG = os.path.join(MAC, "hexa_cfg.json")
OUT = os.path.join(TR, "bench_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 100
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "4242"

# 이름, D, B, K, CRN, K2, B2
CONFIGS = [
    ("지금(3수)", 3, 8, 8, 0, 0, 0),
    ("3수+같은조각", 3, 8, 8, 1, 0, 0),
    ("4수+같은조각", 4, 8, 8, 1, 0, 0),
    ("5수+같은조각(깊은곳 좁게)", 5, 6, 6, 1, 3, 3),
    ("5수+같은조각(넓게)", 5, 8, 8, 1, 4, 4),
]
REAL_TH = 12          # 실전 수 읽기 스레드 (4수 이상일 때)
LIMIT_MS = 15000      # 실전 한 수 계산 상한 (사용자: 시간 여유 있음)


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def run(c):
    name, D, B, K, crn, k2, b2 = c
    env = dict(os.environ, RMODE="1", CRN=str(crn), K2=str(k2), B2=str(b2))
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(GAMES), str(D), str(B), str(K), str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    line = (r.stdout or "").strip() or (r.stderr or "").strip()
    m = re.search(r"moves ([\d.]+)", line)
    ms = re.search(r"([\d.]+) ms/move", line)
    say("  %s: %s  (%.0f분)" % (name, line, (time.time() - t0) / 60))
    return (float(m.group(1)) if m else None), (float(ms.group(1)) if ms else None)


def main():
    if not os.path.exists(W):
        say("hexa_nt_w.bin 없음 - 공방을 한 판 돌린 뒤 다시 실행")
        return
    say("비교 시작: 설정 %d개 x %d판, 스레드 %d" % (len(CONFIGS), GAMES, TH))
    res = []
    for c in CONFIGS:
        mv, ms = run(c)
        res.append((c, mv, ms))
    base = res[0][1]
    if base is None:
        say("비교 실패 - 바꾸지 않음")
        return
    best = res[0]
    for c, mv, ms in res[1:]:
        if mv is None or ms is None:
            continue
        real_ms = ms / REAL_TH  # 실전 12스레드 기준 한 수 계산 시간(대략)
        say("  %s: 실전 한 수 계산 약 %.1f초 예상" % (c[0], real_ms / 1000))
        if real_ms > LIMIT_MS:
            say("  %s: 실전 한 수 약 %.1f초 예상 -> 너무 느려 제외" % (c[0], real_ms / 1000))
            continue
        if mv > best[1]:
            best = (c, mv, ms)
    if best is res[0] or best[1] < base * 1.02:
        say("지금 설정보다 2%% 이상 나은 게 없어 그대로 둠 (지금 평균 %.1f수)" % base)
        return
    name, D, B, K, crn, k2, b2 = best[0]
    cfg = json.load(open(CFG, encoding="utf-8")) if os.path.exists(CFG) else {}
    shutil.copyfile(CFG, CFG + ".bak242") if os.path.exists(CFG) else None
    cfg.update({"c_depth": D, "c_B": B, "c_K": K, "c_crn": crn, "c_K2": k2, "c_B2": b2})
    if D >= 4:
        cfg["c_threads"] = max(6, min(REAL_TH, TH))
        cfg["think_sec"] = max(cfg.get("think_sec", 10.0), 25.0)  # C 상한 = think_sec x 0.8 초
    json.dump(cfg, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("적용: %s  평균 %.1f -> %.1f수 (%+.1f%%). 예전 설정은 hexa_cfg.json.bak242. 다음 공방 판부터" %
        (name, base, best[1], (best[1] / base - 1) * 100))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
