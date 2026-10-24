# -*- coding: utf-8 -*-
"""유물 공방 화면 읽기 (720x1280, RGB 배열 입력)"""
import numpy as np
from hexa_engine import CELLS, N, pix, rot

# 등급별 칸 배경색(RGB). 9·10등급은 처음 만들 때 자동 학습(cfg['colors'])
REF = {0: (19, 12, 10), 1: (77, 83, 86), 2: (50, 94, 53), 3: (43, 68, 108), 4: (114, 82, 162),
       5: (180, 75, 80), 6: (175, 130, 50), 7: (63, 160, 180), 8: (114, 81, 91)}
TOL = 28

TRAY_C = (359, 998)          # 아래 조각 무게중심
TRAY_P = (84.0, 85.0)        # 조각 칸 간격 (가로 열간격, 세로 칸간격)
PREV_C = (575, 997)          # 오른쪽 '다음' 칸
PREV_P = (31.0, 31.5)
ROT_BTN = (144, 997)
ICON_X = [int(118 + 53.7 * i) for i in range(10)]


def set_colors(extra):
    for k, v in (extra or {}).items():
        REF[int(k)] = tuple(v)


def classify(p):
    best, bd = None, 1e9
    for k, v in REF.items():
        d = ((p[0] - v[0]) ** 2 + (p[1] - v[1]) ** 2 + (p[2] - v[2]) ** 2) ** 0.5
        if d < bd:
            best, bd = k, d
    return (best if bd <= TOL else None), bd


def cell_color(im, i):
    x, y = pix(i)
    return im[y - 12:y + 12, x - 40:x - 33].reshape(-1, 3).astype(float).mean(0)


def read_board(im):
    """반환 (board list, 모르는 칸 index 목록)"""
    b, unk = [], []
    for i in range(N):
        k, d = classify(cell_color(im, i))
        if k is None:
            unk.append(i)
            b.append(-1)
        else:
            b.append(k)
    return b, unk


def unlocked(im):
    n = 1
    for i in range(1, 10):
        x = ICON_X[i]
        p = im[268:292, x - 12:x + 12].reshape(-1, 3).astype(int)
        if (p.max(1) - p.min(1)).mean() > 40:
            n = i + 1
        else:
            break
    return n


# --- 조각 모양 후보 (축좌표) ---
def _shapes():
    base = [[(0, 0)], [(0, 0), (1, 0)], [(0, 0), (1, 0), (2, 0)], [(0, 0), (1, 0), (0, 1)],
            [(0, 0), (1, 0), (1, 1)]]
    out = set()
    for s in base:
        for k in range(6):
            o = rot(s, k)
            q0 = min(q for q, r in o)
            r0 = min(r for q, r in o)
            out.add(tuple(sorted((q - q0, r - r0) for q, r in o)))
    return [list(s) for s in out]


SHAPES = _shapes()


def ax_px(q, r, P):
    return q * P[0], (r + q / 2.0) * P[1]


def _bg_frac(im, x, y, h, bg):
    x, y, h = int(round(x)), int(round(y)), int(round(h))
    p = im[y - h:y + h, x - h:x + h].reshape(-1, 3).astype(float)
    if len(p) == 0:
        return 0.0
    d = np.sqrt(((p - np.array(bg)) ** 2).sum(1))
    return float((d > 40).mean())


def read_piece(im, C, P, bg=None, win=None):
    """반환 [((q,r),tier)...] 또는 None. 무게중심 C 기준, 모양 후보와 겹침(IoU)으로 고름"""
    if bg is None:
        bg = (68, 61, 45)
    if win is None:
        wx, wy = int(2.3 * P[0]), int(1.9 * P[1])
        win = (int(C[0]) - wx, int(C[1]) - wy, int(C[0]) + wx, int(C[1]) + wy)
    x0, y0, x1, y1 = win
    sub = im[y0:y1, x0:x1].astype(float)
    obs = np.sqrt(((sub - np.array(bg, float)) ** 2).sum(2)) > 40
    if obs.mean() < 0.02:
        return None
    hs = 0.46 * P[1]
    best = None
    for s in SHAPES:
        pts = [ax_px(q, r, P) for q, r in s]
        mx = sum(x for x, y in pts) / len(pts)
        my = sum(y for x, y in pts) / len(pts)
        cen = [(C[0] + x - mx, C[1] + y - my) for x, y in pts]
        pm = np.zeros_like(obs)
        for x, y in cen:
            a0, a1 = int(round(y - hs)) - y0, int(round(y + hs)) - y0
            b0, b1 = int(round(x - hs)) - x0, int(round(x + hs)) - x0
            pm[max(0, a0):max(0, a1), max(0, b0):max(0, b1)] = True
        inter = (pm & obs).sum()
        uni = (pm | obs).sum()
        iou = inter / max(1, uni)
        if best is None or iou > best[0]:
            best = (iou, s, cen)
    iou, s, cen = best
    if iou < 0.5:
        return None
    res = []
    for (q, r), (x, y) in zip(s, cen):
        x, y = int(round(x)), int(round(y))
        k = tile_tier(im, x, y, P)
        if k is None:
            return None
        res.append(((q, r), k))
    return res


