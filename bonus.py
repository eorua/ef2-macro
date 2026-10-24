"""bonus.py - patch235: 주말 '환생 훈장 +50%' 이벤트 (하루 5회) 판독

전투 화면 좌상단 천사 아이콘 아래 '+50%' / 'N/5' 배지와,
성 함락 팝업 훈장 줄 오른쪽의 파란 '+보너스' 글자, 빨간 '환생 (훈장 x2)' 버튼 위치를 읽는다.

  py bonus.py            지금 화면에서 배지 읽기 (누르지 않음)
  py bonus.py file 경로   저장된 캡처에서 읽기
"""
import os, sys, time
import cv2, numpy as np

BASE = r"C:\macro"
TPL = os.environ.get("BONUS_TPL") or os.path.join(BASE, "tpl", "bonus")
SHOTS = os.path.join(BASE, "shots")

ROI_BADGE = (35, 226, 110, 272)        # x1, y1, x2, y2 (720x1280 기준)
ROI_PLUS = (400, 425, 690, 490)        # 성 함락 팝업 훈장 줄 오른쪽 파란 '+514b'
SZ = (12, 16)                          # 글자 비교 크기 (가로, 세로)
SLASH_DX = 8                           # '5' 글자 왼쪽 끝에서 '/' 왼쪽 끝까지 (10-24 캡처 4장에서 일정)


def _mask(img, roi):
    """배지 글자(하늘색 H≈100, S≈150) 마스크. 어두운 창이 덮여 밝기가 줄어도 읽히도록 밝기는 상대값"""
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    m = (h >= 95) & (h <= 106) & (s >= 115) & (s <= 190) & (v >= 60)
    if m.sum() < 30:
        return np.zeros_like(m, np.uint8)
    vmax = np.percentile(v[m], 90)
    return (m & (v >= 0.6 * vmax)).astype(np.uint8)


def _bands(m):
    """세로로 글자 줄 나누기 -> [(y1, y2)]"""
    rows = m.sum(1) > 0
    out, s = [], None
    for i, r in enumerate(list(rows) + [False]):
        if r and s is None:
            s = i
        if not r and s is not None:
            if i - s >= 6:
                out.append((s, i))
            s = None
    return out


def _glyphs(line):
    """한 줄을 연결 요소로 나눠 왼쪽부터 (x, 마스크) 목록 (작은 점 제외)"""
    n, lab, st, _ = cv2.connectedComponentsWithStats(line, 8)
    gs = []
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        if a < 8 or hh < 6:
            continue
        g = (lab[y:y + hh, x:x + w] == i).astype(np.uint8)
        gs.append((int(x), g))
    gs.sort(key=lambda t: t[0])
    return gs


def _crop(m):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _norm(g):
    return cv2.resize(g.astype(np.float32), SZ, interpolation=cv2.INTER_AREA)


def _sim(a, b):
    a, b = _norm(a), _norm(b)
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float((a * b).sum()) / den if den > 0 else 0.0


_T = {}


def tpls():
    if not _T:
        for f in os.listdir(TPL) if os.path.isdir(TPL) else []:
            if f.endswith(".png"):
                t = cv2.imread(os.path.join(TPL, f), cv2.IMREAD_GRAYSCALE)
                if t is not None:
                    _T[f[:-4]] = (t > 127).astype(np.uint8)
    return _T


