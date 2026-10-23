"""guild.py - 길드 일일 작업 (출석 / 우체국 선물 5회 / 길드레이드 상점 뽑기)
실행:  py guild.py look          지금 화면이 어떤 화면인지 판별만 (아무것도 안 누름)
       py guild.py post go       길드 출석 + 우체국 선물
       py guild.py raid go       길드레이드 상점 뽑기 (티켓 + 광고)
       py guild.py arch go       놀이터 양궁 게임 (하루 1번, 실험 기능)
좌표/색 기준은 720x1280 화면 캡처. 실패하면 shots\\guild_*.png 로 화면을 저장합니다.
"""
import sys, os, time
import cv2, numpy as np
import daily

TPL = r"C:\macro\tpl"
_sleep = getattr(sys.modules.get("speed"), "_real_sleep", time.sleep)   # speed.py 의 대기 단축을 받지 않게

GUILD_ICON = (597, 220)                     # 우상단 길드 깃발 (patch213: 10-21 업데이트, 예전 590, 268 -> 지금은 펫 아이콘 자리)
GX = (683, 290)                             # 길드 창 X
GX_ROI = (655, 265, 712, 315)
TAB_Q = (271, 1247)                         # 퀘스트 탭
TAB_B = (620, 1247)                         # 건물 탭
ROW_ATTEND = (620, 477)                     # 퀘스트 탭 첫 줄: 출석 게시판 [출석]
ROW_RAID = (620, 660)                       # 퀘스트 탭: 길드레이드 [입장] (patch163: 길드전 줄 추가로 750 -> 660, 실제로는 글자로 찾음)
RAID_SHOP = (650, 393)                      # 길드레이드 화면 우상단 [상점]
BLD_POST = (360, 475)                       # 건물 탭 첫 줄: 길드 우체국
BLD_PLAY = (360, 653)                       # 건물 탭 세 번째 줄: 놀이터
BACK = (48, 393)                            # 좌상단 빨간 뒤로가기 화살표
DLG_OK = (360, 484)                         # 알림 창 [확인]
DLG_ROI = (290, 462, 430, 505)
POST_BTN = (638, 470)                       # 우체국 맨 윗줄 [선물]
POST_BTN_ROI = (600, 452, 680, 488)
POST_MAX = 5
SHOP_TICKET = (620, 485)                    # 레이드 상점 1번 줄 (티켓)
SHOP_TICKET_ROI = (560, 462, 680, 508)
SHOP_AD = (620, 773)                        # 레이드 상점 4번 줄 (광고)
SHOP_AD_ROI = (560, 750, 680, 796)
TITLE_ROI = (0, 340, 400, 450)
SAT_ACTIVE = 60                             # 버튼 채도가 이보다 높으면 활성(갈색), 낮으면 회색


class Blocked(Exception):
    """성 함락 / 환생결과 팝업, 캡처 실패 등으로 작업을 멈춰야 할 때"""


def log(*a):
    print(time.strftime("[%H:%M:%S] guild:"), *a, flush=True)


def shot(name, img=None):
    try:
        os.makedirs(daily.SHOTS, exist_ok=True)
        if img is None:
            img = daily.cap()
        cv2.imwrite(os.path.join(daily.SHOTS, name + ".png"), img)
        log("화면 저장: shots\\%s.png" % name)
    except Exception as e:
        log("화면 저장 실패:", e)


def grab():
    img = daily.cap()
    if img is None:
        raise Blocked("화면 캡처 실패")
    if daily.blocked(img):
        raise Blocked("성 함락/환생결과 팝업")
    return img


def tap(pt, wait=0.9):
    daily.adb("shell", "input", "tap", str(pt[0]), str(pt[1]))
    _sleep(wait)


def sat(img, roi):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    return float(np.median(hsv[..., 1]))


def green(img, roi):
    return daily.ratio(img, roi, "green")


def red(img, roi):
    return daily.ratio(img, roi, "red")


def guild_open(img):
    return red(img, GX_ROI) >= 0.3


def title_score(img, name):
    t = cv2.imread(os.path.join(TPL, name))
    if t is None:
        return 0.0
    x1, y1, x2, y2 = TITLE_ROI
    r = cv2.matchTemplate(img[y1:y2, x1:x2], t, cv2.TM_CCOEFF_NORMED)
    return float(r.max())


