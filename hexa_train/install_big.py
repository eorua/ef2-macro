# -*- coding: utf-8 -*-
"""patch233: PC 에서 학습한 큰 두뇌(big.bin)를 지금 두뇌와 가상 대전으로 비교해 더 좋으면 설치.
사용: py install_big.py [판수]   (train_big.bat 이 마지막에 자동 실행)"""
import os, sys, json, shutil, subprocess, time, re

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
EXE = os.path.join(MAC, "hexa_search.exe")
NEW = os.path.join(TR, "big.bin")
CUR = os.path.join(MAC, "hexa_nt_w.bin")
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 300
TH = str(max(2, (os.cpu_count() or 4) - 2))
OUT = os.path.join(TR, "result.txt")


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def sim(w, rmode):
    env = dict(os.environ, RMODE=str(rmode))
    r = subprocess.run([EXE, w, "sim", str(GAMES), "3", "8", "8", TH, "777"], capture_output=True, text=True, env=env,
                       creationflags=0x00004000 if os.name == "nt" else 0)
    line = (r.stdout or "").strip()
    say("  ", os.path.basename(w), line or r.stderr)
    m = re.search(r"moves ([\d.]+)", line)
    return float(m.group(1)) if m else None


def main():
    if not os.path.exists(NEW):
        say("big.bin 없음 - 학습이 끝나지 않음")
        return
    # 지금 두뇌: bin 이 없으면(아직 한 번도 공방을 안 돌림) npz 에서 만들기
    sys.path.insert(0, MAC)
    import hexa_nt as T
    T._ensure_bin()
    cur_meta = json.load(open(os.path.join(MAC, "hexa_nt_w.json"), encoding="utf-8"))
    cur_rm = 1 if (cur_meta.get("reward") or {}).get("mode") == "survive" else 0
    say("비교 시작: %d판, 3수, 스레드 %s" % (GAMES, TH))
    a = sim(CUR, cur_rm)
    b = sim(NEW, 1)
    if a is None or b is None:
        say("비교 실패 - 설치 안 함")
        return
    say("지금 두뇌 평균 %.1f수 / 새 두뇌 평균 %.1f수 (%+.1f%%)" % (a, b, (b / a - 1) * 100))
    if b < a * 1.02:
        say("새 두뇌가 2%% 이상 낫지 않아 설치 안 함 (big.bin 은 hexa_train 에 남김)")
        return
    tup = open(NEW + ".tup").read().split()
    n = int(tup[0]); p = 1; base = []
    for _ in range(n):
        L = int(tup[p]); base.append([int(x) for x in tup[p + 1:p + 1 + L]]); p += 1 + L
    sym = json.load(open(os.path.join(TR, "tuples.json")))["sym"]
    meta = {"base": base, "sym": sym, "reward": {"mode": "survive", "bonus": 0.002}}
    for ext in ("", ".tup"):
        if os.path.exists(CUR + ext):
            shutil.copyfile(CUR + ext, CUR + ext + ".bak233")
    js = os.path.join(MAC, "hexa_nt_w.json")
    if os.path.exists(js):
        shutil.copyfile(js, js + ".bak233")
    shutil.copyfile(NEW, CUR + ".new")
    os.replace(CUR + ".new", CUR)
    shutil.copyfile(NEW + ".tup", CUR + ".tup")
    json.dump(meta, open(js, "w", encoding="utf-8"))
    now = time.time()
    os.utime(CUR, (now, now))
    say("설치 완료: hexa_nt_w.bin (튜플 %d개). 예전 것은 .bak233. 다음 공방 판부터 적용" % n)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