def read_badge(img):
    """-> (n, info). n = 남은 횟수(0~5) 또는 None(배지 없음/못 읽음).
    info["guess3"] = True 이면 손으로 그린 3 과 닮아서 3 으로 추정 (메인이 환생 기록과 맞을 때만 인정)"""
    info = {"badge": False, "sims": {}, "nonzero_unknown": False}
    if img is None:
        return None, info
    T = tpls()
    m = _mask(img, ROI_BADGE)
    b = [t for t in _bands(m) if 8 <= t[1] - t[0] <= 18]     # 글자 높이의 줄만 (천사 그림 조각 제외)
    if len(b) < 2:
        info["why"] = "줄 %d개" % len(b)
        return None, info
    b = b[-2:]
    top = m[b[0][0]:b[0][1]]
    bot = m[b[1][0]:b[1][1]]
    # 1) 윗줄 '+50%' 확인 (이벤트 배지가 맞는지)
    tg = _glyphs(top)
    if len(tg) < 3 or "plus" not in T:
        info["why"] = "윗줄 글자 %d개" % len(tg)
        return None, info
    sp = _sim(tg[0][1], T["plus"])
    info["sims"]["plus"] = round(sp, 3)
    if sp < 0.9:
        info["why"] = "'+' 모양 아님"
        return None, info
    # 2) 아랫줄 'N/5' : 맨 오른쪽 글자가 5, 그 왼쪽 8칸부터 '/', 그보다 왼쪽이 남은 횟수 숫자
    #    (숫자 2 는 '/' 와 대각선으로 붙어 한 덩어리가 되므로 연결 요소 대신 고정 간격으로 자름)
    g = _glyphs(bot)
    if not g:
        info["why"] = "아랫줄 글자 없음"
        return None, info
    x5, g5 = g[-1]
    sl0 = x5 - SLASH_DX
    if sl0 < 4:
        info["why"] = "아랫줄 위치 이상"
        return None, info
    slm = _crop(bot[:, sl0:x5 - 1])
    dgm = _crop(bot[:, :sl0])
    if slm is None or dgm is None:
        info["why"] = "'/' 또는 숫자 없음"
        return None, info
    s5 = _sim(g5, T["d5"])
    ssl = _sim(slm, T["slash"])
    info["sims"].update(five=round(s5, 3), slash=round(ssl, 3))
    if s5 < 0.93 or ssl < 0.9 or not (3 <= dgm.shape[1] <= 11 and 10 <= dgm.shape[0] <= 14):
        info["why"] = "'/5' 모양 아님"
        return None, info
    info["badge"] = True
    g = [(0, dgm)]
    # 3) 첫 글자 (남은 횟수)
    sc = sorted(((_sim(g[0][1], t), k) for k, t in T.items() if k.startswith("d")), reverse=True)
    info["sims"]["digit"] = [(k, round(s, 3)) for s, k in sc[:3]]
    best_s, best_k = sc[0]
    second = sc[1][0] if len(sc) > 1 else 0.0
    if best_s >= 0.95 and best_s - second >= 0.04:
        return int(best_k[1:]), info
    s0 = _sim(g[0][1], T["d0"])
    s3 = _sim(g[0][1], T["s3"]) if "s3" in T else 0.0
    info["sims"]["s3"] = round(s3, 3)
    info["glyph"] = g[0][1]
    if "d3" not in T and s3 >= 0.85 and s0 < 0.8 and s3 >= s0 + 0.1 and s3 >= best_s:
        info["guess3"] = True                # 손으로 그린 3 과 닮음 (진짜 3 그림은 아직 없음)
        return 3, info
    if s0 < 0.8 and best_s < 0.95:
        info["nonzero_unknown"] = True       # 아는 숫자는 아니지만 0 과는 다름 -> 판독 실패로 처리
    try:
        os.makedirs(os.path.join(SHOTS, "bonus"), exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, "bonus", "unknown_%d.png" % int(time.time())), g[0][1] * 255)
    except Exception:
        pass
    info["why"] = "첫 글자 판독 불확실"
    return None, info


def learn_digit(glyph, d):
    """처음 보는 숫자 그림을 tpl\\bonus\\dN.png 로 저장 (메인이 환생 기록과 맞을 때만 호출)"""
    try:
        p = os.path.join(TPL, "d%d.png" % d)
        if os.path.exists(p):
            return False
        cv2.imwrite(p, glyph * 255)
        _T.clear()
        return True
    except Exception:
        return False


def plus_text(img):
    """성 함락 팝업 훈장 줄 오른쪽 파란 '+보너스' 글자가 있는지 (이벤트 보너스가 이번 환생에 붙는다는 뜻)"""
    if img is None:
        return False, 0
    x1, y1, x2, y2 = ROI_PLUS
    h = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = ((h[..., 0] >= 95) & (h[..., 0] <= 110) & (h[..., 1] >= 90) & (h[..., 2] >= 170)).astype(np.uint8)
    n = int(m.sum())
    if n < 120:
        return False, n
    ys, xs = np.nonzero(m)
    w, hh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    return (30 <= w <= 110 and 8 <= hh <= 24), n


def red_button(img):
    """성 함락 팝업의 빨간 '환생 (훈장 x2/x3)' 💎500 버튼 중심. 없으면 None"""
    if img is None:
        return None
    H, W = img.shape[:2]
    x1, y1, x2, y2 = int(0.25 * W), int(0.40 * H), int(0.80 * W), int(0.62 * H)
    h = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = (((h[..., 0] <= 8) | (h[..., 0] >= 170)) & (h[..., 1] >= 120) & (h[..., 2] >= 90)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stt, _ = cv2.connectedComponentsWithStats(m, 8)
    cands = []
    for i in range(1, n):
        x, y, w, hh, a = stt[i]
        if 200 <= w <= 320 and 55 <= hh <= 100 and a >= 0.7 * w * hh:
            cands.append((int(x1 + x + w // 2), int(y1 + y + hh // 2)))
    return cands[0] if len(cands) == 1 else None


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["file"]:
        img = cv2.imread(a[1])
    else:
        import preset
        img = preset.capture()
    n, info = read_badge(img)
    print("배지:", n, info)
    print("팝업 +보너스:", plus_text(img), " 빨간 버튼:", red_button(img))
