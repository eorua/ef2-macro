"""cleanup.py - C:\\macro 정리 (patch159). 지우지 않고 _archive\\<날짜>\\ 로 옮기기만 함 (되돌리기 쉬움)

  py cleanup.py        옮길 목록만 보여줌 (아무것도 안 바꿈)
  py cleanup.py go     실제로 옮김

옮기는 것
  - 백업 파일 (*.bak*, main.py.bak 등)        - 적용 끝난 패치 스크립트 (patch*.py, patch_main.py)
  - 예전 시험용 스크립트 (아래 OLD 목록)        - 루트의 예전 캡처 (scan_*.png, notice_now.png, log_tail.txt)
  - shots 안에서 3일 지난 반복 저장 화면 (wc_fail_*, bk_notfull_*, maint_hit_*, soul_miss_*, skill_miss_*, cont_cd_*, chest_noboost_*)
매크로가 쓰는 파일(main.py, panel.py, 각 모듈, tpl, tests, state.json, settings.json)은 건드리지 않음
"""
import os, sys, glob, shutil, time, fnmatch

BASE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(BASE, "_archive", time.strftime("%Y-%m-%d"))
OLD = ["arch_probe.py", "fast_probe.py", "skill_probe.py", "popuptest.py", "wavetest.py", "wcsnap.py",
       "detect.py", "grid.py", "guide.py", "opt.py", "watch.py", "attend.py", "reset_high.py",
       "mktpl.py", "mktpl_ask.py", "mktpl_attend.py"]
ROOT_PAT = ["*.bak*", "patch*.py", "scan_*.png", "log_tail.txt", "notice_now.png"]
SHOT_PAT = ["wc_fail_*", "bk_notfull_*", "maint_hit_*", "soul_miss_*", "skill_miss_*", "cont_cd_*", "chest_noboost_*", "dia_unknown_*"]
KEEP_DAYS = 3


def targets():
    out = []
    for n in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, n)
        if not os.path.isfile(p) or n == "cleanup.py":
            continue
        if n in OLD or any(fnmatch.fnmatch(n, pat) for pat in ROOT_PAT):
            out.append((p, os.path.join(DEST, n)))
    sd = os.path.join(BASE, "shots")
    cut = time.time() - KEEP_DAYS * 86400
    if os.path.isdir(sd):
        for n in sorted(os.listdir(sd)):
            p = os.path.join(sd, n)
            if os.path.isfile(p) and any(fnmatch.fnmatch(n, pat) for pat in SHOT_PAT) and os.path.getmtime(p) < cut:
                out.append((p, os.path.join(DEST, "shots", n)))
    return out


def main():
    go = "go" in sys.argv[1:]
    t = targets()
    size = sum(os.path.getsize(p) for p, _ in t)
    for p, q in t:
        print(("옮김  " if go else "대상  ") + os.path.relpath(p, BASE))
        if go:
            os.makedirs(os.path.dirname(q), exist_ok=True)
            shutil.move(p, q)
    print("%d개, %.1f MB %s" % (len(t), size / 1e6, "-> " + os.path.relpath(DEST, BASE) + " 로 옮김" if go else "(실제로 옮기려면: py cleanup.py go)"))


if __name__ == "__main__":
    main()
