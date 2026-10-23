"""dungeon.py - 던전 소탕: 재화 4개 중 가장 적은 재화의 보스를 티켓이 다 떨어질 때까지 소탕 (patch101)
티켓이 0 이 되면 그날 광고(하루 5회, 회당 티켓 3장)를 한 번씩 보고 이어서 소탕.

  py dungeon.py        읽기만: 재화 4개, 티켓, 고를 보스를 출력 (입장/소탕 안 함, 던전 목록은 열었다 닫음)
  py dungeon.py ad     읽기만: 티켓 구매 창을 열어 광고 표시(n/5)를 읽고 닫음 (광고 안 누름)
  py dungeon.py close  구매 창/'최대 횟수 초과' 알림이 떠 있으면 닫기
  py dungeon.py go     실제 소탕 (+ 광고)

안전: 티켓 구매 창의 초록 '💎100' 버튼은 절대 누르지 않음. 창 판별이 애매하면 X 로 닫고 중단.

재화 순서(목록 위 막대): 파랑=킹슬라임, 초록=오크플라워, 빨강=혼토드, 보라=다크허밋
크기 비교: 단위(없음 < a < b < ... < z < aa < ab ...)를 먼저, 같으면 앞 숫자
"""
import os, re, sys, time, subprocess
import cv2
import daily
from daily import log

INTERVAL = 2400                       # 자동 실행 주기 (40분) - 티켓 10분에 1장, 최대 8장 - patch123
_last_buy = [False]                   # patch123: 직전 소탕에서 구매 창(티켓 0)이 떴는지
RETRY = 600                           # 실패 시 10분 뒤
MAX_SWEEP = 8

BOSS = ["킹슬라임", "오크플라워", "혼토드", "다크허밋"]
ENTER = [(632, 866), (632, 958), (632, 1052), (632, 1145)]           # 목록의 '입장' 버튼
CUR_ROI = [(320, 720, 385, 750), (430, 720, 495, 750),
           (540, 720, 604, 750), (648, 720, 716, 750)]                # 재화 숫자 (파랑/초록/빨강/보라)
TICKET_ROI = (458, 766, 512, 794)                                     # '3 / 8'
# 티켓 구매 창 (던전 목록/안쪽 화면의 '구매' 버튼으로 열림)
BUY_BTN = (596, 790)
BUY_X = (631, 561)
BUY_X_ROI = (612, 543, 650, 580)
BUY_GREEN_ROI = (150, 690, 330, 730)       # 💎100 (절대 누르지 않음, 창 판별에만 사용)
AD_BTN = (477, 709)                        # 회색 '광고 (n/5)'
AD_ROI = (380, 690, 580, 730)
AD_CNT_ROI = (498, 694, 545, 724)
AD_MAX = 5
# '오늘 최대 횟수를 초과했습니다.' 알림 (구매 창 위에 뜸; 창 캡처에서 환산한 좌표)
ALERT_X = (631, 308)
ALERT_X_ROI = (612, 290, 650, 326)
ALERT_OK_ROI = (300, 450, 420, 485)
TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TMP = os.path.join(daily.SHOTS, "dg_ocr.png")