def dimmed(img):
    """뽑기 결과 팝업이 떠서 화면이 어두워진 상태"""
    return float(cv2.cvtColor(img[400:760, 100:620], cv2.COLOR_BGR2HSV)[..., 2].mean()) < 40


def close_all_windows():
    try:
        import closer
        n = closer.close_all()
        log("열린 창 %s개 닫음" % n)
    except ImportError:
        pass
    # patch138: 길드 창은 X 를 눌러도 한 단계(레이드 상점 -> 레이드 -> 길드)씩만 닫혀서 X 가 같은 자리에 남음
    #           closer 는 이걸 '안 닫힘'으로 보고 멈추므로, 길드 창이 사라질 때까지 X 를 더 누름
    for i in range(6):
        img = daily.cap()
        if img is None or not guild_open(img):
            if i:
                log("길드 창 닫힘 (X %d번 더 누름)" % i)
            return
        tap(GX, 1.0)
    shot("guild_close_fail")
    log("길드 창이 안 닫힘")


def open_guild():
    img = grab()
    if guild_open(img):
        return True
    daily.close_panels()
    daily.hud_ensure()
    tap(GUILD_ICON, 1.4)
    for _ in range(4):
        img = grab()
        if guild_open(img):
            return True
        _sleep(0.6)
    shot("guild_open_fail")
    log("길드 창이 안 열림")
    return False


def wait_dim_clear():
    """뽑기 결과 연출이 끝나길 기다림. 3초가 지나도 어두우면 빈 곳을 한 번 눌러 닫음"""
    _sleep(0.8)
    t0 = time.time()
    tapped = False
    while time.time() - t0 < 6:
        img = grab()
        if not dimmed(img):
            return True
        if not tapped and time.time() - t0 > 3:
            tap((360, 1150), 0.8)
            tapped = True
        _sleep(0.4)
    return False


def do_attend():
    tap(TAB_Q, 1.0)
    tap(ROW_ATTEND, 1.0)
    for i in range(2):
        img = grab()
        if green(img, DLG_ROI) >= 0.4:
            tap(DLG_OK, 0.9)
            log("출석 완료")
            return "done"
        _sleep(1.0)
    shot("guild_attend_nodlg")
    log("출석 알림창이 안 뜸 (이미 출석했거나 버튼 위치가 다름)")
    return "none"


def do_post():
    tap(TAB_B, 1.0)
    tap(BLD_POST, 1.3)
    img = grab()
    if title_score(img, "g_post_title.png") < 0.85:
        shot("guild_post_nav")
        log("길드 우체국 화면이 아님")
        return False
    sent = 0
    for _ in range(POST_MAX + 1):
        img = grab()
        if sat(img, POST_BTN_ROI) < SAT_ACTIVE:
            break                                   # 맨 윗줄이 회색 = 더 보낼 곳이 없음 (5회 소진)
        tap(POST_BTN, 0.9)
        ok = False
        for _k in range(2):
            img = grab()
            if green(img, DLG_ROI) >= 0.4:
                ok = True
                break
            _sleep(0.8)
        if not ok:
            shot("guild_post_nodlg")
            log("선물 확인창이 안 뜸 -> 중단")
            break
        tap(DLG_OK, 0.9)
        sent += 1
    log("우체국 선물 %d회 보냄" % sent)
    tap(BACK, 1.0)
    return True


def _pull(btn, roi, label, limit):
    n = 0
    for _ in range(limit):
        img = grab()
        if sat(img, roi) < SAT_ACTIVE:
            break
        tap(btn, 0.4)
        n += 1
        log("%s 뽑기 %d회째" % (label, n))
        if not wait_dim_clear():
            log("뽑기 결과 팝업이 안 닫힘 -> 중단")
            shot("guild_raid_dim")
            break
    return n


