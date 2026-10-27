"""q30.py - (시범) 퀘스트 30번 열기 전략. 패널 옵션 'q30_open' 으로 켜고 끔 (기본 꺼짐)

흐름 (환생 한 번당):
  pre     : 환생 직후 영웅 '골드' / 유물 '시간' / 펫 팅키. 29퀘 200c~400c 랩티 교체는 기존 pet.py 그대로
  collect : 29퀘 400c 도달 -> 유물 '골드 모으기' + 팅키 -> (pet.py 가 4배속 확인 후 보물상자 1번)
            -> 1분마다 화면 아래 골드(주황 숫자)를 읽어 170ao 이상이 두 번 연속이면 open
  open    : 유물 '오픈골드 감소' + 펫 레오 -> 퀘스트 탭 맨 아래 30번 '오픈' 버튼이 활성(회색 아님)일 때만 누름
            회색이면 누르지 않고 '골드 모으기' + 팅키로 되돌려 collect 계속
  done    : 영웅 '기본' / 유물 '시간' / 펫 팅키 -> 이후 원래 사이클
  skip    : 고레벨 단계(6500)가 먼저 오면 이번 환생은 포기 (고레벨 단계는 그대로 진행)

  py q30.py gold        지금 화면의 골드 읽기만
  py q30.py look        퀘스트 탭 맨 아래 30번 줄과 오픈 버튼 상태 보기 (누르지 않음)
"""
import os, re, sys, time, subprocess
import cv2, numpy as np
import preset

BASE = r"C:\macro"
SHOTS = os.path.join(BASE, "shots")
TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]

GOLD_ROI = (588, 716, 716, 754)      # 화면 아래 정보줄의 골드(주황 글자) x1, y1, x2, y2
TARGET = "170ao"                     # 이만큼 모이면 오픈 시도 (patch285: 200ao -> 170ao)
GOLD_EVERY = 25                      # 골드 확인 간격(초) (patch286: 텀 단축 60초 -> 25초)
OPEN_RETRY = 120                     # 오픈 버튼이 회색이었으면 이만큼 뒤에 다시 (초, patch286: 300초 -> 120초)
MAX_OPEN_TRIES = 6
TAB_QUEST = (68, 1240)
TAB_HERO = (185, 1240)
BTN_DX, BTN_DY = 630, 18             # 30번 제목 줄 y 기준 오픈 버튼 위치 (x 는 고정)
SAT_ACTIVE = 60                      # 버튼 채도(중앙값)가 이보다 높으면 활성(갈색), 낮으면 회색

# ---- patch244: 좌측 상단 종족 보너스 아이콘 판별 (720x1280) ----
# 외곽 호박·꽃 이벤트 테두리(상단 y<=55, 좌우 x<=37 / x>=95) 및 하단 레벨("Lv.80": y>=118) 제외
TRIBE_TPL_BOX = (43, 64, 89, 106)    # 순수 얼굴 중심부 크롭 좌표 (46x42)
TRIBE_ROI = (37, 58, 95, 112)        # 탐색 영역 (58x54, 상하좌우 ±6px 여유)
TRIBE_SCORE_TH = 0.75                # 최고 점수 최소 임계값 (settings.json 'tribe_score_th' 오버라이드 지원)
TRIBE_MARGIN_TH = 0.15               # 1위 - 2위 점수 차 최소 마진 (settings.json 'tribe_margin_th' 오버라이드 지원)
TRIBE_RETRIES = 5                    # 환생 직후 아이콘 지연 대비 재시도 횟수
TRIBE_RETRY_SEC = 1.5                # 재시도 간격(초)
TRIBE_KO = {"HUMAN": "인간", "ELF": "엘프", "UNDEAD": "언데드", "ORC": "오크", "UNKNOWN": "미인식"}
_TRIBE_TPLS = None
_LAST_TRIBE = {"tribe": None, "score": 0.0}


def log(*a):
    print(*a, flush=True)


