# -*- coding: utf-8 -*-
"""patch253/259 (계획 B: 탐색 정책 + ★10 확정 달성 올인 보상 체계로 학습) 1~5단계 자동 실행.
실전 파일(hexa_nt_w.bin, hexa_cfg.json)은 바꾸지 않음.
 1) 회귀: nt3(POL=0, TENB=0, CLUST=0) 와 nt2 의 eval 결과가 같은지
 2) 배율 측정: search9c CALIB=1, D2 300판 -> 전체 meanG/meanV = SCALE  (이 판의 SIM/TEN 이 '현재 두뇌 D2' 기준값)
 3) 대조군: 배율만 곱한 두뇌(학습 0) D2 300판 -> 3% 넘게 나빠지면 시범 학습은 SCALE=1
 4) 시범 학습 (각 50만 판, alpha 0.003, 현재 두뇌에서 이어서, ★10 올인 보상 TENB=180 / STAR9B=15 / STAR8B=3 / CLUST=1.0)
      ctl  : POL=0 (1수 학습 + ★10 보상, 대조군)
      all  : POL=2 PU=3 (처음부터 2수 + ★10 보상·결합 가중치)
      late : POL=2 PU=7 (u>=7 부터 2수 + ★10 보상·결합 가중치)
 5) 선별: 셋 다 D2 300판(같은 seed, TENB=180 CLUST=1.0) -> ★10 달성률(star10%) 및 평균 수 비교, ★10 달성률 최우선 선별
 결과: train_b_result.txt, 학습 출력: train_b.log, 두뇌: b_ctl.bin / b_all.bin / b_late.bin / b_scale.bin
 중간에 창을 닫아도 다시 실행하면 끝난 단계(.done)는 건너뜀.
 사용: py train_b.py [시범 판수=500000]   (train_b.bat 이 실행)"""
import os, re, sys, shutil, subprocess, time

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
W0 = os.path.join(MAC, "hexa_nt_w.bin")
NT3 = os.path.join(TR, "nt3.exe")
NT2C = os.path.join(TR, "nt2chk.exe")     # nt2.c 를 nt3 와 같은 옵션으로 빌드 (회귀 비교용)
NT2 = os.path.join(TR, "nt2.exe")         # 예전 빌드 (참고 비교만)
SRCH = os.path.join(TR, "search9c.exe")
if not os.path.exists(SRCH):
    SRCH = os.path.join(TR, "search9.exe")
OUT = os.path.join(TR, "train_b_result.txt")
LOG = os.path.join(TR, "train_b.log")
GAMES = int(sys.argv[1]) if len(sys.argv[1:]) >= 1 and sys.argv[1] else 500000
CHUNK = 100000 if GAMES >= 100000 else GAMES
ALPHA = "0.003"
TH = max(2, (os.cpu_count() or 4) - 2)
SEED = "2700"
NBENCH = 300
GATE = 1.03
# patch259: ★10 확정 달성 올인 보상·탐색 파라미터
TEN_RW = dict(TENB=10, STAR9B=0, STAR8B=0, CLUST=0)   # patch260: 판 길이 우선 (bench_ten: 보너스 100+ 는 ★10·판 길이 둘 다 하락)
TEN_SIM = dict(TENB=10, CLUST=0)
LOW = 0x00004000 if os.name == "nt" else 0       # BELOW_NORMAL


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def done_path(name):
    return os.path.join(TR, "b_%s.done" % name)