def _prep(crop, thr):
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, thr, 255, cv2.THRESH_BINARY_INV)        # 밝은 글자 -> 흰 바탕 검은 글자
    t = cv2.resize(t, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(t, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def _ocr(crop, chars, thr):
    """Tesseract(한 줄, 허용 글자 제한)로 읽음. 없으면 윈도우 OCR. 실패 시 ''"""
    img = _prep(crop, thr)
    if os.path.exists(TESS):
        try:
            cv2.imwrite(TMP, img)
            r = subprocess.run([TESS, TMP, "-", "--psm", "7", "-c", "tessedit_char_whitelist=" + chars],
                               capture_output=True, text=True, timeout=10)
            return r.stdout.strip().replace(" ", "")
        except Exception as e:
            log("Tesseract 오류: %r" % (e,))
    try:
        import ocrx
        ws = ocrx.words(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)) or []
        ws.sort(key=lambda w: w[1])
        return "".join(w[0] for w in ws).replace(" ", "")
    except Exception as e:
        log("윈도우 OCR 오류: %r" % (e,))
        return ""


def parse_amount(t):
    """'4.33e' -> (1, 'e', 4.33) 처럼 비교용 키. 못 읽으면 None"""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([a-z]{0,3})", t or "")
    if not m:
        return None
    suf = m.group(2)
    return (len(suf), suf, float(m.group(1)))


def read_currency_stable(tries=6):
    """patch184: 칸마다 따로, 같은 글자가 두 번 나오면 인정 (최대 6번 읽음)
    예전: 4칸 전체가 연속 두 번 똑같아야 해서, 한 칸만 한 번 틀려도(4.00e, 4.5. 등) 소탕 실패가 잦았음 (10-18 하루 7번)"""
    seen = [{} for _ in CUR_ROI]
    img = None
    for n in range(tries):
        img = daily.cap()
        if img is None:
            return None, None
        for j, (t, k) in enumerate(read_currency(img)):
            if k is not None:
                seen[j][t] = seen[j].get(t, 0) + 1
        pick = [max(c, key=c.get) if c and max(c.values()) >= 2 else None for c in seen]
        if all(p is not None for p in pick):
            return [(p, parse_amount(p)) for p in pick], img
        time.sleep(0.6)
    return [((max(c, key=c.get) if c else ""), None) for c in seen], None


def read_currency(img):
    out = []
    for x1, y1, x2, y2 in CUR_ROI:
        t = _ocr(img[y1:y2, x1:x2], "0123456789.abcdefghijklmnopqrstuvwxyz", 120)
        out.append((t, parse_amount(t)))
        try:                                          # patch186: 글꼴 견본
            import glyph
            glyph.save("dgcur", img[y1:y2, x1:x2], t)
        except Exception:
            pass
    return out


def read_tickets(img):
    x1, y1, x2, y2 = TICKET_ROI
    t = _ocr(img[y1:y2, x1:x2], "0123456789/", 150)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", t)
    if m and int(m.group(1)) <= int(m.group(2)) <= 20:
        return int(m.group(1))
    return None


def buy_popup(img):
    """티켓 구매 창이 떠 있는지: 빨간 X + 왼쪽 초록 💎 버튼"""
    return (img is not None and daily.ratio(img, BUY_X_ROI, "red") >= 0.25
            and daily.ratio(img, BUY_GREEN_ROI, "green") >= 0.5)


def limit_alert(img):
    """'오늘 최대 횟수를 초과했습니다' 알림: 위쪽 빨간 X + 가운데 초록 확인"""
    return (img is not None and daily.ratio(img, ALERT_X_ROI, "red") >= 0.25
            and daily.ratio(img, ALERT_OK_ROI, "green") >= 0.5)


def close_alert():
    for _ in range(3):
        img = daily.cap()
        if not limit_alert(img):
            return True
        daily.tap(ALERT_X, 0.8)
    return not limit_alert(daily.cap())


def close_buy():
    close_alert()
    for _ in range(3):
        img = daily.cap()
        if not buy_popup(img):
            return True
        daily.tap(BUY_X, 0.8)
    return not buy_popup(daily.cap())


def read_ad_count(img):
    x1, y1, x2, y2 = AD_CNT_ROI
    t = _ocr(img[y1:y2, x1:x2], "0123456789/()", 150)
    m = re.search(r"(\d)/5", t)
    return int(m.group(1)) if m else None


def watch_ad(press=True):
    """구매 창을 열고 (press 면) 광고 1회. 반환 'ok' / 'max'(오늘 횟수 초과 알림) / None(실패)
    창의 '(n/5)' 표시는 실제 횟수와 맞지 않아(0/5 인데 초과 알림) 참고로 로그만 남김"""
    daily.tap(BUY_BTN, 1.2)
    img = daily.cap()
    if not buy_popup(img):
        log("티켓 구매 창이 안 열림")
        close_buy()
        return None
    n = read_ad_count(img)
    log("광고 버튼 표시 %s/5" % ("?" if n is None else n))
    if not press:
        close_buy()
        return n
    if daily.ratio(img, AD_ROI, "green") > 0.05:         # 광고 버튼 자리가 초록이면 화면이 다름 -> 누르지 않음
        log("광고 버튼 자리가 이상함 -> 누르지 않음")
        close_buy()
        return None
    daily.tap(AD_BTN, 2.5)
    img = daily.cap()
    if limit_alert(img):
        log("'오늘 최대 횟수 초과' 알림 -> 닫음")
        close_buy()
        return "max"
    close_buy()                                          # 창이 남아 있으면 닫음
    return "ok"


def _poll(cond, timeout, step=0.15):
    """patch106: 조건이 맞으면 바로, 아니면 timeout 초까지 다시 확인. 마지막 화면 반환"""
    t0 = time.time()
    img = daily.cap()
    while not (img is not None and cond(img)) and time.time() - t0 < timeout:
        time.sleep(step)
        img = daily.cap()
    return img


def _result_up(img):
    return buy_popup(img) or daily.ratio(img, daily.SWEEP_OK_ROI, "green") >= 0.30


def _sweep_once():
    """소탕 1회: 위에서부터 '소탕' 버튼을 눌러 결과 팝업이 뜨면 확인. 성공 True"""
    for btn in daily.SWEEP_BTNS:
        daily.tap(btn, 0.15)
        img = _poll(_result_up, 1.2)                     # patch106: 결과 창이 뜨면 바로
        if buy_popup(img):                               # 티켓이 없어 구매 창이 뜸 -> 닫고 중단
            log("티켓 구매 창이 뜸 -> 닫음 (티켓 0)")
            close_buy()
            _last_buy[0] = True
            return False
        if img is not None and daily.ratio(img, daily.SWEEP_OK_ROI, "green") >= 0.30:
            daily.tap(daily.SWEEP_OK, 0.15)
            _poll(lambda im: daily.ratio(im, daily.SWEEP_OK_ROI, "green") < 0.30, 1.5)     # 닫히면 바로
            return True
    return False


def run(go, d=None):
    """True = 정상 처리(소탕 0회 포함), False = 실패(다시 시도 필요). d = 오늘의 일일 상태(광고 완료 표시)"""
    if d is None:
        d = {}
    if not d.get("dg_v193"):                 # patch193: 예전 방식으로 하루 끝 처리된 광고를 한 번 되살림
        d["dg_v193"] = True
        if d.get("dg_ads") and d.get("dg_ads_n", 0) < AD_MAX:
            d["dg_ads"] = False
            d["dg_ads_fail"] = 0
    daily.go_battle()
    if not daily.safe_wave_ok():
        return False
    daily.tap(daily.ROW_DUNGEON, 0.3)
    img = _poll(daily.has_x, 3.0, 0.25)                  # patch106: 목록이 보이면 바로
    if img is None or not daily.has_x(img):
        log("던전 목록 화면을 못 찾음 -> 중단")
        daily.close_panels()
        return False
    cur, img2 = read_currency_stable()
    if img2 is None:
        log("재화 숫자가 읽을 때마다 달라짐 -> 소탕 안 함 (%s)" % " / ".join(t for t, _ in (cur or [])))
        daily.close_panels()
        return False
    tk = read_tickets(img2)
    log("던전 재화 " + " / ".join("%s %s" % (BOSS[i], t or "?") for i, (t, _) in enumerate(cur))
        + " | 티켓 %s" % ("?" if tk is None else tk))
    if any(k is None for _, k in cur):
        log("재화를 다 읽지 못함 -> 소탕 안 함")
        daily.close_panels()
        return False
    idx = min(range(4), key=lambda i: cur[i][1])
    log("가장 적은 재화 -> %s 소탕" % BOSS[idx])
    if not go:
        daily.close_panels()
        return True
    daily.tap(ENTER[idx], 1.3)
    done = 0
    ad_fails = 0
    budget = tk if tk is not None else 8                # patch123: 못 읽어도 이만큼은 소탕
    force_zero = False
    for _ in range(40):                     # 소탕 최대 8 + 광고 15장 + 광고 단계
        img = daily.cap()
        if img is None or not daily.safe_wave_ok(img):
            break
        if limit_alert(img) or buy_popup(img):
            close_buy()
            continue
        left = 0 if force_zero else read_tickets(img)
        force_zero = False
        if left == 0:
            if d.get("dg_ads") or d.get("dg_ads_n", 0) >= AD_MAX or ad_fails >= 2:
                break
            r = watch_ad(True)
            if r == "max":
                # patch193: 9시 갱신 직후엔 광고 칸이 전날 상태로 남아 '초과' 알림이 뜨는 일이 있음
                #  -> 5회를 다 보기 전이면 바로 끝내지 않고 다음 주기(40분)에 다시, 3번 연속이면 끝
                d["dg_ads_max"] = d.get("dg_ads_max", 0) + 1
                if d.get("dg_ads_n", 0) >= AD_MAX or d["dg_ads_max"] >= 3:
                    log("오늘 광고 끝 (게임 알림 %d번)" % d["dg_ads_max"])
                    d["dg_ads"] = True
                else:
                    log("'초과' 알림 (%d/3) -> 다음 주기에 다시 시도" % d["dg_ads_max"])
                break
            if r is None:
                ad_fails += 1
                d["dg_ads_fail"] = d.get("dg_ads_fail", 0) + 1
                if d["dg_ads_fail"] >= 3:
                    log("광고를 3번 실패 -> 오늘은 광고 생략")
                    d["dg_ads"] = True
                continue
            after = read_tickets(daily.cap())
            if not after:
                log("광고 후에도 티켓이 늘지 않음")
                ad_fails += 1
                continue
            d["dg_ads_n"] = d.get("dg_ads_n", 0) + 1
            d["dg_ads_max"] = 0
            log("광고 %d/5 -> 티켓 %d" % (d["dg_ads_n"], after))
            budget = done + after
            if d["dg_ads_n"] >= AD_MAX:
                d["dg_ads"] = True
            continue
        if left is None and done >= budget:
            log("티켓 수를 못 읽음, 처음 티켓 %d장을 다 씀 -> 멈춤" % budget)
            break
        _last_buy[0] = False
        if not _sweep_once():
            if _last_buy[0]:                            # 티켓이 떨어짐 -> 광고 단계로
                force_zero = True
                continue
            log("소탕 결과 팝업이 안 뜸 -> 중단")
            break
        done += 1
        log("%s 소탕 %d회" % (BOSS[idx], done))
    daily.close_panels()
    log("던전 소탕 끝: %s %d회" % (BOSS[idx], done))
    return True


if __name__ == "__main__":
    if "close" in sys.argv[1:]:
        log("결과:", close_buy())
        sys.exit()
    if "ad" in sys.argv[1:]:
        log("광고 횟수만 확인 (던전 목록을 열어 둔 상태에서 실행하세요)")
        log("결과:", watch_ad(False))
        sys.exit()
    go = "go" in sys.argv[1:]
    log("모드:", "실행" if go else "읽기만")
    log("결과:", run(go))