def _float_setting(key, default):
    try:
        import json
        with open(os.path.join(BASE, "settings.json"), encoding="utf-8") as f:
            v = json.load(f).get(key)
        return float(v) if v is not None else float(default)
    except Exception:
        return float(default)


def human_only_on():
    """패널 옵션 '인간 판에서만 30퀘' (기본 켜짐)"""
    try:
        import daily
        return daily.setting("q30_human_only", True)
    except Exception:
        return True


def on(st=None):
    """30퀘 전략 활성 여부:
    - q30_open 이 켜져 있어야 함
    - q30_human_only(기본 켜짐)가 켜져 있으면 현재 판 종족(reborn_tribe)이 HUMAN 일 때만 True"""
    try:
        import daily
        if not daily.setting("q30_open", False):
            return False
        if human_only_on():
            tr = (st.get("reborn_tribe") if isinstance(st, dict) else None) or _LAST_TRIBE.get("tribe")
            return tr == "HUMAN"
        return True
    except Exception:
        return False


def _load_tribe_templates():
    """templates/tribe_*.png 또는 tpl/tribe_*.png 로드 -> {종족대문자: BGR이미지}"""
    global _TRIBE_TPLS
    if _TRIBE_TPLS is not None:
        return _TRIBE_TPLS
    tpls = {}
    rx1, ry1, rx2, ry2 = TRIBE_ROI
    rw, rh = rx2 - rx1, ry2 - ry1
    for d in (os.path.join(BASE, "templates"), os.path.join(BASE, "tpl")):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            low = fn.lower()
            if not (low.startswith("tribe_") and low.endswith(".png")):
                continue
            code = low[6:-4].upper()
            if code in ("GRID", "LOOK", "UNKNOWN") or code in tpls:
                continue
            im = cv2.imread(os.path.join(d, fn), cv2.IMREAD_COLOR)
            if im is None or im.shape[0] > rh or im.shape[1] > rw:
                continue
            tpls[code] = im
    _TRIBE_TPLS = tpls
    return tpls


def score_tribe(img):
    """단일 화면에서 좌상단 종족 아이콘 매칭 점수 계산.
    반환: (판정종족, 1위점수, 1위종족, 2위종족, 2위점수, 전체점수dict)"""
    if img is None or img.shape[:2] != (1280, 720):
        return "UNKNOWN", 0.0, "NONE", "NONE", 0.0, {}
    tpls = _load_tribe_templates()
    if not tpls:
        return "UNKNOWN", 0.0, "NONE", "NONE", 0.0, {}
    x1, y1, x2, y2 = TRIBE_ROI
    sub = img[y1:y2, x1:x2]
    scores = {}
    for code, tpl in tpls.items():
        res = cv2.matchTemplate(sub, tpl, cv2.TM_CCOEFF_NORMED)
        _, sc, _, _ = cv2.minMaxLoc(res)
        scores[code] = float(sc)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    b_code, b_sc = ranked[0]
    s_code, s_sc = ranked[1] if len(ranked) > 1 else ("NONE", -1.0)
    sth = _float_setting("tribe_score_th", TRIBE_SCORE_TH)
    mth = _float_setting("tribe_margin_th", TRIBE_MARGIN_TH)
    if b_sc >= sth and (b_sc - s_sc) >= mth:
        return b_code, b_sc, b_code, s_code, s_sc, scores
    return "UNKNOWN", b_sc, b_code, s_code, s_sc, scores