def _raid_rows():
    """patch163: 퀘스트 탭에서 '길드레이드' 줄 [입장] 위치 후보. 10-18 업데이트로 '길드전' 줄이 생겨 한 칸 위(660)로 이동
    글자(OCR)로 찾은 줄이 먼저, 그다음 660(새 배치), 750(예전 배치)"""
    ys = []
    try:
        import ocrx
        for t, x, y, w, h in (ocrx.words(grab()) or []):
            if "레이드" in t and x < 420 and 420 < y < 1150:
                ys.append(int(y))
                break
    except Blocked:
        raise
    except Exception as e:
        log("글자 인식 실패:", repr(e))
    for y in (660, 750):
        if all(abs(y - v) > 30 for v in ys):
            ys.append(y)
    return ys


def do_raid():
    tap(TAB_Q, 1.0)
    img = None
    for y in _raid_rows():
        tap((ROW_RAID[0], y), 1.6)
        tap(RAID_SHOP, 1.6)
        img = grab()
        if title_score(img, "g_shop_title.png") >= 0.85:
            break
        log("길드레이드 줄 y=%d 로 상점이 안 열림" % y)
        if title_score(img, "g_shop_title.png") < 0.5:
            tap(BACK, 1.0)                                  # 다른 화면이 열렸으면 한 단계 뒤로
            tap(TAB_Q, 1.0)
    if img is None or title_score(img, "g_shop_title.png") < 0.85:
        shot("guild_raid_nav")
        log("길드레이드 상점 화면이 아님")
        return False
    t = _pull(SHOP_TICKET, SHOP_TICKET_ROI, "티켓", 12)
    a = _pull(SHOP_AD, SHOP_AD_ROI, "광고", 4)
    log("레이드 상점: 티켓 %d회 / 광고 %d회" % (t, a))
    shot("guild_raid_after")
    return True


def do_archery():
    import arch
    tap(TAB_B, 1.0)
    tap(BLD_PLAY, 1.4)
    img = grab()
    if arch.title_score(img) < 0.85:
        shot("guild_arch_nav")
        log("양궁 게임 화면이 아님")
        return False
    try:                                              # patch115: 새 방식 먼저
        import arch2
        r = arch2.run(say=log)
    except Exception as e:
        log("arch2 오류:", repr(e))
        r = "nocam"
    if r == "nocam":
        log("새 방식 실패 -> 예전 방식(arch.py)으로")
        r = arch.run(say=log)
    log("양궁 결과:", r)
    return r in ("done", "already")


def task_post():
    r = do_attend()
    ok = do_post()
    return ok


TASKS = {"g_post": task_post, "g_raid": do_raid, "g_arch": do_archery}


def run_task(key):
    """daily.run_daily 에서 호출. 성공(또는 할 게 없음) True / 나중에 재시도 False"""
    ok = False
    try:
        if not open_guild():
            return False
        ok = bool(TASKS[key]())
    except Blocked as e:
        log("중단:", e)
        return False
    except Exception as e:
        log("오류:", repr(e))
        ok = False
    try:
        close_all_windows()
    except Exception as e:
        log("창 닫기 오류:", repr(e))
    return ok


def look():
    img = daily.cap()
    log("길드 창 열림(X 빨강 %.2f): %s" % (red(img, GX_ROI), guild_open(img)))
    log("우체국 제목 %.2f / 레이드 상점 제목 %.2f" % (title_score(img, "g_post_title.png"), title_score(img, "g_shop_title.png")))
    log("우체국 윗줄 선물 버튼 채도 %.0f / 상점 티켓 %.0f / 상점 광고 %.0f (60 이상이면 활성)" %
        (sat(img, POST_BTN_ROI), sat(img, SHOP_TICKET_ROI), sat(img, SHOP_AD_ROI)))
    log("알림창 확인 버튼 초록 %.2f / 어두워짐 %s" % (green(img, DLG_ROI), dimmed(img)))


if __name__ == "__main__":
    go = "go" in sys.argv
    what = [a for a in sys.argv[1:] if a in ("post", "raid", "arch", "look")]
    if not what or what == ["look"]:
        look()
    else:
        if not go:
            log("시험 모드: 실제로 누르려면 맨 끝에 go 를 붙이세요 (예: py guild.py post go)")
            look()
        else:
            for w in what:
                log("%s 결과: %s" % (w, run_task({"post": "g_post", "raid": "g_raid", "arch": "g_arch"}[w])))
