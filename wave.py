import subprocess, os, time, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
FONTS = [r"C:\Windows\Fonts\calibrib.ttf"]
WAVE_ROI = (0.40, 0.030, 0.62, 0.060)     # 'Wave NNNN' 위치 (비율)
_T = None


def capture():
    png = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout
    if not png:
        return None
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def _norm(c):
    ys, xs = np.where(c > 0)
    c = c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = c.shape
    nw = max(1, round(w * 36 / h))
    c = cv2.resize(c, (nw, 36), interpolation=cv2.INTER_AREA)
    can = np.zeros((36, 40), np.uint8)
    nw = min(nw, 40)
    x0 = (40 - nw) // 2
    can[:, x0:x0 + nw] = c[:, :nw]
    return can.astype(np.float32) / 255


def _templates():
    global _T
    if _T is None:
        font = next(f for f in FONTS if os.path.exists(f))
        _T = {}
        for d in "0123456789":
            img = Image.new("L", (120, 140), 0)
            ImageDraw.Draw(img).text((20, 10), d, fill=255, font=ImageFont.truetype(font, 100))
            _T[d] = _norm((np.array(img) > 128).astype(np.uint8) * 255)
    return _T


def _score(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9))


_G = None


def _game_templates():
    """tpl 폴더의 wave_digits.png (게임 글꼴로 만든 숫자 그림, 숫자마다 평균 1 + 대표 12) 을 읽음. 없으면 False"""
    global _G
    if _G is None:
        _G = False
        try:
            m = cv2.imread(os.path.join(BASE, "tpl", "wave_digits.png"), cv2.IMREAD_GRAYSCALE)
            if m is not None and m.shape == (9 * 36, 13 * 40):
                G = {}
                for r, d in enumerate("023456789"):
                    tiles = [m[r * 36:(r + 1) * 36, k * 40:(k + 1) * 40].astype(np.float32) / 255 for k in range(13)]
                    G[d] = (tiles[0], tiles[1:])
                _G = G
        except Exception:
            _G = False
    return _G


def _classify(c, T):
    """숫자 조각 c 의 [(점수, 숫자)] (높은 순). 게임 글꼴 그림이 있으면 그것으로, 없으면 예전 글꼴 그림으로"""
    G = _game_templates()
    if not G:
        return sorted(((_score(c, T[d]), d) for d in T), reverse=True)
    out = [(0.5 * _score(c, mean) + 0.5 * max(_score(c, e) for e in ex), d) for d, (mean, ex) in G.items()]
    return sorted(out, reverse=True)


def read_wave(img, exact=False):
    """'Wave NNNN'에서 마지막 두 자리를 버린 백 단위 값 반환 (5184 -> 5100). 실패하면 None"""
    if img is None:
        return None
    H, W = img.shape[:2]
    roi = img[int(WAVE_ROI[1]*H):int(WAVE_ROI[3]*H), int(WAVE_ROI[0]*W):int(WAVE_ROI[2]*W)]
    v = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 2]
    m = (v < 40).astype(np.uint8) * 255                 # 글자 검은 외곽선
    m = cv2.resize(m, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    _, m = cv2.threshold(m, 100, 255, cv2.THRESH_BINARY)
    m = cv2.copyMakeBorder(m, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
    ff = m.copy()
    h, w = ff.shape
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 128)
    holes = np.where(ff == 0, 255, 0).astype(np.uint8)  # 외곽선 안쪽 = 글자 속
    holes = cv2.medianBlur(holes, 7)
    n, lab, st, _ = cv2.connectedComponentsWithStats(holes)
    cs = [(s[0], s[1], s[2], s[3], i) for i, s in enumerate(st)
          if i > 0 and s[4] > 300 and 85 <= s[3] <= 110 and s[2] <= 130]      # 글자 높이인 덩어리만 (patch251: 폭 130 초과 = 어두운 배경 덩어리 제외)
    cs.sort()
    if len(cs) < 5:
        return None
    # 간격이 100 이상 벌어지면 다른 묶음: [W] [숫자들] [+1 같은 표시]
    groups = [[cs[0]]]
    for c in cs[1:]:
        prev = groups[-1][-1]
        if c[0] - (prev[0] + prev[2]) > 50:
            groups.append([c])
        else:
            groups[-1].append(c)
    if len(groups) < 2:
        return None
    digs = groups[1]
    if not 4 <= len(digs) <= 5:
        return None
    T = _templates()
    out = ""
    for x, y, cw, ch, i in digs:
        if cw < 52:                       # '1'은 폭이 확연히 좁음
            out += "1"
            continue
        c = _norm(((lab == i) * 255).astype(np.uint8))
        sc = _classify(c, T)
        if sc[0][0] < 0.5:
            return None
        if _game_templates() and sc[0][0] - sc[1][0] < 0.02:
            return None                  # 두 숫자가 거의 같은 점수면 읽지 않음 (오독보다 미인식이 낫다)
        out += sc[0][1]
    if exact:
        return int(out)
    return int(out[:-2]) * 100 if len(out) > 2 else None


if __name__ == "__main__":
    print("웨이브 읽기 테스트 (중지: Ctrl + C)")
    while True:
        img = capture()
        print("현재 웨이브(백 단위):", None if img is None else read_wave(img))
        time.sleep(1)