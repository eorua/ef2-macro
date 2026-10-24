# -*- coding: utf-8 -*-
"""patch244: 유물 공방 '낮은 등급(1~3성) 칸 벌점' 비교. PC 에서 가상 대전 후 가장 오래 버티는 벌점을 hexa_cfg.json 에 적용.
사용: py bench_dead.py [판수]   (bench_dead.bat 이 실행)"""
import os, sys, json, subprocess, time, re, shutil

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(MAC, "hexa_search_v3.exe")          # patch247: v3(= v2 + c_exact) 가 있으면 그것
if not os.path.exists(EXE):
    EXE = os.path.join(MAC, "hexa_search_v2.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
CFG = os.path.join(MAC, "hexa_cfg.json")
OUT = os.path.join(TR, "bench_dead_result.txt")
DEPTH_OUT = os.path.join(TR, "bench_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 300
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2444"
PENALTIES = [0, 1, 3, 6, 12]   # 1~3성 칸 하나당 벌점 (평가 단위 = 대략 '남은 수')


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def depth_bench_done():
    try:
        last = open(DEPTH_OUT, encoding="utf-8").read().strip().splitlines()[-1]
    except Exception:
        return True
    return any(k in last for k in ("적용:", "그대로 둠", "오류", "비교 실패", "없음"))


def run(p, crn, exact=0):
    env = dict(os.environ, RMODE="1", CRN=str(crn), K2="0", B2="0", DEADP=str(p), DEADG="3", EXACT=str(exact))
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(GAMES), "3", "8", "8", str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    line = (r.stdout or "").strip() or (r.stderr or "").strip()
    m = re.search(r"moves ([\d.]+)", line)
    say("  벌점 %s: %s  (%.0f분)" % (p, line, (time.time() - t0) / 60))
    return float(m.group(1)) if m else None


def main():
    if not depth_bench_done():   # patch247: 끝내지 않고 기다림
        say("깊이 비교(bench_depth)가 아직 도는 중 -> 끝날 때까지 기다림 (2분마다 확인)")
        while not depth_bench_done():
            time.sleep(120)
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    cfg = json.load(open(CFG, encoding="utf-8")) if os.path.exists(CFG) else {}
    exact = 1 if cfg.get("c_exact") else 0      # patch247: bench_exact 결과(조각 전부)가 적용됐으면 그 상태로 비교
    crn = 0 if exact else int(cfg.get("c_crn", 0))
    say("비교 시작: 벌점 %s x %d판, 3수 B8 K8 CRN %d EXACT %d, 스레드 %d" % (PENALTIES, GAMES, crn, exact, TH))
    res = [(p, run(p, crn, exact)) for p in PENALTIES]
    base = res[0][1]
    if base is None:
        say("비교 실패 - 바꾸지 않음")
        return
    best = max((r for r in res if r[1] is not None), key=lambda r: r[1])
    if best[0] == 0 or best[1] < base * 1.02:
        say("벌점 없는 지금보다 2%% 이상 나은 게 없어 그대로 둠 (지금 평균 %.1f수)" % base)
        return
    cfg = json.load(open(CFG, encoding="utf-8")) if os.path.exists(CFG) else {}
    if os.path.exists(CFG):
        shutil.copyfile(CFG, CFG + ".bak244")
    cfg.update({"c_deadp": best[0], "c_deadg": 3})
    json.dump(cfg, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("적용: 벌점 %s  평균 %.1f -> %.1f수 (%+.1f%%). 예전 설정은 hexa_cfg.json.bak244. 다음 공방 판부터" %
        (best[0], base, best[1], (best[1] / base - 1) * 100))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
