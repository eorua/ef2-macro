# -*- coding: utf-8 -*-
"""patch246: 유물 공방 '3수째 조각 전부 가중평균'(EXACT) 비교. 지금 설정 vs 3수+EXACT, 같은 판 200판.
2% 이상 오래 버티면 hexa_cfg.json 에 c_exact=1 (c_depth 3) 적용. 깊이 비교/벌점 비교가 돌고 있으면 끝날 때까지 기다림.
사용: py bench_exact.py [판수]   (bench_exact.bat 이 실행)"""
import os, sys, json, subprocess, time, re, shutil

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(MAC, "hexa_search_v3.exe")
W = os.path.join(MAC, "hexa_nt_w.bin")
CFG = os.path.join(MAC, "hexa_cfg.json")
OUT = os.path.join(TR, "bench_exact_result.txt")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 200
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2466"


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def last_line(fn):
    try:
        return open(os.path.join(TR, fn), encoding="utf-8").read().strip().splitlines()[-1]
    except Exception:
        return ""


def busy():
    """다른 비교가 CPU 를 쓰는 중인지 (깊이 비교 / 벌점 비교)"""
    d = last_line("bench_result.txt")
    if d and not any(k in d for k in ("적용:", "그대로 둠", "오류", "비교 실패", "없음")):
        try:
            if time.time() - os.path.getmtime(os.path.join(TR, "bench_result.txt")) < 4 * 3600:
                return "깊이 비교(bench_depth)"
        except OSError:
            pass
    x = last_line("bench_dead_result.txt")
    if x and ("비교 시작" in x or "  벌점 " in x):
        try:
            if time.time() - os.path.getmtime(os.path.join(TR, "bench_dead_result.txt")) < 2 * 3600:
                return "벌점 비교(bench_dead)"
        except OSError:
            pass
    return None


def run(name, D, B, K, env_add):
    env = dict(os.environ, RMODE="1", **env_add)
    t0 = time.time()
    r = subprocess.run([EXE, W, "sim", str(GAMES), str(D), str(B), str(K), str(TH), SEED], capture_output=True,
                       text=True, env=env, creationflags=0x00004000 if os.name == "nt" else 0)
    line = (r.stdout or "").strip() or (r.stderr or "").strip()
    m = re.search(r"moves ([\d.]+)", line)
    ms = re.search(r"([\d.]+) ms/move", line)
    say("  %s: %s  (%.0f분)" % (name, line, (time.time() - t0) / 60))
    return (float(m.group(1)) if m else None), (float(ms.group(1)) if ms else None)


def main():
    w = busy()
    if w:
        say("%s 가 아직 도는 중 -> 끝날 때까지 기다림 (2분마다 확인, 이 창은 최소화해 두세요)" % w)
        while busy():
            time.sleep(120)
    for f in (EXE, W):
        if not os.path.exists(f):
            say("파일 없음:", f)
            return
    cfg = json.load(open(CFG, encoding="utf-8")) if os.path.exists(CFG) else {}
    D, B, K = int(cfg.get("c_depth", 3)), int(cfg.get("c_B", 8)), int(cfg.get("c_K", 8))
    base_env = {"CRN": str(int(cfg.get("c_crn", 0))), "K2": str(int(cfg.get("c_K2", 0))), "B2": str(int(cfg.get("c_B2", 0))),
                "EXACT": "0"}
    if cfg.get("c_deadp"):
        base_env.update(DEADP=str(float(cfg["c_deadp"])), DEADG=str(int(cfg.get("c_deadg", 3))))
    ex_env = dict(base_env, CRN="0", K2="0", B2="0", EXACT="1")
    say("비교 시작: 지금(D%d B%d K%d) vs 3수+조각 전부, %d판, 스레드 %d" % (D, B, K, GAMES, TH))
    base, _ = run("지금", D, B, K, base_env)
    ex, ms = run("3수+조각 전부", 3, B, K, ex_env)
    if base is None or ex is None:
        say("비교 실패 - 바꾸지 않음")
        return
    est = (ms or 0) / 12 / 1000.0          # 실전 12스레드 기준 한 수 계산(초) 추정
    if ex < base * 1.02:
        say("지금보다 2%% 이상 낫지 않아 그대로 둠 (지금 %.1f수, 조각 전부 %.1f수, %+.1f%%)" % (base, ex, (ex / base - 1) * 100))
        return
    if est > 15:
        say("조각 전부가 낫지만 실전 한 수 계산이 약 %.1f초로 너무 느려 그대로 둠" % est)
        return
    cfg = json.load(open(CFG, encoding="utf-8")) if os.path.exists(CFG) else {}
    if os.path.exists(CFG):
        shutil.copyfile(CFG, CFG + ".bak246")
    cfg.update({"c_exact": 1, "c_depth": 3})
    json.dump(cfg, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("적용: 3수+조각 전부  평균 %.1f -> %.1f수 (%+.1f%%), 실전 한 수 계산 약 %.2f초. 예전 설정 hexa_cfg.json.bak246. 다음 공방 판부터" %
        (base, ex, (ex / base - 1) * 100, est))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
