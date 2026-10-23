"""tests/run_tests.py - 인식 회귀 테스트 (patch158)
저장된 화면(tests/img/*.png)에 화면 인식 함수들을 돌려서, 기준 결과(golden.json)와 다르면 알려줌.
게임/ADB 는 건드리지 않음 (사진만 읽음).

  py tests\\run_tests.py            기준과 비교 (다르면 목록 출력, 종료코드 1)
  py tests\\run_tests.py record     지금 결과를 기준으로 저장 (의도한 변경을 확인한 뒤에만)
  py tests\\run_tests.py show home  이름에 home 이 들어간 사진의 결과만 출력

expect.json : 사람이 확인한 정답 (예: 바탕화면 사진에서만 home_screen=True). 기준과 별개로 항상 검사.
"""
import os, sys, json, glob, io, contextlib, importlib, traceback
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
os.chdir(BASE)

# (모듈, 함수, 이름) - 사진 한 장만 받는 인식 함수들. OCR(윈도우/테서랙트)을 쓰는 함수는 넣지 않음
CHECKS = [
    ("main", "home_screen"), ("main", "fall_popup"), ("main", "result_popup"), ("main", "continue_btn"),
    ("main", "popup_open"), ("main", "wave_visible"), ("main", "dl_popup"),
    ("wave", "read_wave"),
    ("wavecall", "dlg_open"), ("wavecall", "tab_selected"), ("wavecall", "auto_on"),
    ("arrange", "dialog_open"), ("arrange", "status"),
    ("preset", "preset_open"), ("preset", "bulk_open"), ("preset", "hero_auto_on"),
    ("skillctl", "auto_on"), ("skillctl", "ring_ok"),
    ("hud", "state"),
    ("pet", "rep_pet"), ("pet", "speed_x4"),
    ("barracks", "barracks_open"), ("barracks", "is_full"),
    ("closer", "close_buttons"),
    ("daily", "blocked"),
    ("notice", "detect"),
    ("soul", "screen_state"),
    ("guild", "guild_open"),
    ("inf2", "is_open"),
    ("friend", "dot"),
]


def norm(v):
    """비교하기 쉬운 값으로: 소수는 2자리, numpy 는 파이썬 값으로"""
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), 2)
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in v.items()}
    if isinstance(v, np.ndarray):
        return "<array %s>" % (v.shape,)
    if v is None or isinstance(v, str):
        return v
    return repr(v)


def close(a, b, tol=0.03):
    """소수 오차(0.03)는 같은 것으로 봄"""
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= tol
        except Exception:
            return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    return a == b


def run_all(filt=None):
    mods, out = {}, {}
    for m, _ in CHECKS:
        if m not in mods:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    mods[m] = importlib.import_module(m)
            except Exception as e:
                mods[m] = e
    for p in sorted(glob.glob(os.path.join(HERE, "img", "*.png"))):
        name = os.path.basename(p)
        if filt and filt not in name:
            continue
        img = cv2.imread(p)
        if img is None:
            continue
        if img.shape[:2] != (1280, 720):
            img = cv2.resize(img, (720, 1280))
        res = {}
        for m, f in CHECKS:
            key = "%s.%s" % (m, f)
            mod = mods[m]
            if isinstance(mod, Exception):
                res[key] = "IMPORT ERROR: %r" % (mod,)
                continue
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    res[key] = norm(getattr(mod, f)(img.copy()))
            except Exception as e:
                res[key] = "ERROR: %s" % (type(e).__name__,)
        out[name] = res
    return out


def main():
    args = sys.argv[1:]
    gpath = os.path.join(HERE, "golden.json")
    epath = os.path.join(HERE, "expect.json")
    if args[:1] == ["show"]:
        for n, r in run_all(args[1] if len(args) > 1 else None).items():
            print("==", n)
            for k, v in r.items():
                print("  %-26s %s" % (k, v))
        return 0
    now = run_all()
    if args[:1] == ["record"]:
        with open(gpath, "w", encoding="utf-8") as f:
            json.dump(now, f, ensure_ascii=False, indent=1, sort_keys=True)
        print("기준 저장: 사진 %d장 x 함수 %d개" % (len(now), len(CHECKS)))
        return 0
    bad = 0
    try:
        gold = json.load(open(gpath, encoding="utf-8"))
    except Exception:
        gold = {}
        print("기준(golden.json)이 없음 -> 'record' 로 먼저 만드세요")
    for n, r in now.items():
        g = gold.get(n)
        if g is None:
            print("[새 사진] %s (기준 없음)" % n)
            continue
        for k, v in r.items():
            if k not in g:
                continue
            if not close(v, g[k]):
                bad += 1
                print("[다름] %-28s %-26s 기준 %s -> 지금 %s" % (n, k, g[k], v))
    try:
        exp = json.load(open(epath, encoding="utf-8"))
    except Exception:
        exp = {}
    for n, want in exp.items():
        if n.startswith("_"):
            continue
        r = now.get(n)
        if r is None:
            print("[정답 검사] 사진 없음: %s" % n)
            bad += 1
            continue
        for k, v in want.items():
            got = r.get(k)
            okv = close(got, v) or (isinstance(got, list) and isinstance(v, bool) and bool(got and got[0]) == v)
            if not okv:
                bad += 1
                print("[정답 틀림] %-26s %-26s 정답 %s / 지금 %s" % (n, k, v, got))
    errs = [(n, k, v) for n, r in now.items() for k, v in r.items() if isinstance(v, str) and ("ERROR" in v)]
    for n, k, v in errs[:20]:
        print("[오류] %s %s %s" % (n, k, v))
    print("결과: 사진 %d장, 다름/틀림 %d건, 오류 %d건" % (len(now), bad, len(errs)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