def check_reborn_tribe(st=None, img=None, retries=TRIBE_RETRIES, delay=TRIBE_RETRY_SEC, say=log):
    """좌상단 종족 아이콘을 판별해 st['reborn_tribe'] 에 저장하고 반환.
    환생 직후 아이콘이 늦게 뜰 수 있으므로 retries 회 재시도 후 실패 시 UNKNOWN."""
    last_img = img
    tribe, b_sc, b_code, s_code, s_sc, scores = "UNKNOWN", 0.0, "NONE", "NONE", 0.0, {}
    tries = max(1, int(retries))
    for i in range(tries):
        cur = img if (i == 0 and img is not None) else preset.capture()
        if cur is not None:
            last_img = cur
            tribe, b_sc, b_code, s_code, s_sc, scores = score_tribe(cur)
            if tribe != "UNKNOWN":
                break
        if i < tries - 1:
            time.sleep(delay)
    _LAST_TRIBE.update(tribe=tribe, score=round(float(b_sc), 3))
    if isinstance(st, dict):
        st["reborn_tribe"] = tribe
        st["reborn_tribe_score"] = round(float(b_sc), 3)
        st["reborn_tribe_2nd"] = "%s:%.2f" % (s_code, s_sc)
        st["reborn_tribe_ts"] = int(time.time())
        st["reborn_tribe_checked"] = True
    ko = TRIBE_KO.get(tribe, tribe)
    if tribe != "UNKNOWN":
        mode_msg = "30퀘 실행" if on(st) else "일반 모드(30퀘 생략)"
        say("[종족] 판별: %s(%s) (점수 %.2f, 2위 %s %.2f, 마진 +%.2f) -> %s" % (
            ko, tribe, b_sc, s_code, s_sc, b_sc - s_sc, mode_msg))
    else:
        if last_img is not None:
            _save("tribe_unknown.png", last_img)
        say("[종족] 판별 실패 -> UNKNOWN (최고 %s %.2f, 2위 %s %.2f) -> 일반 모드(30퀘 생략)" % (
            b_code, b_sc, s_code, s_sc))
    return tribe


def _save(name, img):
    try:
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, name), img)
    except Exception:
        pass


# ---------------------------------------------------------------- 골드 읽기
def _value(text):
    import pet
    return pet.level_value(text)


