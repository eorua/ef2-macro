"""pet.py - 대표 펫 자동 교체 (통합 프리셋 창 안에서)
  사이클: 환생~6200 팅키(퀘스트 29번이 200c 이상 400c 미만이면 랩티) / 고레벨 업글 백호 -> 최대치면 맘보 / 이후 사르크
  펫은 그림 가운데(테두리·배경·별 제외)의 윤곽선으로 구분 -> 등급이 올라 배경색이 바뀌어도 구분됨
  py pet.py look           (통합 프리셋 창을 연 상태) 펫 위치와 점수, 지금 대표 펫
  py pet.py set 백호 go    (통합 프리셋 창을 연 상태) 대표 펫만 바꿈 (저장은 안 누름)
  py pet.py quest          퀘스트 탭을 열어 29번 레벨 읽기 (누르기만, 펫은 안 바꿈)
"""
import os, re, sys, time, subprocess
import cv2, numpy as np
import preset

BASE = r"C:\macro"
TPL = os.path.join(BASE, "tpl")
SHOTS = os.path.join(BASE, "shots")
ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
NOWIN = 0x08000000                # CREATE_NO_WINDOW (검은 창 깜빡임 방지)

NAMES = {"맘보": "mambo", "팅키": "tinky", "조커": "joker", "레오": "leo",
         "랩티": "rapty", "사르크": "sark", "백호": "baekho"}
REP = (86, 834)                      # 대표 펫 칸 왼쪽 위 (65x65)
GRID_X0, GRID_DX = 193, 75.4         # 즐겨찾기 펫 칸: 한 줄 6칸
GRID_Y0, GRID_DY = 835, 77
COLS, ROWS = 6, 3
MIN_SCORE, MIN_MARGIN, REP_SCORE = 0.5, 0.25, 0.6

# 퀘스트
TAB_QUEST = (68, 1240)
TAB_HERO = (185, 1240)
Q_TITLE = "quest29.png"              # '29. 국경 요충지 장악' 제목 글자
Q_HEAD = "quest_head.png"            # 퀘스트 창 왼쪽 위 '퀘스트' 글자 (창이 열렸는지 확인)
Q_AREA = (120, 200, 420, 1215)       # 제목을 찾는 범위 x1, y1, x2, y2
LV_DX, LV_DY = (15, 110), (46, 74)   # 제목 왼쪽 위 기준 레벨 글자('Lv.200c') 범위
TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TO_RAPTY, TO_TINKY = 200e9, 400e9    # 200c 이상 랩티 / 400c 이상 다시 팅키 (c = 10^9)
QUEST_EVERY = 300                    # 퀘스트 확인 간격(초)
QUEST_SOON = 60                      # 29번이 100c~200c 이면 곧 200c -> 1분마다
CHEST_BTN = (620, 790)               # 퀘스트 창 오른쪽 위 보물상자 (골드 받기)
CHEST_TRIES = 5                      # 4배속이 아니면 1분 뒤 다시, 최대 5번
SPEED_TPL = "speed_x4.png"           # 왼쪽 위 'x4' 배속 아이콘


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 펫 그림 비교
def _feat(img, x, y, pad=0):
    c = img[y + 8 - pad:y + 46 + pad, x + 12 - pad:x + 53 + pad]
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))


_T = {}


def templates():
    if not _T:
        for k, f in NAMES.items():
            im = cv2.imread(os.path.join(TPL, "pet_%s.png" % f))
            if im is not None:                       # 저장된 그림은 칸 전체(65x65) -> 같은 방식으로 특징 계산
                _T[k] = _feat(im, 0, 0)
    return _T


def _scores(img, x, y):
    f = _feat(img, x, y, pad=4)
    return {k: float(cv2.matchTemplate(f, t, cv2.TM_CCOEFF_NORMED).max()) for k, t in templates().items()}


def _filled(img, x, y):
    """칸에 펫이 있는지 (테두리 색이 진함)"""
    hsv = cv2.cvtColor(img[y:y + 65, x:x + 65], cv2.COLOR_BGR2HSV)
    return float(((hsv[..., 1] > 120) & (hsv[..., 2] > 120)).mean()) > 0.08


