"""daily.py - 일일 작업 자동화 (던전 소탕 / 일일 랭킹전 / 일일퀘스트 보상 받기)
사용:  py daily.py              -> 판별만 (클릭 안 함)
       py daily.py go           -> 전체 실행 (던전, 랭킹전, 퀘스트)
       py daily.py go dungeon   -> 던전만
       py daily.py go ranking   -> 랭킹전만
       py daily.py go quest     -> 퀘스트 보상만
"""
import cv2, numpy as np, subprocess, sys, time, os, json, datetime
import speed          # 대기시간 단축 (speed.py 의 FACTOR)

from dev import ADB_EXE as ADB   # patch162
from dev import SERIAL as DEV
SHOTS = r"C:\macro\shots"

MAX_WAVE = 6200          # 이 웨이브 이상이면 일일 작업 안 함
SWEEP_COUNT = 3          # 던전 소탕 횟수
QUEST_COOLDOWN = 3600    # 퀘스트 보상 확인 최소 간격(초)

TAB_BATTLE = (535, 1245)
ROW_DUNGEON = (300, 870)
ROW_RANKING = (300, 1060)
BTN_ENTER_FIRST = (632, 865)         # 던전 선택 화면의 첫 번째(킹슬라임) 입장
SWEEP_BTNS = [(508, 960), (508, 1052), (508, 1145)]
SWEEP_OK = (360, 722)
SWEEP_OK_ROI = (250, 690, 470, 755)
JOIN_BTN = (360, 1050)
JOIN_ROI = (280, 1020, 440, 1085)
X_PANEL = (678, 790)
X_PANEL_ROI = (645, 765, 712, 815)
QUEST_ICON = (595, 185)
QUEST_DOT_ROI = (598, 155, 622, 180)
QUEST_X = (638, 194)
QUEST_X_ROI = (610, 170, 668, 220)
QUEST_ROWS_Y = [425, 515, 603, 692, 780, 869, 957]
QUEST_BTN_X = (530, 650)
# 무한랭킹전
MY_LEVEL = 72                      # 내 레벨 (올라가면 이 숫자만 바꾸세요)
ROW_INF = (300, 950)
INF_X = (683, 432)
INF_X_ROI = (655, 410, 712, 455)
INF_BTN_Y = [718, 842, 965]        # 상대 3명의 전투 버튼 y (x=622)
INF_REFRESH = (610, 650)
INF_DIA_ROI = (588, 610, 622, 640)  # 새로고침 버튼의 다이아 아이콘 (보이면 무료 0회)
INF_ALERT_OK = (360, 467)
INF_ALERT_ROI = (300, 445, 420, 490)
HERO_BTN = (360, 1240)
HERO_ROI = (300, 1215, 420, 1265)
RES_OK = (360, 860)
RES_ROI = (280, 835, 440, 885)
INF_BATTLE_TIMEOUT = 40          # patch123: 20 -> 40
INF_INTERVAL = 7200                # 다음 자동 실행까지 (2시간) - patch100
INF_RETRY = 600

# 상점 광고 (광고제거 패키지: 클릭 한 번이면 보상)
TAB_SHOP = (650, 1245)
AD_GEM_TAB = (515, 790)
AD_BTN = {"speed": (615, 958), "coin": (615, 1050), "gem": (615, 1142)}
AD_ROI = {"speed": (550, 935, 680, 985), "coin": (550, 1030, 680, 1075), "gem": (550, 1120, 680, 1165)}
AD_MAX = {"coin": 5, "gem": 10}


SETTINGS_FILE = r"C:\macro\settings.json"