def tile_tier(im, x, y, P):
    """조각 칸 등급: 왼쪽·오른쪽·위 띠 3곳 색으로 투표 (보라 배경의 빛살 무늬 때문에 한 곳만 보면 1·8로 잘못 읽음)"""
    a = int(0.40 * P[1])
    w = max(2, int(0.08 * P[1]))
    hh = max(3, int(0.14 * P[1]))
    strips = [im[y - hh:y + hh, x - a:x - a + w], im[y - hh:y + hh, x + a - w:x + a],
              im[y - a:y - a + w, x - hh:x + hh]]
    votes = {}
    for st in strips:
        p = np.median(st.reshape(-1, 3).astype(float), axis=0)
        k, d = classify(p)
        if k:
            votes[k] = votes.get(k, 0) + 1
    if not votes:
        return None
    k, n = max(votes.items(), key=lambda kv: kv[1])
    return k if n >= 2 or len(votes) == 1 else None


def tray(im):
    return read_piece(im, TRAY_C, TRAY_P, win=(196, 860, 522, 1140))


def preview(im):
    # 상자 안쪽 배경(어두움): 상자 모서리 근처에서 직접 잼
    bg = im[960:966, 538:544].reshape(-1, 3).astype(float).mean(0)
    return read_piece(im, PREV_C, PREV_P, bg, win=(537, 958, 613, 1036))


def _near(p, c, tol=22):
    return all(abs(p[i] - c[i]) <= tol for i in range(3))


def px(im, x, y, r=6):
    return im[y - r:y + r, x - r:x + r].reshape(-1, 3).astype(float).mean(0)


BROWN = (110, 59, 36)


POPUP_Y = [882]


def popup_y(im):
    """'공방 마감' 창의 나가기/다시 하기 버튼 줄 y (창 내용에 따라 위아래로 움직임). 없으면 None"""
    if not _near(px(im, 300, 1093), (28, 24, 18), 18):
        return None
    hits = []
    for y in range(770, 940, 3):
        a, b = px(im, 470, y, 3), px(im, 211, y, 3)
        if (_near(a, (81, 48, 32), 16) or _near(a, (112, 59, 36), 16)) and _near(b, (45, 35, 28), 12):
            hits.append(y)
    runs, cur = [], []
    for y in hits:
        if cur and y - cur[-1] > 3:
            runs.append(cur)
            cur = []
        cur.append(y)
    if cur:
        runs.append(cur)
    best = max(runs, key=len) if runs else []
    if len(best) < 5:
        return None
    POPUP_Y[0] = (best[0] + best[-1]) // 2
    return POPUP_Y[0]


def state(im):
    """'game' / 'over'(결과 버튼) / 'lobby' / 'popup'(공방 마감) / None"""
    b1, b2 = px(im, 300, 1093), px(im, 430, 1085)
    if _near(b1, BROWN) and _near(b2, BROWN):
        if _near(px(im, 110, 212), (121, 89, 47), 26):
            return 'lobby'
        return 'over'
    if popup_y(im):
        return 'popup'
    b, unk = read_board(im)
    if len(unk) <= 4 and _near(px(im, 250, 207), (36, 27, 19), 14) and _near(px(im, 108, 340, 4), (25, 18, 15), 12) and _near(px(im, 612, 850, 4), (25, 18, 15), 12):
        return 'game'
    return None