def slots(img):
    """[(이름, 점수, 차이, 누를 곳)] 칸마다 가장 닮은 펫"""
    out = []
    for r in range(ROWS):
        for c in range(COLS):
            x, y = int(round(GRID_X0 + GRID_DX * c)), GRID_Y0 + GRID_DY * r
            if y + 70 > img.shape[0] or not _filled(img, x, y):
                continue
            s = sorted(_scores(img, x, y).items(), key=lambda kv: -kv[1])
            if not s:
                continue
            out.append((s[0][0], s[0][1], s[0][1] - (s[1][1] if len(s) > 1 else 0), (x + 32, y + 32)))
    return out


def rep_pet(img):
    """대표 칸의 펫 이름 (확실하지 않으면 None)"""
    s = sorted(_scores(img, *REP).items(), key=lambda kv: -kv[1])
    if s and s[0][1] >= REP_SCORE and s[0][1] - (s[1][1] if len(s) > 1 else 0) >= MIN_MARGIN:
        return s[0][0]
    return None


def select(name, img=None):
    """통합 프리셋 창이 열린 상태에서 대표 펫을 name 으로. 이미 그 펫이면 True. 저장은 안 누름"""
    if name not in NAMES or len(templates()) < 2:
        log("펫 그림(tpl\\pet_*.png)이 없어 펫 교체 건너뜀"); return False
    img = img if img is not None else preset.capture()
    if img is None or not preset.preset_open(img):
        return False
    cur = rep_pet(img)
    if cur == name:
        log("대표 펫 이미 %s" % name); return True
    cand = [s for s in slots(img) if s[0] == name]
    if not cand:
        log("%s 칸을 못 찾음 (칸별: %s)" % (name, ", ".join("%s %.2f/%.2f" % s[:3] for s in slots(img)))); return False
    nm, sc, mg, pt = max(cand, key=lambda s: s[1])
    if sc < MIN_SCORE or mg < MIN_MARGIN:
        log("%s 판단이 애매함 (점수 %.2f, 차이 %.2f) -> 안 누름" % (name, sc, mg)); return False
    log("대표 펫 %s -> %s (점수 %.2f, 차이 %.2f)" % (cur, name, sc, mg))
    preset.tap(pt, "펫 %s" % name)
    img = preset.wait_for(lambda im: rep_pet(im) == name, 2.5, first=0.3, step=0.25)
    if img is None or rep_pet(img) != name:
        log("눌렀는데 대표 칸이 %s 로 안 바뀜" % name); return False
    return True


# ---------------------------------------------------------------- 퀘스트 29번 레벨
def _adb(*a):
    return subprocess.run(ADB + list(a), capture_output=True, timeout=15, creationflags=NOWIN)


def _find_title(img, tpl):
    x1, y1, x2, y2 = Q_AREA
    g = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    r = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(r)
    return (loc[0] + x1, loc[1] + y1) if mx >= 0.8 else None