def setting(key, default=False):
    """settings.json (조작 패널에서 켜고 끔) 에서 옵션을 읽음. 파일이 없으면 기본값."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return bool(json.load(f).get(key, default))
    except Exception:
        return default


def log(*a):
    print(time.strftime("[%H:%M:%S] daily:"), *a, flush=True)


def adb(*args):
    import dev                                  # patch162: 공통 ADB (시간 제한)
    return dev.run(list(args))


def cap():
    import dev                                  # patch162
    return dev.capture()


def tap(pt, wait=1.0):
    adb("shell", "input", "tap", str(pt[0]), str(pt[1]))
    time.sleep(wait)


def ratio(img, roi, kind):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if kind == "green":
        m = (h >= 35) & (h <= 85) & (s >= 120) & (v >= 100)
    elif kind == "red":
        m = ((h <= 8) | (h >= 172)) & (s >= 150) & (v >= 100)
    else:  # dot: 빨강/주황 깜빡이는 점
        m = ((h <= 25) | (h >= 172)) & (s >= 200) & (v >= 200)
    return float(m.mean())


def has_x(img, roi=X_PANEL_ROI):
    return ratio(img, roi, "red") >= 0.15


def get_wave(img):
    try:
        import wave
        w = wave.read_wave(img, exact=True)
        return int(w) if w else None
    except Exception as e:
        log("웨이브 읽기 실패:", e)
        return None


def blocked(img):
    """성 함락 / 환생 결과 팝업이 떠 있으면 True"""
    try:
        import rebirth
        for tpl, roi in (("title_fall.png", rebirth.FALL_TITLE),
                         ("title_result.png", rebirth.RES_TITLE)):
            r = rebirth.match(img, tpl, roi)
            s = r[0] if isinstance(r, (tuple, list)) else r
            if s >= 0.85:
                return True
    except Exception as e:
        log("팝업 검사 실패(무시):", e)
    return False


def safe_wave_ok(img=None):
    """웨이브 상한 이하이고 팝업이 없으면 True"""
    if img is None:
        img = cap()
    if blocked(img):
        log("성 함락/환생결과 팝업 감지 -> 중단")
        return False
    w = get_wave(img)
    if w is not None and w >= MAX_WAVE:
        log("웨이브 %d >= %d -> 중단" % (w, MAX_WAVE))
        return False
    return True


def close_panels(max_n=3):
    """우측 상단 빨간 X(패널 닫기)가 보이는 동안 닫기. 안 보이면 아무것도 안 누름."""
    for _ in range(max_n):
        img = cap()
        if has_x(img):
            tap(X_PANEL, 0.8)
        else:
            break


def go_battle():
    close_panels()
    tap(TAB_BATTLE, 1.0)


# ---------------------------------------------------------------- 던전
def do_dungeon(go):
    import dungeon                              # patch101: 새 던전 소탕 (가장 적은 재화 보스 + 광고)
    return dungeon.run(go)
    go_battle()
    if not safe_wave_ok():
        return False
    img = cap()
    log("던전 화면 진입 시도")
    if not go:
        return True
    tap(ROW_DUNGEON, 1.3)
    if not has_x(cap()):
        log("던전 선택 화면을 못 찾음 -> 중단")
        close_panels()
        return False
    tap(BTN_ENTER_FIRST, 1.3)
    done = 0
    for i in range(SWEEP_COUNT):
        if not safe_wave_ok():
            break
        ok = False
        for btn in SWEEP_BTNS:
            tap(btn, 0.9)
            img = cap()
            if ratio(img, SWEEP_OK_ROI, "green") >= 0.30:
                ok = True
                break
        if not ok:
            log("소탕 결과 팝업이 안 뜸(티켓 없음 등) -> 중단")
            break
        tap(SWEEP_OK, 1.0)
        done += 1
        log("던전 소탕 %d/%d 완료" % (done, SWEEP_COUNT))
    close_panels()
    return done > 0


# ---------------------------------------------------------------- 랭킹전
def do_ranking(go):
    go_battle()
    if not safe_wave_ok():
        return False
    if not go:
        return True
    tap(ROW_RANKING, 1.3)
    img = cap()
    g = ratio(img, JOIN_ROI, "green")
    log("참여하기 버튼 초록 비율 %.2f" % g)
    joined = False
    if g >= 0.30:
        tap(JOIN_BTN, 1.5)
        joined = True
        log("일일 랭킹전 참여")
    else:
        log("참여하기 버튼 없음(이미 참여했거나 화면 다름)")
    close_panels()
    return joined


# ---------------------------------------------------------------- 퀘스트
CHEST_X = [118, 270, 423, 576]      # 포인트 상자 25 / 50 / 75 / 100


def claim_chests():
    """받을 수 있는(보라색 아이콘) 포인트 상자를 누름"""
    n = 0
    for cx in CHEST_X:
        img = cap()
        y1, y2, x1, x2 = 328, 354, cx - 14, cx + 14
        hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        r = float(((h >= 120) & (h <= 160) & (s >= 60) & (v >= 100)).mean())
        log("포인트 상자 x=%d 보라색 비율 %.2f" % (cx, r))
        if r >= 0.15:
            tap((cx, 310), 1.0)
            n += 1
            log("포인트 상자 수령 (x=%d)" % cx)
    return n

def hud_ensure(close=True):
    """오른쪽 메뉴가 접혀 있으면 펼치고, 가려져 있으면 창을 닫음 (실패해도 그냥 진행)"""
    try:
        import hud
        if not hud.ensure(close):
            log("오른쪽 메뉴 펼침 확인 실패 (그냥 진행)")
    except Exception as e:
        log("hud_ensure 오류:", e)


def do_quest(go, force=False):
    hud_ensure(False)
    img = cap()
    dot = ratio(img, QUEST_DOT_ROI, "dot")
    log("퀘스트 아이콘 점 비율 %.2f" % dot)
    if dot < 0.05 and not force:
        return False
    if not go:
        return True
    if not safe_wave_ok(img):
        return False
    close_panels()
    hud_ensure()
    tap(QUEST_ICON, 1.3)
    img = cap()
    if not has_x(img, QUEST_X_ROI):
        log("일일퀘스트 창을 못 찾음 -> 중단")
        return False
    claimed = 0
    for _ in range(8):
        img = cap()
        target = None
        for y in QUEST_ROWS_Y:
            roi = (QUEST_BTN_X[0], y - 25, QUEST_BTN_X[1], y + 25)
            if ratio(img, roi, "green") >= 0.35:
                target = (590, y)
                break
        if target is None:
            break
        tap(target, 1.0)
        claimed += 1
        log("보상 받기 클릭 (y=%d)" % target[1])
    claimed += claim_chests()
    img = cap()
    os.makedirs(SHOTS, exist_ok=True)
    cv2.imwrite(os.path.join(SHOTS, "daily_quest_after.png"), img)
    if has_x(img, QUEST_X_ROI):
        tap(QUEST_X, 1.0)
    close_panels()
    return claimed > 0


# ---------------------------------------------------------------- 무한랭킹전
def blue_ratio(img, roi):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return float(((h >= 95) & (h <= 115) & (s >= 100) & (v >= 150)).mean())


def inf_free_refresh(img):
    """무료 새로고침이 남아 있으면 True (다이아 아이콘이 보이면 0회)"""
    return blue_ratio(img, INF_DIA_ROI) < 0.08


def _inf_close():
    img = cap()
    if has_x(img, INF_X_ROI):
        tap(INF_X, 1.0)
    close_panels()


def _inf_battle():
    """전투 버튼을 누른 직후부터 결과 확인까지. 'ok' / 'empty' / 'abort'"""
    time.sleep(1.5)
    for _ in range(5):
        img = cap()
        if img is None:
            time.sleep(1)
            continue
        if ratio(img, HERO_ROI, "red") >= 0.25:
            break
        if ratio(img, INF_ALERT_ROI, "green") >= 0.25:
            log("티켓 부족 알림 -> 확인")
            tap(INF_ALERT_OK, 1.0)
            return "empty"
        time.sleep(1.0)
    else:
        log("영웅 선택 화면을 못 찾음 -> 중단")
        return "abort"
    tap(HERO_BTN, 2.0)
    t0 = time.time()
    left_list = False
    while time.time() - t0 < INF_BATTLE_TIMEOUT:
        img = cap()
        if img is not None:
            try:                                       # patch123: 결과 창 없이 목록으로 돌아오면 끝난 것으로
                import inf2
                if not inf2.is_open(img):
                    left_list = True
                elif left_list and time.time() - t0 > 6:
                    log("결과 창을 못 봤지만 목록으로 돌아옴 -> 전투 끝난 것으로 봄")
                    return "ok"
            except Exception:
                pass
            if blocked(img):
                log("전투 중 성 함락/결과 팝업 감지 -> 중단")
                return "abort"
            if ratio(img, RES_ROI, "green") >= 0.30:
                tap(RES_OK, 1.5)
                return "ok"
        time.sleep(3.0)
    try:
        img = cap()
        if img is not None:
            os.makedirs(SHOTS, exist_ok=True)
            cv2.imwrite(os.path.join(SHOTS, "inf_timeout.png"), img)
            log("그때 화면 저장: shots\\inf_timeout.png")
    except Exception:
        pass
    log("전투 결과가 %d초 안에 안 뜸 -> 중단" % INF_BATTLE_TIMEOUT)
    return "abort"


def do_infinite(go):
    """무한랭킹전: 내 레벨 이하 상대만 전투, 없으면 무료 새로고침, 그것도 없으면 맨 위 상대.
    다이아는 쓰지 않음. 티켓이 없을 때까지 반복. 반환: 'empty' / 'abort' / 'ok'"""
    import lvdigits
    go_battle()
    if not safe_wave_ok():
        return "abort"
    tap(ROW_INF, 1.5)
    img = cap()
    try:
        import inf2
        if inf2.is_open(img):
            return inf2.run(go, img)
    except Exception as e:
        log("새 무한랭킹전 처리 오류: %r" % (e,))
    if img is None or not has_x(img, INF_X_ROI):
        log("무한랭킹전 상대 목록 화면을 못 찾음 -> 중단")
        close_panels()
        return "abort"
    if not go:
        lv = lvdigits.read_levels(img)
        log("상대 레벨 %s / 내 레벨 %d / 무료 새로고침 %s" % (lv, MY_LEVEL, "있음" if inf_free_refresh(img) else "없음(다이아)"))
        _inf_close()
        return "ok"
    status = "ok"
    fought = 0
    refreshes = 0
    for _ in range(14):
        img = cap()
        if img is None or not has_x(img, INF_X_ROI):
            log("목록 화면이 아님 -> 중단")
            status = "abort"
            break
        if not safe_wave_ok(img):
            status = "abort"
            break
        lv = lvdigits.read_levels(img)
        free = inf_free_refresh(img)
        log("상대 레벨 %s / 무료 새로고침 %s" % (lv, "있음" if free else "없음"))
        if all(x is None for x in lv):
            os.makedirs(SHOTS, exist_ok=True)
            cv2.imwrite(os.path.join(SHOTS, "inf_unreadable.png"), img)
            log("레벨을 하나도 못 읽음 -> 중단 (shots\\inf_unreadable.png 저장)")
            status = "abort"
            break
        idx = None
        for i, x in enumerate(lv):
            if x is not None and x <= MY_LEVEL:
                idx = i
                break
        if idx is None:
            if free and refreshes < 5:
                refreshes += 1
                log("싸울 만한 상대 없음 -> 무료 새로고침 (%d)" % refreshes)
                tap(INF_REFRESH, 1.5)
                continue
            idx = 0
            log("무료 새로고침 없음 -> 맨 위 상대와 전투")
        else:
            log("%d번째 상대(Lv.%s)와 전투" % (idx + 1, lv[idx]))
        tap((622, INF_BTN_Y[idx]), 0.5)
        r = _inf_battle()
        if r == "ok":
            fought += 1
            refreshes = 0
            log("전투 완료 (%d회)" % fought)
            continue
        status = r
        break
    log("무한랭킹전 종료: 전투 %d회, 상태 %s" % (fought, status))
    _inf_close()
    return status


# ---------------------------------------------------------------- 상점 광고
def ad_active(img, key):
    """광고 버튼이 갈색(활성)이면 True, 회색이면 False"""
    x1, y1, x2, y2 = AD_ROI[key]
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    return float(np.median(hsv[..., 1])) >= 60


def do_ads(go):
    """명예코인/보석 광고 전부 받기. 하루가 지나 회색으로 굳은 상태면 게임속도 광고를 먼저 눌러 풀어줌.
    반환: True(수행함) / False(아직 못 함, 나중에 재시도)"""
    close_panels()
    if not safe_wave_ok():
        return False
    tap(TAB_SHOP, 1.2)
    tap(AD_GEM_TAB, 1.0)
    img = cap()
    if img is None:
        return False
    st = dict((k, ad_active(img, k)) for k in AD_BTN)
    log("광고 버튼 활성: 게임속도 %s / 명예코인 %s / 보석 %s" % (st["speed"], st["coin"], st["gem"]))
    if not go:
        tap(TAB_BATTLE, 1.0)
        return True
    pressed = False
    if not st["coin"] and not st["gem"]:
        if st["speed"]:
            log("코인/보석이 회색 -> 게임속도 광고를 눌러 갱신")
            tap(AD_BTN["speed"], 1.5)
            pressed = True
        else:
            log("전부 회색(게임속도 쿨타임 중) -> 나중에 재시도")
            tap(TAB_BATTLE, 1.0)
            return False
    got = 0
    for key in ("coin", "gem"):
        for _ in range(AD_MAX[key]):
            img = cap()
            if img is None or not ad_active(img, key):
                break
            tap(AD_BTN[key], 1.2)
            got += 1
            log("%s 광고 보상 %d회째" % (key, got))
    tap(TAB_BATTLE, 1.0)
    return pressed or got > 0


# ---------------------------------------------------------------- 메인 연동
def game_day():
    return (datetime.datetime.now() - datetime.timedelta(hours=9, minutes=10)).strftime("%Y-%m-%d")     # patch125: 9시 10분부터 새 날


INF_MANUAL_FILE = r"C:\macro\inf_manual.txt"


def inf_due(st):
    """다음 무한랭킹전 시각. 메인이 저장한 inf_next 와, 패널/명령으로 직접 돌린 시각 + 주기 중 늦은 쪽"""
    t = st.get("inf_next", 0)
    try:
        with open(INF_MANUAL_FILE, encoding="utf-8") as f:
            t = max(t, float(f.read().strip()) + INF_INTERVAL)
    except Exception:
        pass
    return t


GUILD_TASKS = (("g_post", "guild_post"), ("g_raid", "raid_shop"), ("g_arch", "archery"))   # (오늘 완료 표시 키, 패널 옵션 키)


def guild_pending(d):
    """오늘 아직 안 한 길드 작업 (옵션이 켜져 있고 재시도 대기 시간이 지난 것)"""
    if time.time() < d.get("guild_next", 0):
        return None
    for key, opt in GUILD_TASKS:
        if not d.get(key) and (opt in ("guild_post", "raid_shop") or setting(opt, False)):     # 출석/레이드 상점은 항상 켜짐, 양궁은 기본 꺼짐
            return key
    return None


FRIEND_DOT_EVERY = 3600     # patch146/147: 친구 아이콘 빨간 점 확인 간격(초) - 1시간


def friend_prereset(st):
    """patch147: 초기화(9시) 직전 08:30~08:59 에 하루 한 번 창을 열어 남은 선물 받기 (9시가 넘으면 의미 없음)"""
    n = datetime.datetime.now()
    if not (n.hour == 8 and n.minute >= 30):
        return False
    return st.get("friend_pre") != n.strftime("%Y-%m-%d")


def friend_due(st, d):
    """하루 한 번 모두 보내기 / 1시간마다 빨간 점 확인 (patch154: 패널 옵션 없이 항상)"""
    now = time.time()
    if not d.get("friend_send") and now >= d.get("friend_next", 0):
        return True
    if friend_prereset(st):
        return True
    return now >= st.get("friend_dot_next", 0)


def due(st):
    """지금 일일 작업을 시도할 때인지 (화면 캡처 없이 빠르게 판단)"""
    if time.time() < st.get("daily_next", 0):
        return False
    d = st.get("daily", {})
    if d.get("date") != game_day():
        return True
    if time.time() >= st.get("dg_next", 0):     # patch101: 던전 1시간 주기
        return True
    if not d.get("ranking"):
        return True
    if not d.get("ads") and time.time() >= d.get("ads_next", 0):
        return True
    if time.time() - d.get("quest_ts", 0) > QUEST_COOLDOWN:
        return True
    if guild_pending(d):
        return True
    if friend_due(st, d):                       # patch146
        return True
    return time.time() >= inf_due(st)


def run_daily(st):
    """main.py에서 호출. 한 번 호출에 한 작업만 실행하고 True 반환(상태 변경 시 저장 필요)."""
    d = st.setdefault("daily", {})
    today = game_day()
    if d.get("date") != today:
        d.clear()
        d["date"] = today
    try:
        img = cap()
        if img is None or not safe_wave_ok(img):
            return False
        if time.time() >= st.get("dg_next", 0):          # patch101: 1시간마다 던전 소탕
            import dungeon
            log("던전 소탕 시작 (40분 주기)")     # patch123
            ok = dungeon.run(True, d)
            st["dg_next"] = time.time() + (dungeon.INTERVAL if ok else dungeon.RETRY)
            if ok:
                d["dungeon"] = True
            else:
                log("던전 소탕 실패 -> %d분 뒤 재시도" % (dungeon.RETRY // 60))
            return True
        if not d.get("ranking") and time.time() >= d.get("ranking_next", 0):
            log("일일 랭킹전 시작")
            d["ranking_tries"] = d.get("ranking_tries", 0) + 1
            if do_ranking(True) or d["ranking_tries"] >= 3:
                d["ranking"] = True
            else:
                log("일일 랭킹전 참여 못 함 -> 10분 뒤 재시도 (%d/3)" % d["ranking_tries"])
                d["ranking_next"] = time.time() + 600
            return True
        if not d.get("ads") and time.time() >= d.get("ads_next", 0):
            log("상점 광고 시작")
            d["ads_tries"] = d.get("ads_tries", 0) + 1
            if do_ads(True) or d["ads_tries"] >= 6:
                d["ads"] = True
            else:
                d["ads_next"] = time.time() + 600
            return True
        if time.time() - d.get("quest_ts", 0) > QUEST_COOLDOWN:
            d["quest_ts"] = time.time()
            if do_quest(True):
                log("퀘스트 보상 수령")
            return True
        gk = guild_pending(d)
        if gk:
            log("길드 작업 시작:", gk)
            import guild
            d["tries_" + gk] = d.get("tries_" + gk, 0) + 1
            if guild.run_task(gk) or d["tries_" + gk] >= 4:
                d[gk] = True
            else:
                d["guild_next"] = time.time() + 600
            return True
        if (not d.get("spirit") and time.time() >= d.get("spirit_next", 0)
                and setting("fairy", True)):                 # patch164: 정령의 고원 (patch181: 패널의 '정령의 고원' 체크와 연결)
            import spirit
            spirit.GO = True
            log("정령의 고원 시작")
            d["sp_tries"] = d.get("sp_tries", 0) + 1
            ok = False
            try:
                ok = spirit.run(d)
            except Exception as e:
                log("정령의 고원 오류: %r" % (e,))
                close_panels()
            if ok or d["sp_tries"] >= 3:
                d["spirit"] = True
            else:
                d["spirit_next"] = time.time() + 600
            return True
        if friend_due(st, d):                                # patch146: 친구 선물
            import friend
            st["friend_dot_next"] = time.time() + FRIEND_DOT_EVERY
            want_send = not d.get("friend_send") and time.time() >= d.get("friend_next", 0)
            pre = friend_prereset(st)
            if pre:
                st["friend_pre"] = datetime.datetime.now().strftime("%Y-%m-%d")
                log("초기화 전 친구 선물 확인")
            r = friend.run(send=want_send, force=pre)
            if want_send:
                if r.get("sent"):
                    d["friend_send"] = True
                    log("친구 선물 보내기 완료")
                else:
                    d["friend_tries"] = d.get("friend_tries", 0) + 1
                    if d["friend_tries"] >= 4:
                        d["friend_send"] = True
                    else:
                        d["friend_next"] = time.time() + 600
            if r.get("got"):
                log("친구 선물 받기")
            if r.get("opened"):
                return True
        if time.time() >= inf_due(st):
            log("무한랭킹전 시작")
            r = do_infinite(True)
            try:
                import inf2
                inf2.close_if_open()
            except Exception as e:
                log("무한랭킹전 화면 닫기 오류: %r" % (e,))
            st["inf_next"] = time.time() + (INF_INTERVAL if r in ("ok", "empty") else INF_RETRY)
            return True
    except Exception as e:
        log("오류:", e)
        close_panels()
    return False


if __name__ == "__main__":
    go = "go" in sys.argv
    what = [a for a in sys.argv[1:] if a in ("dungeon", "ranking", "quest", "infinite", "ads")]
    if not what:
        what = ["dungeon", "ranking", "quest"]
    log("모드:", "실행" if go else "판별만", what, "상한 웨이브", MAX_WAVE)
    if "dungeon" in what:
        log("던전 결과:", do_dungeon(go))
    if "ranking" in what:
        log("랭킹전 결과:", do_ranking(go))
    if "quest" in what:
        log("퀘스트 결과:", do_quest(go, force=True))
    if "infinite" in what:
        r_inf = do_infinite(go)
        log("무한랭킹전 결과:", r_inf)
        if go and r_inf in ("ok", "empty"):
            try:
                with open(INF_MANUAL_FILE, "w", encoding="utf-8") as f:
                    f.write(str(time.time()))
                log("직접 실행 기록 -> 다음 자동 실행은 %d분 뒤" % (INF_INTERVAL // 60))
            except Exception as e:
                log("직접 실행 기록 실패:", e)
    if "ads" in what:
        log("광고 결과:", do_ads(go))