def read_done(name):
    try:
        with open(done_path(name), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def mark(name, val):
    with open(done_path(name), "w", encoding="utf-8") as f:
        f.write(str(val))


def copy_w(src, dst):
    shutil.copyfile(src, dst + ".tmp")
    os.replace(dst + ".tmp", dst)
    shutil.copyfile(src + ".tup", dst + ".tup")


def base_env(**kw):
    env = dict(os.environ, RMODE="1")
    for k in ("POL", "PB1", "PU", "SCALE", "PRESTART", "RMIN", "MAXMV", "TUP", "BONUS", "NEEDLOAD",
              "CALIB", "CRN", "K2", "B2", "EXACT", "DEADP", "DEADG", "GATEP", "DUMP", "FIVEB",
              "TENB", "STAR9B", "STAR8B", "CLUST"):
        env.pop(k, None)
    env.update({k: str(v) for k, v in kw.items()})
    return env


def run(cmd, env, log=False):
    if log:
        with open(LOG, "a", encoding="utf-8") as lf:
            lf.write("\n[%s] %s\n" % (time.strftime("%m-%d %H:%M:%S"), " ".join(os.path.basename(c) for c in cmd)))
            lf.flush()
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 encoding="utf-8", errors="replace", env=env, creationflags=LOW)
            out = []
            for line in p.stdout:
                lf.write(line); lf.flush(); out.append(line)
                if "games" in line:
                    print("    " + line.rstrip(), flush=True)
            p.wait()
            return p.returncode, "".join(out)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, creationflags=LOW)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def parse_ten(out):
    """TEN 줄에서 (games with star10 %, star10/game) 추출"""
    m = re.search(r"TEN star10/game ([\d.]+).*?games with star10 ([\d.]+)%", out)
    if m:
        return float(m.group(2)), float(m.group(1))
    return 0.0, 0.0


def sim(wfile, d=2, calib=0):
    env = base_env(CRN=0, K2=0, B2=0, EXACT=0, CALIB=calib, **TEN_SIM)
    t0 = time.time()
    rc, out = run([SRCH, wfile, "sim", str(NBENCH), str(d), "8", "8", str(TH), SEED], env)
    m = re.search(r"SIM .*? moves ([\d.]+)", out)
    if not m:
        say("   SIM 결과 없음:", out.strip()[-300:])
        return None, 0.0, out
    s10_pct, _ = parse_ten(out)
    for l in out.splitlines():
        if l.startswith(("TEN", "SIM")):
            say("   %s" % l.strip())
    say("   (소요 %.1f분)" % ((time.time() - t0) / 60))
    return float(m.group(1)), s10_pct, out


def parse_scale(out):
    """CALIB 표(u별)에서 가중 meanG / meanV. 머리줄 열 이름으로 위치를 찾음 (형식이 달라도 동작)"""
    idx = None
    sv = sg = 0.0
    for l in out.splitlines():
        t = l.split()
        if not t or t[0] != "CALIB":
            continue
        if "meanV" in t and "meanG" in t:
            idx = None
            if len(t) > 1 and t[1] == "u":
                wcol = "n" if "n" in t else ("moves%" if "moves%" in t else ("share" if "share" in t else None))
                if wcol:
                    idx = (t.index(wcol), t.index("meanV"), t.index("meanG"))
            continue
        if idx and len(t) > max(idx) and re.match(r"^u?\d+$", t[1]):
            try:
                w = float(t[idx[0]].rstrip("%")); v = float(t[idx[1]]); g = float(t[idx[2]])
            except ValueError:
                continue
            sv += w * v; sg += w * g
    return (sg / sv) if sv > 0 else None


