# -*- coding: utf-8 -*-
"""patch299b: 10/26 신규 룰(점 확정 + 망치 1회) 완벽 반영 search12.exe 기반 HUB x TENB 최신 벤치마크.
  A: HUB 60 TENB 100 (지금 실전 기준)
  B: HUB 40 TENB 50   C: HUB 50 TENB 100   D: HUB 60 TENB 50
  E: HUB 70 TENB 100  F: HUB 80 TENB 100   G: HUB 60 TENB 150
  동일 조각 순서(Seed 2510), 판당 망치 1회, 점 확정 합성.
사용: py bench_v12.py [판수]
"""
import os, re, sys, json, shutil, subprocess, time

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(TR, "search12.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
OUT = os.path.join(TR, "bench_v12_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 600
# patch299d: 크롬 및 PC 사용에 영향이 전혀 없도록 스레드 수를 4개로 제한하고, IDLE(최하) 우선순위로 강제 지정
TH = 4
SEED = "2510"
ARMS = [("A", dict(HUB=60, TENB=100)), ("B", dict(HUB=40, TENB=50)), ("C", dict(HUB=50, TENB=100)),
        ("D", dict(HUB=60, TENB=50)), ("E", dict(HUB=70, TENB=100)), ("F", dict(HUB=80, TENB=100)),
        ("G", dict(HUB=60, TENB=150))]
CFG = os.path.join(MAC, "hexa_cfg.json")


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
    # 0x00000040 = IDLE_PRIORITY_CLASS (윈도우 최하위 우선순위: 다른 프로그램이 CPU를 쓰면 100% 양보)
    idle_flag = 0x00000040 if os.name == "nt" else 0
    r = subprocess.run([EXE, W, "sim", str(GAMES), "3", "8", "8", str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=idle_flag)
    lines = (r.stdout or "").strip().splitlines() or [(r.stderr or "").strip()]
    desc = " ".join("%s %s" % kv for kv in extra.items()) or "기준"
    say("  %s: %s (%.1f분)" % (name, desc, (time.time() - t0) / 60))
    ten = mv = hm = None
    for l in lines:
        if l.startswith("SIM") or l.startswith("TEN") or l.startswith("HAMMER"):
            say("     " + l)
        m = re.search(r"games with star10 ([\d.]+)%", l)
        if m: ten = float(m.group(1))
        m = re.search(r"moves ([\d.]+)", l)
        if m and l.startswith("SIM"): mv = float(m.group(1))
        m = re.search(r"HAMMER used (\d+)/([\d.]+)%", l)
        if m: hm = float(m.group(2))
    return ten, mv, hm


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00000040)
        except Exception:
            pass
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    if os.path.exists(OUT):
        try: os.remove(OUT)
        except Exception: pass
    err = 100 * 2 * (0.22 * 0.78 / GAMES) ** 0.5
    say("=== [10/26 신규 룰 완전 반영] 최신 벤치마크 시작: %d판씩, 3수 B8 K8, 스레드 %d, seed %s ===" % (GAMES, TH, SEED))
    res = {}
    for name, extra in ARMS:
        res[name] = run(name, extra)
    a10, amv, ahm = res["A"]
    say("요약 (A 대비, ★10 오차 약 ±%.1f%%p):" % err)
    best = None
    for name, (t, m, h) in res.items():
        if t is None or m is None or a10 is None:
            say("  %s: 결과 읽기 실패" % name); continue
        d10, dmv = t - a10, (m - amv) / amv * 100
        ok = name != "A" and d10 > err
        say("  %s: ★10 %.1f%% (%+.1f%%p)  판 길이 %.1f수 (%+.1f%%)  망치 %.1f%%%s" % (name, t, d10, m, dmv, h or 0.0, "  <- 합격" if ok else ""))
        if ok and (best is None or t > res[best][0]): best = name
    if not best:
        say("결론: 합격 없음 - 지금 설정 유지 (HUB 60 TENB 100)")
        return
    ex = dict(ARMS)[best]
    try:
        shutil.copy2(CFG, CFG + ".bak299b")
        cfg = json.load(open(CFG, encoding="utf-8"))
        cfg["c_hub"] = float(ex["HUB"]); cfg["c_tenb"] = float(ex["TENB"])
        json.dump(cfg, open(CFG, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        say("결론: %s 승리 적용 -> hexa_cfg.json c_hub %s, c_tenb %s (백업 hexa_cfg.json.bak299b)" % (best, ex["HUB"], ex["TENB"]))
    except Exception as e:
        say("적용 실패:", repr(e))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