def read_gold(img):
    """(값, 글자). 못 읽으면 (None, 글자)"""
    if img is None:
        return None, ""
    x1, y1, x2, y2 = GOLD_ROI
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = (hsv[..., 0] >= 8) & (hsv[..., 0] <= 28) & (hsv[..., 1] >= 140) & (hsv[..., 2] >= 170)
    t = np.where(m, 0, 255).astype(np.uint8)
    t = cv2.resize(t, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    t = cv2.copyMakeBorder(t, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    p = os.path.join(SHOTS, "q30_gold_ocr.png")
    _save("q30_gold_ocr.png", t)
    txt = ""
    if os.path.exists(TESS):
        try:
            r = subprocess.run([TESS, p, "-", "--psm", "7", "-c",
                                "tessedit_char_whitelist=0123456789.abcdefghijklmnopqrstuvwxyz"],
                               capture_output=True, text=True, timeout=10, creationflags=0x08000000)
            txt = r.stdout.strip().replace(" ", "")
        except Exception:
            txt = ""
    if not txt:
        try:
            import ocrx
            ws = sorted(ocrx.words(cv2.cvtColor(t, cv2.COLOR_GRAY2BGR)) or [], key=lambda w: w[1])
            txt = "".join(w[0] for w in ws).replace(" ", "").lower()
        except Exception:
            txt = ""
    txt = _fix_unit(txt)
    if re.fullmatch(r"\d{4,}", txt):                 # patch185: 단위까지 숫자로 읽음 ('213ao' -> '21340', 10-18 18:14)
        t2 = ""
        try:                                          # 윈도우 OCR 로 한 번 더
            import ocrx
            ws = sorted(ocrx.words(cv2.cvtColor(t, cv2.COLOR_GRAY2BGR)) or [], key=lambda w: w[1])
            t2 = _fix_unit("".join(w[0] for w in ws).replace(" ", "").lower())
        except Exception:
            pass
        if re.search(r"\d+(?:\.\d+)?[a-z]{2}", t2):
            txt = t2
        else:                                         # 끝 두 글자를 글자로 되돌림 (4->a, 0->o ...)
            mp = {"4": "a", "0": "o", "6": "b", "8": "b", "5": "s", "1": "l"}
            if txt[-1] in mp and txt[-2] in mp:
                txt = txt[:-2] + mp[txt[-2]] + mp[txt[-1]]
    if re.fullmatch(r"\.?\d+(?:\.\d+)?[a-z]", txt.strip(".")):          # patch167: 단위가 한 글자면 윈도우 OCR 로 한 번 더
        try:
            import ocrx
            ws = sorted(ocrx.words(cv2.cvtColor(t, cv2.COLOR_GRAY2BGR)) or [], key=lambda w: w[1])
            t2 = _fix_unit("".join(w[0] for w in ws).replace(" ", "").lower())
            if re.search(r"\d+(?:\.\d+)?[a-z]{2}", t2):
                txt = t2
        except Exception:
            pass
    try:                                              # patch186: 글꼴 견본 (원본 색 조각)
        import glyph
        glyph.save("gold", img[y1:y2, x1:x2], txt)
    except Exception:
        pass
    m2 = re.search(r"\d+(?:\.\d+)?[a-z]{1,2}", txt)
    if not m2:
        return None, txt
    return _value(m2.group(0)), m2.group(0)


def _fix_unit(txt):
    """patch167: 단위 글자 뒤의 숫자는 글자를 잘못 읽은 것 ('200a0' -> '200ao'). 10-18 'ao' 를 'a0' 으로 읽어 200a 로 판단, 30퀘가 안 열림"""
    m = re.search(r"[a-z]", txt)
    if not m:
        return txt
    head, tail = txt[:m.start()], txt[m.start():]
    tail = tail.translate(str.maketrans({"0": "o", "1": "l", "5": "s", "8": "b"}))
    return head + tail


def gold_ok(st, v, t, say=log):
    """소수점 오독 대비: 직전 값보다 1분 사이에 5배 넘게 뛰면 무시, 목표 이상이 두 번 연속일 때만 True"""
    tgt = _value(TARGET)
    prev = st.get("q30_gold")
    if v is None:
        say("  [30퀘] 골드 못 읽음 (%s)" % t)
        return False
    if prev and v > prev * 5:
        rej = st.get("q30_rej")
        if rej and rej / 3 <= v <= rej * 3:          # patch167: 튄 값이 두 번 연달아 비슷하면 진짜로 보고 받아들임
            say("  [30퀘] 골드 %s 가 두 번 연속 비슷하게 읽힘 -> 이 값으로 다시 시작" % t)
            st.pop("q30_rej", None)
        else:
            st["q30_rej"] = v
            say("  [30퀘] 골드 %s 는 직전 %.3g 에서 너무 뛰어 오독으로 보고 무시" % (t, prev))
            st["q30_hits"] = 0
            return False
    st.pop("q30_rej", None)
    st["q30_gold"] = v
    if v >= tgt:
        st["q30_hits"] = st.get("q30_hits", 0) + 1
    else:
        st["q30_hits"] = 0
    say("  [30퀘] 골드 %s (목표 %s, 연속 %d)" % (t, TARGET, st.get("q30_hits", 0)))
    return st.get("q30_hits", 0) >= 2


# ---------------------------------------------------------------- 퀘스트 30번 줄
def _adb(*a):
    return subprocess.run(ADB + list(a), capture_output=True, timeout=15, creationflags=0x08000000)


def _to_bottom(max_swipes=10):
    """patch286: 퀘스트 목록 맨 아래(30번)까지 스크롤. 600px 씩 시원하게 스와이프"""
    import ocrx
    img = preset.capture()
    for i in range(max_swipes):
        if img is None:
            return None
        _adb("shell", "input", "swipe", "360", "1080", "360", "480", "350")
        time.sleep(0.5)
        img = preset.capture()
        if img is None:
            return None
        if i >= 3:  # 최소 4회 이상 스크롤 후 30번 위치 확인
            ws = ocrx.words(img) or []
            ys = [w[2] for w in ws if "협상" in w[0] or w[0].startswith("30.")]
            if ys:
                y = max(ys)
                if y > 1080:  # 30번 제목이 화면 밑에 살짝 걸쳤으면 추가 스와이프로 온전히 올림
                    _adb("shell", "input", "swipe", "360", "1000", "360", "750", "300")
                    time.sleep(0.5)
                    img = preset.capture()
                return img
    return img


def row30(img):
    """patch286: 30번 줄 -> (제목 y, 오픈 버튼 좌표, 버튼 활성 여부, 버튼 글자, 채도, lv0, coin) / 못 찾으면 None"""
    if img is None:
        return None
    import ocrx
    ws = ocrx.words(img) or []
    # 30. 또는 협상 (퀘스트 바닥 위치는 y ≈ 1130~1150)
    ys = [w[2] for w in ws if ("협상" in w[0] or w[0].startswith("30.")) and 600 <= w[2] <= 1180]
    if not ys:
        return None
    y = max(ys)
    bx, by = BTN_DX, y + BTN_DY
    # patch286: 동전 아이콘 간섭을 피하기 위해 버튼 상단 배경(by-20:by-5)의 채도 측정 (회색=0~25, 활성갈색=80~200)
    roi_top = img[by - 20:by - 5, bx - 45:bx + 45]
    sat = float(np.median(cv2.cvtColor(roi_top, cv2.COLOR_BGR2HSV)[..., 1])) if roi_top.size > 0 else 0.0
    btxt = " ".join(w[0] for w in ws if abs(w[2] - by) < 30 and w[1] > 540)
    lv0 = any(re.search(r"Lv\.?0\b", w[0]) for w in ws if w[1] < 160 and 0 < w[2] - y < 90)
    hv = cv2.cvtColor(img[y + 18:y + 50, 156:178], cv2.COLOR_BGR2HSV) if y + 50 <= 1280 else None
    coin = float(((hv[..., 0] >= 12) & (hv[..., 0] <= 35) & (hv[..., 1] >= 120) & (hv[..., 2] >= 150)).mean()) if hv is not None and hv.size > 0 else 0.0
    if coin < 0.12:                                   # 열린 줄 0.3~0.43, 안 열린 30번 0.0
        lv0 = True
    active = sat >= 50
    return y, (bx, by), active, btxt, sat, lv0, coin


def _closed(btxt):
    """patch187: 버튼 글자가 '오픈'의 일부라도 있으면 아직 안 열림 (10-18 '픈 0 189a0' 을 열린 것으로 오판)"""
    return "오픈" in btxt or "픈" in btxt or "오" in btxt


def open_quest30(say=log):
    """patch286: 퀘스트 탭 맨 아래 30번 오픈 버튼이 활성일 때만 누름 -> 'opened' / 'gray' / 'fail'"""
    try:
        preset.tap(TAB_QUEST, "퀘스트 탭")
        time.sleep(0.8)
        img = _to_bottom()
        if img is None:
            return "fail"
        r = row30(img)
        if r is None:
            # 살짝 올려서 한 번 더 시도
            _adb("shell", "input", "swipe", "360", "950", "360", "650", "300")
            time.sleep(0.5)
            img = preset.capture()
            r = row30(img) if img is not None else None
        if r is None:
            _save("q30_norow.png", img)
            say("  [30퀘] 30번 줄을 못 찾음 (shots\\q30_norow.png)")
            return "fail"
        y, pt, active, btxt, sat, lv0, coin = r
        _save("q30_before.png", img)
        # patch286 오판 방지: 'max' 가 있으면 이미 열린 퀘스트 줄
        if "max" in btxt.lower():
            say("  [30퀘] 30번이 이미 열려 있음 (버튼=%s, coin=%.2f) -> opened" % (btxt, coin))
            return "opened"
        if not lv0:
            # patch296: 이미 열린 줄(Lv.1 이상, 코인 아이콘 있음)이면 버튼은 '오픈'이 아니라 레벨업 -> 절대 누르지 않고 열린 것으로 처리
            say("  [30퀘] 30번이 이미 열려 있음 (Lv.1 이상, coin=%.2f, 버튼=%s) -> 누르지 않고 opened" % (coin, btxt))
            return "opened"
        if not active:
            say("  [30퀘] 오픈 버튼이 회색 (채도 %.0f, %s) -> 아직 골드 부족" % (sat, btxt))
            return "gray"
        say("  [30퀘] 오픈 버튼 활성 (채도 %.0f, %s) -> 누름" % (sat, btxt))
        preset.tap(pt, "30번 오픈")
        time.sleep(1.5)
        img2 = preset.capture()
        if img2 is not None:
            _save("q30_after.png", img2)
            r2 = row30(img2)
            if r2 is not None:
                _, _, active2, btxt2, sat2, lv02, coin2 = r2
                # patch296: 버튼 회색 여부가 아니라 줄이 열렸는지(lv0 해제)로 판정 (열린 뒤에는 다음 레벨업 비용 부족으로 버튼이 회색이 됨)
                if lv02 and "max" not in btxt2.lower():
                    say("  [30퀘] 눌렀는데 아직 미오픈 상태임 (sat=%.0f, %s, coin=%.2f)" % (sat2, btxt2, coin2))
                    return "gray"
        return "opened"
    finally:
        try:
            import closer
            closer.close_all()
        except Exception:
            pass
        preset.tap(TAB_HERO, "영웅 탭")
        time.sleep(0.4)


# ---------------------------------------------------------------- 메인 루프 연결
def low_presets(st=None):
    """환생 직후 (영웅, 유물)"""
    return ("골드", "시간") if on(st) else ("기본", "시간")


def start(st, say=log):
    """환생 직후 프리셋을 맞춘 뒤 main 이 부름"""
    active = on(st)
    st["q30"] = "pre" if active else None
    st.update(q30_gold=None, q30_hits=0, q30_tries=0, q30_next=0)
    tr = st.get("reborn_tribe") or _LAST_TRIBE.get("tribe") or "UNKNOWN"
    ko = TRIBE_KO.get(tr, tr)
    if active:
        say("[30퀘] 시작 (종족=%s/%s -> pre 단계 진입)" % (ko, tr))
    elif human_only_on() and daily_q30_open():
        say("[30퀘] 종족=%s(%s) -> 인간 판이 아니므로 이번 판은 30퀘 생략 (일반 모드)" % (ko, tr))


def daily_q30_open():
    try:
        import daily
        return daily.setting("q30_open", False)
    except Exception:
        return False


def restart_presets(st):
    """재시작 후 다시 맞출 (영웅, 유물, 펫) 또는 None(기존 규칙대로)"""
    ph = st.get("q30")
    if ph in ("restore", "restore_skip"):
        return "기본", "시간", "팅키"
    if not on(st) or ph not in ("pre", "collect", "open"):
        return None
    if ph == "pre":
        return "골드", "시간", st.get("pet_q", "팅키")
    return "골드", "골드 모으기", "팅키"


def collecting(st):
    return on(st) and st.get("q30") in ("collect", "open")


def restore(st, say=log):
    """영웅 기본 / 유물 시간 / 팅키 로 되돌림. 실패하면 다음 루프에서 다시"""
    if preset.set_presets("기본", "시간", pet="팅키"):
        st["q30"] = "done" if st.get("q30") == "restore" else "skip"
        st["pet_q"] = "팅키"
    else:
        st["q30_next"] = time.time() + 30
    return True


def abandon(st, why, say=log, restore_now=True):
    """이번 환생은 포기. 영웅 프리셋이 '골드'로 남지 않게 기본/시간/팅키로 되돌림"""
    if st.get("q30") in ("pre", "collect", "open"):
        say("[30퀘] %s -> 이번 환생은 30퀘 열기 포기 (영웅 기본 / 유물 시간으로)" % why)
        st["q30"] = "restore_skip"
        if restore_now:
            restore(st, say)


def tick(st, say=log):
    """메인 루프(환생 후 ~ 고레벨 전)에서 pet.quest_tick 보다 먼저 부름. 할 일을 했으면 True"""
    ph = st.get("q30")
    if ph == "done" and on(st) and not st.get("q30_fix188"):    # patch187/188: 10-18 18:20 '이미 열림' 오판 -> 한 번만 다시 확인
        st["q30_fix188"] = 1
        say("[30퀘] patch188: 30번이 정말 열렸는지 다시 확인 (골드 모으기 단계부터)")
        st.update(q30="collect", q30_hits=0, q30_next=0, q30_tries=0)
        ph = "collect"
    if ph in ("restore", "restore_skip"):                     # 되돌리기 실패했던 것 다시 (옵션을 꺼도)
        if time.time() >= st.get("q30_next", 0):
            return restore(st, say)
        return False
    if not on(st) and ph in ("pre", "collect", "open"):       # patch191/244: 도중에 옵션을 끄거나 인간 판 조건 불일치 시 복구
        why = "인간 판이 아님(%s)" % st.get("reborn_tribe") if (daily_q30_open() and human_only_on()) else "패널에서 30퀘 옵션을 끔"
        abandon(st, why, say)
        return True
    if not on(st) or ph not in ("pre", "collect", "open"):
        return False
    now = time.time()
    if ph == "pre":
        if st.get("pq_done"):                                  # 29퀘 400c 도달 (pet.py 가 팅키로 돌려놓음)
            say("[30퀘] 29퀘 400c 도달 -> 유물 '골드 모으기' + 팅키")
            if preset.set_presets(None, "골드 모으기", pet="팅키"):
                st["q30"] = "collect"
                st["q30_next"] = now + GOLD_EVERY
            else:
                st["q30_next"] = now + 60
            return True
        return False
    if now < st.get("q30_next", 0) or st.get("chest_pending"):   # 보물상자 단계가 먼저
        return False
    if ph == "collect":
        img = preset.capture()
        v, t = read_gold(img)
        st["q30_next"] = now + GOLD_EVERY
        if not gold_ok(st, v, t, say):
            return True
        say("[30퀘] 골드 %s 확인 -> 유물 '오픈골드 감소' + 펫 레오" % TARGET)
        if not preset.set_presets(None, "오픈골드 감소", pet="레오"):
            st["q30_next"] = now + 60
            return True
        st["q30"] = "open"
        ph = "open"
    if ph == "open":
        st["q30_tries"] = st.get("q30_tries", 0) + 1
        r = open_quest30(say)
        if r == "opened":
            say("[30퀘] 퀘스트 30번 오픈 완료 -> 영웅 기본 / 유물 시간 / 팅키")
            st["q30"] = "restore"
            return restore(st, say)
        if st["q30_tries"] >= MAX_OPEN_TRIES:
            abandon(st, "오픈 시도 %d번 실패" % st["q30_tries"], say)
            return True
        say("[30퀘] 오픈 못 함(%s) -> '골드 모으기' + 팅키로 되돌리고 %d분 뒤 다시" % (r, OPEN_RETRY // 60))
        preset.set_presets(None, "골드 모으기", pet="팅키")
        st.update(q30="collect", q30_hits=0, q30_next=time.time() + OPEN_RETRY)
        return True
    return False


if __name__ == "__main__":
    a = sys.argv[1:]
    if "tribe" in a:
        p = next((x for x in a if x != "tribe" and os.path.exists(x)), None)
        im = cv2.imread(p) if p else preset.capture()
        tr, b_sc, b_code, s_code, s_sc, scs = score_tribe(im)
        print("판정:", tr, "| 1위:", b_code, round(b_sc, 3), "| 2위:", s_code, round(s_sc, 3), "| 전체:", {k: round(v, 3) for k, v in scs.items()})
    elif "gold" in a:
        print("골드:", read_gold(preset.capture()))
    elif "look" in a:
        preset.GO = True
        try:
            preset.tap(TAB_QUEST, "퀘스트 탭")
            time.sleep(0.8)
            img = _to_bottom()
            print("30번 줄:", row30(img) if img is not None else None)
        finally:
            preset.tap(TAB_HERO, "영웅 탭")
    else:
        print(__doc__)