def main():
    say("=== 계획 B(★10 올인) 1~5단계 시작: 시범 %d판, 스레드 %d, 비교 seed %s, 탐색기 %s ===" % (GAMES, TH, SEED, os.path.basename(SRCH)))
    for f in (W0, W0 + ".tup", NT3, NT2C, SRCH):
        if not os.path.exists(f):
            say("파일 없음:", f); return
    free = shutil.disk_usage(TR).free / 2 ** 30
    need = os.path.getsize(W0) * 4 / 2 ** 30
    if free < need + 0.5:
        say("디스크 여유 부족: %.1fGB (필요 약 %.1fGB)" % (free, need + 0.5)); return

    # 1) 회귀 (보너스/결합 0 일 때 nt2 와 완전히 같은지)
    if read_done("reg") is None:
        say("1) 회귀: nt3(POL=0, 보너스 0) vs nt2 eval 300판")
        _, a = run([NT2C, "eval", W0, "300", "0"], base_env())
        _, b = run([NT3, "eval", W0, "300", "0"], base_env(POL=0, TENB=0, STAR9B=0, STAR8B=0, CLUST=0))
        ea = [l for l in a.splitlines() if l.startswith("EVAL")]
        eb = [l for l in b.splitlines() if l.startswith("EVAL")]
        say("   nt2 :", ea[0] if ea else a.strip()[-200:])
        say("   nt3 :", eb[0] if eb else b.strip()[-200:])
        if not ea or ea != eb:
            say("   !! 결과가 다름 -> 중단 (nt3 코드 확인 필요)"); return
        if os.path.exists(NT2):
            _, c = run([NT2, "eval", W0, "300", "0"], base_env())
            ec = [l for l in c.splitlines() if l.startswith("EVAL")]
            say("   (참고) 예전 nt2.exe:", "같음" if ec == ea else ("다름(빌드 옵션 차이로 실수 계산이 미세하게 다를 수 있음): " + (ec[0] if ec else "?")))
        t0 = time.time()
        _, d2 = run([NT3, "eval", W0, "100", "0"], base_env(POL=2, PB1=4, PU=3, **TEN_RW))
        e2 = [l for l in d2.splitlines() if l.startswith("EVAL")]
        say("   (참고) nt3 POL=2(★10 올인) 1스레드 100판: %s (%.0f초)" % (e2[0] if e2 else "?", time.time() - t0))
        mark("reg", "ok")
    else:
        say("1) 회귀: 이미 통과 (건너뜀)")

    # 2) 배율 측정 + 현재 두뇌 D2 기준값
    r = read_done("scale")
    if r is None:
        say("2) 배율 측정: 현재 두뇌 D2 CALIB %d판 (TENB=%s, CLUST=%s)" % (NBENCH, TEN_SIM["TENB"], TEN_SIM["CLUST"]))
        base, base10, out = sim(W0, 2, calib=1)
        s = parse_scale(out)
        if base is None or s is None:
            say("   !! CALIB/SIM 결과를 읽지 못함 -> 중단"); say(out.strip()[-500:]); return
        s = round(min(2.5, max(1.0, s)), 4)
        say("   배율 SCALE = %.4f (전체 meanG/meanV), 현재 두뇌 D2 = %.1f수 (★10 %.1f%%)" % (s, base, base10))
        mark("scale", "%s %s %s" % (s, base, base10))
    else:
        parts = [float(x) for x in r.split()]
        s, base = parts[0], parts[1]
        base10 = parts[2] if len(parts) > 2 else 0.0
        say("2) 배율: 이미 측정됨 SCALE %.4f, 현재 D2 %.1f수, ★10 %.1f%% (건너뜀)" % (s, base, base10))

    # 3) 대조군: 배율만
    r = read_done("scaleonly")
    if r is None:
        say("3) 대조군: 배율만 곱한 두뇌(학습 0) D2 %d판" % NBENCH)
        sw = os.path.join(TR, "b_scale.bin")
        rc, out = run([NT3, "scale", W0, sw, str(s)], base_env())
        if rc != 0:
            say("   !! scale 실패:", out.strip()[-300:]); return
        so, so10, _ = sim(sw, 2)
        if so is None:
            return
        use = s
        if so < base / GATE and so10 < base10:
            use = 1.0
            say("   배율만 곱해도 %.1f -> %.1f수 (★10 %.1f%% -> %.1f%%): 해로움 -> 시범 학습은 SCALE=1" % (base, so, base10, so10))
        else:
            say("   %.1f -> %.1f수 (★10 %.1f%% -> %.1f%%): SCALE %.4f 사용" % (base, so, base10, so10, s))
        mark("scaleonly", "%s %s %s" % (so, use, so10))
    else:
        parts = [float(x) for x in r.split()]
        so, use = parts[0], parts[1]
        so10 = parts[2] if len(parts) > 2 else 0.0
        say("3) 대조군: 이미 측정됨 %.1f수 (★10 %.1f%%), 사용 SCALE %.4f (건너뜀)" % (so, so10, use))

    # 4) 시범 학습 (★10 확정 달성 올인 보상 TEN_RW 적용)
    arms = [("ctl", dict(POL=0, SCALE=1, **TEN_RW)),
            ("all", dict(POL=2, PB1=4, PU=3, SCALE=use, **TEN_RW)),
            ("late", dict(POL=2, PB1=4, PU=7, SCALE=use, **TEN_RW))]
    for name, kw in arms:
        wf = os.path.join(TR, "b_%s.bin" % name)
        if read_done("train_" + name) is not None and os.path.exists(wf):
            say("4) 시범 학습 %s: 이미 끝남 (건너뜀)" % name); continue
        say("4) 시범 학습 %s: %s, %d판, alpha %s" % (name, " ".join("%s=%s" % kv for kv in kw.items()), GAMES, ALPHA))
        copy_w(W0, wf)       # 중간에 끊겼으면 처음부터 다시 (SCALE 이 두 번 곱해지지 않게)
        t0 = time.time()
        env = base_env(PRESTART=0.5, RMIN=80, MAXMV=5000, NEEDLOAD=1, **kw)
        rc, out = run([NT3, "train", wf, str(GAMES), str(CHUNK), ALPHA, str(TH)], env, log=True)
        last = [l for l in out.splitlines() if "games" in l]
        if rc != 0 or not last:
            say("   !! 학습 실패:", out.strip()[-300:]); return
        say("   끝 (%.1f분): %s" % ((time.time() - t0) / 60, last[-1].strip()))
        mark("train_" + name, "ok")

    # 5) 선별 (patch260: 판 길이 우선, ★10 보조)
    say("5) 선별: D2 %d판, seed %s (같은 조각 순서, TENB=%s CLUST=%s)" % (NBENCH, SEED, TEN_SIM["TENB"], TEN_SIM["CLUST"]))
    res = {}
    res10 = {}
    for name, _ in arms:
        r = read_done("bench_" + name)
        if r is not None:
            parts = [float(x) for x in r.split()]
            res[name] = parts[0]
            res10[name] = parts[1] if len(parts) > 1 else 0.0
            say("   %s: %.1f수, ★10 %.1f%% (이미 측정)" % (name, res[name], res10[name])); continue
        say("   %s:" % name)
        v, s10, _ = sim(os.path.join(TR, "b_%s.bin" % name), 2)
        if v is None:
            return
        res[name] = v
        res10[name] = s10
        mark("bench_" + name, "%s %s" % (v, s10))
    ctl = res["ctl"]
    ctl10 = res10["ctl"]
    say("--- 요약 (D2 %d판: ★10 달성률 및 평균 수) ---" % NBENCH)
    say("   현재 두뇌        ★10 %5.1f%% | %.1f수" % (base10, base))
    say("   배율만           ★10 %5.1f%% | %.1f수 (%+.1f%%)" % (so10, so, (so / base - 1) * 100))
    for name in ("ctl", "all", "late"):
        say("   %-5s           ★10 %5.1f%% (현재 %+.1f%%p, ctl %+.1f%%p) | %.1f수 (현재 %+.1f%%, ctl %+.1f%%)" %
            (name, res10[name], res10[name] - base10, res10[name] - ctl10,
             res[name], (res[name] / base - 1) * 100, (res[name] / ctl - 1) * 100))
    # ★10 달성률이 현재 두뇌 및 ctl 보다 높거나(최우선), 동률이면 판 길이가 +3% 이상인 후보 선별
    # patch260: 판 길이 +3% 관문이 기준, ★10 달성률은 동률일 때만 (★10 ~8% 라 300판에서 ±1.6%p 는 잡음)
    cands = [n for n in ("ctl", "all", "late") if res[n] >= ctl * GATE]
    if cands:
        best = max(cands, key=lambda n: (res[n], res10[n]))
        say("관문 통과: %s -> 6단계 본 학습 후보 = %s (b_%s.bin, ★10 %.1f%%, 평균 %.1f수)" %
            (", ".join(cands), best, best, res10[best], res[best]))
    else:
        say("관문 미통과: ★10 달성률 및 판 길이 개선 부족 -> 보상 가중치 추가 조정 검토")
    say("=== 끝 (실전 두뇌·설정은 바꾸지 않음) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        say("오류:", repr(ex))