def _ocr_level(crop):
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] >= 15) & (hsv[..., 0] <= 40) & (hsv[..., 1] >= 120) & (hsv[..., 2] >= 150))
    m = m | ((hsv[..., 1] <= 50) & (hsv[..., 2] >= 200))          # patch134: 최대가 아닐 때 흰 글자도
    t = np.where(m, 0, 255).astype(np.uint8)                     # 노란 글자만 -> 흰 바탕 검은 글자
    t = cv2.resize(t, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    t = cv2.copyMakeBorder(t, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    p = os.path.join(SHOTS, "quest_lv_ocr.png")
    cv2.imwrite(p, t)
    if os.path.exists(TESS):
        r = subprocess.run([TESS, p, "-", "--psm", "7", "-c",
                            "tessedit_char_whitelist=Lv.0123456789abcdefghijklmnopqrstuvwxyz"],
                           capture_output=True, text=True, timeout=10, creationflags=NOWIN)
        return r.stdout.strip().replace(" ", "")
    try:
        import ocrx
        ws = sorted(ocrx.words(cv2.cvtColor(t, cv2.COLOR_GRAY2BGR)) or [], key=lambda w: w[1])
        return "".join(w[0] for w in ws).replace(" ", "")
    except Exception:
        return ""


def level_value(text):
    """'Lv.200c' -> 2e11. 단위 a=10^3, b=10^6, c=10^9 ... 못 읽으면 None"""
    m = re.search(r"(\d+(?:\.\d+)?)([a-z]{0,2})$", text or "")
    if not m:
        return None
    v, suf = float(m.group(1)), m.group(2)
    if not suf:
        return v
    if len(suf) == 1:
        return v * 10 ** (3 * (ord(suf) - 96))
    return v * 10 ** (3 * (26 + (ord(suf[0]) - 96) * 26 + (ord(suf[1]) - 96)))   # 두 글자 단위(아주 큼)


def read_quest29(max_swipes=12):
    """퀘스트 탭에서 29번 퀘스트 레벨을 읽음 -> (값, 글자) / 못 찾으면 (None, 이유). 끝나면 영웅 탭으로"""
    tpl = cv2.imread(os.path.join(TPL, Q_TITLE), cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        return None, "tpl\\quest29.png 없음"
    try:
        preset.tap(TAB_QUEST, "퀘스트 탭")
        time.sleep(0.8)
        head = cv2.imread(os.path.join(TPL, Q_HEAD), cv2.IMREAD_GRAYSCALE)
        if head is not None:                         # 다른 창(크리스탈 등)이 떠 있으면 퀘스트 창이 안 열림
            img = preset.capture()
            g = cv2.cvtColor(img[600:900, 0:200], cv2.COLOR_BGR2GRAY) if img is not None else None
            if g is None or float(cv2.matchTemplate(g, head, cv2.TM_CCOEFF_NORMED).max()) < 0.8:
                return None, "퀘스트 창이 안 열림(다른 창이 떠 있음?)"
        prev = None
        same = 0
        for i in range(max_swipes + 1):
            img = preset.capture()
            if img is None:
                return None, "캡처 실패"
            pos = _find_title(img, tpl)
            if pos:
                x, y = pos
                crop = img[y + LV_DY[0]:y + LV_DY[1], LV_DX[0]:LV_DX[1]]
                t = _ocr_level(crop)
                return level_value(t), t
            band = cv2.cvtColor(img[840:1200, 150:600], cv2.COLOR_BGR2GRAY).astype(int)
            if prev is not None and float(np.abs(band - prev).mean()) < 2.0:
                same += 1
                if same >= 2:                        # 두 번 연속 안 움직이면 목록 끝
                    try:
                        cv2.imwrite(os.path.join(SHOTS, "quest_nofind.png"), img)
                    except Exception:
                        pass
                    return None, "목록 끝까지 내렸는데 29번이 없음 (shots\\quest_nofind.png)"
            else:
                same = 0
            prev = band
            _adb("shell", "input", "swipe", "360", "1170", "360", "870", "500")
            time.sleep(0.7)
        return None, "29번을 못 찾음"
    finally:
        preset.tap(TAB_QUEST, "퀘스트 탭")  # patch292: 퀘스트 탭 기본 대기 유지
        time.sleep(0.4)


def quest_target(value, cur):
    """29번 레벨로 정한 ①~③ 구간 대표 펫"""
    if value is None:
        return cur
    return "랩티" if TO_RAPTY <= value < TO_TINKY else "팅키"


def speed_x4(img):
    """왼쪽 위 배속 아이콘이 'x4' 이고 남은 시간(노란 숫자)이 보이면 True. (점수, 노랑) 도 같이"""
    tpl = cv2.imread(os.path.join(TPL, SPEED_TPL), cv2.IMREAD_GRAYSCALE)
    if img is None or tpl is None:
        return False, 0.0, 0.0
    g = cv2.cvtColor(img[50:110, 90:160], cv2.COLOR_BGR2GRAY)
    sc = float(cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED).max())
    hsv = cv2.cvtColor(img[70:90, 134:176], cv2.COLOR_BGR2HSV)
    yel = float(((hsv[..., 0] >= 18) & (hsv[..., 0] <= 35) & (hsv[..., 1] >= 120) & (hsv[..., 2] >= 150)).mean())
    return (sc >= 0.85 and yel >= 0.08), sc, yel


def chest_tick(st, say=log):
    """29번 400c + 팅키 뒤: 4배속이면 퀘스트 보물상자 1번 누름, 아니면 1분 뒤 재시도(최대 5번)"""
    img = preset.capture()
    on, sc, yel = speed_x4(img)
    if not on:
        st["chest_try"] = st.get("chest_try", 0) + 1
        try:
            cv2.imwrite(os.path.join(SHOTS, "chest_noboost_%d.png" % st["chest_try"]), img)
        except Exception:
            pass
        if st["chest_try"] >= CHEST_TRIES:
            st["chest_pending"] = False
            say("4배속이 아님 (x4 %.2f, 시간 %.2f) %d번 -> 이번 환생은 보물상자 생략" % (sc, yel, st["chest_try"]))
        else:
            st["chest_next"] = time.time() + 60
            say("4배속이 아님 (x4 %.2f, 시간 %.2f) -> 1분 뒤 다시 (%d/%d)" % (sc, yel, st["chest_try"], CHEST_TRIES))
        return True
    try:
        preset.tap(TAB_QUEST, "퀘스트 탭")
        time.sleep(0.8)
        head = cv2.imread(os.path.join(TPL, Q_HEAD), cv2.IMREAD_GRAYSCALE)
        img = preset.capture()
        g = cv2.cvtColor(img[600:900, 0:200], cv2.COLOR_BGR2GRAY) if img is not None else None
        if head is not None and (g is None or float(cv2.matchTemplate(g, head, cv2.TM_CCOEFF_NORMED).max()) < 0.8):
            st["chest_try"] = st.get("chest_try", 0) + 1
            st["chest_next"] = time.time() + 60
            say("퀘스트 창이 안 열림 -> 보물상자 1분 뒤 다시")
            return True
        preset.tap(CHEST_BTN, "퀘스트 보물상자")
        time.sleep(1.2)
        try:
            cv2.imwrite(os.path.join(SHOTS, "chest_after.png"), preset.capture())
        except Exception:
            pass
        st["chest_pending"] = False
        say("4배속 확인 (x4 %.2f) -> 퀘스트 보물상자 1번 누름 (shots\\chest_after.png)" % sc)
        try:
            import closer                               # 보상 창이 떴으면 닫기
            closer.close_all()
        except Exception:
            pass
    finally:
        preset.tap(TAB_HERO, "영웅 탭")
        time.sleep(0.4)
    return True


# ---------------------------------------------------------------- patch134/patch292b: 확인 시점 맞추기
# 유저 스펙 상향에 맞추어 기존 29퀘 기본 간격 대폭 최적화 (하한선 및 초기값 단축)
Q_FIRST = (120, 360, 180)       # 환생 뒤 첫 확인(초): 최소 120, 최대 360, 초기값 180
Q_400 = (60, 180, 90)           # 랩티로 바꾼 뒤 400c 첫 확인(초): 최소 60, 최대 180, 초기값 90
Q_STEP = 20                     # 맞추는 폭(초)
Q_RETRY = 20                    # 200c 전 다시 확인 간격(초)
Q_RETRY_400 = 15                # 400c 전 다시 확인 간격(초)

# patch286: 30퀘 빌드(골드 프리셋) 전용 초고속 간격 (골드 증가로 29퀘 만렙 도달이 훨씬 빠름)
Q_FIRST_Q30 = (25, 60, 35)      # 30퀘 환생 뒤 첫 확인: 35초 (최소 25, 최대 60)
Q_400_Q30 = (15, 45, 20)        # 30퀘 랩티 뒤 첫 확인: 20초 (최소 15, 최대 45)
Q_RETRY_Q30 = 15                # 30퀘 200c 전 다시 확인 간격(초)
Q_RETRY_400_Q30 = 12            # 30퀘 400c 전 다시 확인 간격(초)


def _is_q30(st):
    try:
        import q30
        return q30.on(st)
    except Exception:
        return False


def first_delay(st):
    """main 이 환생 직후 부름: 첫 확인까지 몇 초"""
    st["pq_t0"] = time.time()
    st["pq_miss200"] = 0
    st["pq_miss400"] = 0
    if _is_q30(st):
        return int(st.get("pq_first_q30", Q_FIRST_Q30[2]))
    return int(st.get("pq_first", Q_FIRST[2]))


def _adapt(st, key, lim, misses):
    """첫 확인에서 바로 맞았으면(misses 0) 다음엔 Q_STEP 일찍, 2번 이상 놓쳤으면 늦게"""
    lo, hi, d0 = lim
    d = st.get(key, d0)
    if misses == 0:
        d -= Q_STEP
    elif misses >= 2:
        d += Q_STEP
    st[key] = int(max(lo, min(hi, d)))


def quest_tick(st, say=log):
    """메인 루프에서 호출 (환생 후 ~ 고레벨 전). 할 일을 했으면 True
    확인 간격: 못 읽음 1분 / 50c 미만 2분 / 50c~200c 1분 / 랩티로 바꾼 직후 3분, 그 뒤 1분 / 400c 넘어 팅키로 돌아가면 이번 환생은 끝"""
    if st.get("chest_pending") and not st.get("pq_done"):
        st["chest_pending"] = False                     # 환생해서 새 사이클 -> 지난 보물상자 대기는 버림
    if st.get("chest_pending") and time.time() >= st.get("chest_next", 0):
        return chest_tick(st, say)
    if st.get("pq_done") or time.time() < st.get("pq_next", 0):
        return False
    v, t = read_quest29()
    cur = st.get("pet_q", "팅키")
    tgt = quest_target(v, cur)
    q30_mode = _is_q30(st)
    # patch134 / patch286: 지난 판 기록으로 맞춘 간격 (30퀘 빌드는 초고속 간격 적용)
    if v is None or v < TO_RAPTY:
        if cur == "랩티":
            st["pq_miss400"] = st.get("pq_miss400", 0) + (1 if v is not None or "안 열림" not in str(t) else 0)
            nxt = Q_RETRY_400_Q30 if q30_mode else Q_RETRY_400
        else:
            st["pq_miss200"] = st.get("pq_miss200", 0) + (1 if v is not None or "안 열림" not in str(t) else 0)
            nxt = Q_RETRY_Q30 if q30_mode else Q_RETRY
    elif v < TO_TINKY:
        if cur != "랩티":
            if q30_mode:
                _adapt(st, "pq_first_q30", Q_FIRST_Q30, st.get("pq_miss200", 0))
                nxt = int(st.get("pq_d400_q30", Q_400_Q30[2]))
            else:
                _adapt(st, "pq_first", Q_FIRST, st.get("pq_miss200", 0))
                nxt = int(st.get("pq_d400", Q_400[2]))
            if st.get("pq_t0"):
                say("  200c 확인: 환생 %.1f분 뒤 (그전 못 미친 확인 %d번) -> 다음 판 첫 확인 %d초" % (
                    (time.time() - st["pq_t0"]) / 60, st.get("pq_miss200", 0),
                    st.get("pq_first_q30" if q30_mode else "pq_first")))
            st["pq_miss400"] = 0
        else:
            st["pq_miss400"] = st.get("pq_miss400", 0) + 1
            nxt = Q_RETRY_400_Q30 if q30_mode else Q_RETRY_400
    else:
        if cur == "랩티":
            if q30_mode:
                _adapt(st, "pq_d400_q30", Q_400_Q30, st.get("pq_miss400", 0))
                say("  400c 확인 (그전 못 미친 확인 %d번) -> 다음 판 랩티 뒤 첫 확인 %d초" % (
                    st.get("pq_miss400", 0), st["pq_d400_q30"]))
            else:
                _adapt(st, "pq_d400", Q_400, st.get("pq_miss400", 0))
                say("  400c 확인 (그전 못 미친 확인 %d번) -> 다음 판 랩티 뒤 첫 확인 %d초" % (
                    st.get("pq_miss400", 0), st["pq_d400"]))
        nxt = 300
    st["pq_next"] = time.time() + nxt
    say("퀘스트 29번 레벨 %s (%s) -> 대표 펫 %s%s / 다음 확인 %d초 뒤" % (
        t, "%.3g" % v if v else "-", tgt, "" if tgt == cur else " (%s에서 교체)" % cur, nxt))
    if tgt != cur:
        if preset.set_presets(None, None, pet=tgt):
            st["pet_q"] = tgt
            if tgt == "팅키" and v is not None and v >= TO_TINKY:
                st["pq_done"] = True                   # 400c 도달 -> 이번 환생은 더 확인 안 함
                st.update(chest_pending=True, chest_try=0, chest_next=time.time() + 3)
                say("퀘스트 29번 400c 도달 -> 이번 환생은 퀘스트 확인 끝, 보물상자 단계로")
        else:
            st["pq_next"] = time.time() + 60           # 실패하면 1분 뒤 다시
    elif v is not None and v >= TO_TINKY:
        st["pq_done"] = True
        st.update(chest_pending=True, chest_try=0, chest_next=time.time() + 3)
        say("퀘스트 29번 400c 도달 -> 이번 환생은 퀘스트 확인 끝, 보물상자 단계로")
    return True


# ---------------------------------------------------------------- 시험
if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "go"]
    preset.GO = "go" in sys.argv[1:]
    cmd = a[0] if a else ""
    if cmd == "look":
        img = preset.capture()
        log("통합 프리셋 창:", preset.preset_open(img))
        for s in slots(img):
            log("  %s 점수 %.2f 차이 %.2f 위치 %s" % s)
        log("대표 펫:", rep_pet(img))
    elif cmd == "set" and len(a) >= 2:
        log("결과:", select(a[1]))
    elif cmd == "quest":
        preset.GO = True
        log("29번:", read_quest29())
    else:
        print(__doc__)
