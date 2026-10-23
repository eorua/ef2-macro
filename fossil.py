"""fossil.py - 화석 발굴 자동 플레이 (망치 최소 사용)
화석 발굴 창을 열어 둔 상태에서 실행하세요. 보드 크기(레벨)는 자동으로 인식합니다.
  py fossil.py                 -> 화면만 읽고 다음 한 수를 알려줌 (클릭 안 함)
  py fossil.py go              -> 망치를 다 쓸 때까지 자동 플레이
  py fossil.py go keep=10      -> 망치 10개가 남으면 멈춤
  py fossil.py go boards=3     -> 3판만 하고 멈춤
"""
import cv2, numpy as np, sys, os, time, random, base64, zlib
import daily as D

SHOTS = D.SHOTS
NSAMP = 150                 # 추론용 가상 배치 수
POPUP_ROI = (280, 905, 440, 950)   # 보상 팝업의 초록 확인 버튼
TAP_WAIT = 1.0        # 한 번 두드린 뒤 기다리는 시간(초). 줄이면 빨라지지만 화면을 덜 기다림
POPUP_BTN = (360, 928)
HAMMER_ROI = (500, 235, 560, 280)
LABEL_ROI = (296, 1050, 350, 1082)  # "감지된 화석 (n/K)" 의 숫자 부분


def log(*a):
    print(time.strftime("[%H:%M:%S] fossil:"), *a, flush=True)


# ------------------------------------------------------------ 템플릿
def _unpack(b):
    out = {}
    for part in b.split("|"):
        ch, n, h, w, data = part.split(":")
        a = np.frombuffer(zlib.decompress(base64.b64decode(data)), np.uint8)
        out[ch] = a.reshape(int(n), int(h), int(w)).astype(np.float32) / 255
    return out

TILE_T = _unpack("1:1:18:12:eNpjYAABv/8gAGYy/Iexra1fw9id/2Hgxo3/qAAq9fr1a2trBmskcxiQ2BuxmU8jNsQvAO51e3A=|2:1:18:12:eNpjYPA78h8MTBgYMv9DwT0TkX3//78+cgQk9ykUSKxiYGAAyXjcuHFDCsjOB7IZoGAxgs37H85WPA1k7oOwQcwjIG0MUmDbysCi+0DMaSCWyEYQs5MdxAbZ9n8xWIHUUyBzLi+IqX4RbLJfGRCAVfw/8hqs/T92AADsxX0N|3:1:18:12:eNpjYIiO/v///6RoOQYGtob/EHCOhyH0PwysYrgNJJeYV4LZDVeABIPWFRCbQUKFh4HB8zOYDQKJ24BqPMHMtz+BzESIMNiYQxD2kiWHgJwTchCexDaEKog6FZVoZ5AE3HIGhlUg+j/YDblAu946z0NyG1vDObibGRjk4H4BAC6SdWI=|4:1:18:12:eNpjYAAB+////0uDWQxGDxDsp//hbP+fcLbuu/9wdsN/ODv22/+fPyFsrjX//69bB2F3ASl7CFv24v//2QwQ9sH//+9pQtlA4vfr1yC9b1//xwE6weAWkDWtE+K4dQh3YmEDAJ8Kel4=")
HAM_T = _unpack("0:1:18:12:eNpjYPH7DwZ+LAwsQf//vz5z5vX//0EsIv//P89jYMh7/v+/CJC9kQEINv7/X9QJZUc8AusCsxmOUI+9EMp2vwO0GGFvJ5D9II6BIe4BUJgt4///R5s2AV2QwcbAkQRxfxIHUCWblFRzs5QUGwMDAINDcjs=|1:1:18:12:eNpjYAABKSmp////M0gZA8F/MPBZ9h8ZzASCMyBGQ0MDSEMDiM0AAfU0ZpNlFwCN4l95|2:1:18:12:eNpjYPH7DwZ+LAwsQf//vz5z5vX//0EsUf//P89jYMh7/v+/CJCZxQAEG8HsIwwwdlqaH5zNAAVI7Lr3CPbc//9tmcAsnqn/35pCBEUm/n9gD2FKTPx/zRXKnPr/fxlUwdz/5xqsIdpW/v8/F2rYDqBzH22CgP84AACGBGGo|3:3:18:12:eNpjkvL7DwZ+LAzOQOr1medAMojl//+3m/IYEjYBeSIzZ5YxgMBGIJsBCnCw857/z2AD0vZnzpx5/T+JAyQGscAappqh9/t/WyYc5kSlpfnB2Av//z8CV/P///MsIDPuAZAdBeRs2rTp0X+gXSxBEOeD7WKRSvj/v1lKCugCplF/DSl/AQBS5BOk|4:4:18:12:eNrd0qEOgzAUBdAnSJD7grnKfQES16RL5ipwE7j+AaJ6sm4eMb3faTKBQ5Ag5u8KfVAMyTRXHdH2vZuUaAoAQzGXjX2y7FdLD7fYoRFs9YFgFx1MzpZocooW+N6JfYOj2Y9TmP5WV1WHAVZhEzsnzEJr4xbh/OtMq5c9d12Eu5KN5HJjn1wNQ8vWHbRkO9TE1j0EuxxRZdFZhbGk6Dg9N5NDo+d+L9umXsv7//qovY73D3+UpGMU|5:3:18:12:eNoT+Q8HIiJA4vUZMBAAsp/nMUAAkL2RARfbfaY1lP1807X/FzZpgtkQcOOMAJMUGCwHmQ/TtxHIgbF7PyPYptf+/09L84Or6fz/KALK7gSa+SCOgSHuAdActoz//x9t2vTo//8MNgaOJIhdSRxAlWxSUs3//yewIblhmPmLAeEvMBvirTMMPv//b4LZh+QMTPbMmTD2pk0gvAnZyDMMUlL/wR5D1vcMj4FpaWlwNkyqAcIGWTQTpMQHbNkmiLwxzC5joDTEIikpBgYAyg0t/Q==|9:1:18:12:eNpjYPH7DwZ+LAwsQUD6+ZnX//8HsYgAWZsSGPKe//8vUvT//0YGINgIZP///ygCyu78//8IiMngfgdkAITNcATE/twLY2tD9c7/+f+/0Eug1NSpYOsY5M8AdT058/7//wtAafNNm4LA5jNAARLb78b/yVwQi2be+P9fHcjQ3LTpGtCQMh4g2xpkXKMxiAlkL5eSAqsFAG4waRo=")


def _match(g, T, thr):
    best = ("?", -1.0)
    for k, arr in T.items():
        for t in arr:
            sc = float((g * t).sum() / (np.linalg.norm(g) * np.linalg.norm(t) + 1e-6))
            if sc > best[1]:
                best = (k, sc)
    return best if best[1] >= thr else ("?", best[1])


# ------------------------------------------------------------ 보드 크기 자동 인식

def _run_span(col):
    best = (0, 0, 0); s = None
    for i, v in enumerate(list(col) + [False]):
        if v and s is None: s = i
        if not v and s is not None:
            if i - s > best[0]: best = (i - s, s, i - 1)
            s = None
    return best

def _count(profile, length, lo=2, hi=14, thr=4500):
    """경계선 에너지로 칸 수 추정: 모든 경계가 뚜렷한 후보 중 가장 큰 값"""
    best = None
    for n in range(lo, hi + 1):
        w = length / n
        e = []
        for k in range(1, n):
            c = int(round(k * w))
            e.append(profile[max(0, c - 2):c + 3].max())
        if min(e) >= thr: best = n
    return best

def detect_grid(img):
    """(rows, cols, x0, cw, y0, ch) 또는 None.  1280x720 화면의 화석 발굴 보드 기준"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    V = hsv[..., 2].astype(int); S = hsv[..., 1].astype(int)
    dark = (V < 125) & (V > 60) & (S > 35)
    best = None
    for x in range(450, 641):
        L, a, b = _run_span(dark[340:1050, x])
        if L >= 300: best = x
    if best is None: return None
    xr = best
    spans = [_run_span(dark[340:1050, x]) for x in range(xr - 3, xr + 1)]
    spans = [sp for sp in spans if sp[0] >= 300]
    yt = min(sp[1] for sp in spans) + 340
    yb = max(sp[2] for sp in spans) + 340
    xl = None
    for x in range(60, 200):
        L, a, b = _run_span(dark[340:1050, x])
        if L >= 200: xl = x; break
    if xl is None: return None
    x0 = xl + 3.0; xin = (xr - 3.0) - x0
    y0 = yt - 2.0; yin = (yb - 5.0) - y0
    if xin < 150 or yin < 150: return None
    Vf = V.astype(float)
    gx = np.abs(np.diff(Vf[int(y0) + 3:int(y0 + yin), int(x0):int(x0 + xin)], axis=1)).sum(axis=0)
    gy = np.abs(np.diff(Vf[int(y0):int(y0 + yin), int(x0):int(x0 + xin)], axis=0)).sum(axis=1)
    cols = _count(gx, xin); rows = _count(gy, yin)
    if not cols or not rows: return None
    return rows, cols, x0, xin / cols, y0, yin / rows



class Geo:
    """보드 크기별 기하/배치 정보"""
    _cache = {}

    def __init__(self, rows, cols, x0, cw, y0, ch):
        self.rows, self.cols, self.x0, self.cw, self.y0, self.ch = rows, cols, x0, cw, y0, ch
        self.N = rows * cols
        self.sx, self.sy = cw / 64.1, ch / 66.0
        key = (rows, cols)
        if key not in Geo._cache:
            Geo._cache[key] = self._build()
        self.PL, self.COVER, self.DMG = Geo._cache[key]

    def _build(self):
        R, C, N = self.rows, self.cols, self.N
        bit = lambda r, c: 1 << (r * C + c)
        PL = []
        for r in range(R):
            for c in range(C - 3):
                PL.append((sum(bit(r, c + k) for k in range(4)), "H"))
        for r in range(R - 3):
            for c in range(C):
                PL.append((sum(bit(r + k, c) for k in range(4)), "V"))
        for r in range(R - 1):
            for c in range(C - 1):
                PL.append((bit(r, c) | bit(r, c + 1) | bit(r + 1, c) | bit(r + 1, c + 1), "S"))
        COVER = [[] for _ in range(N)]
        for pi, (m, s) in enumerate(PL):
            for i in range(N):
                if m >> i & 1: COVER[i].append(pi)
        DMG = []
        for i in range(N):
            r, c = divmod(i, C)
            lst = []
            for dr, dc, v in ((0, 0, 2), (1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < R and 0 <= cc < C: lst.append((rr * C + cc, v))
            DMG.append(lst)
        return PL, COVER, DMG

    def center(self, i):
        r, c = divmod(i, self.cols)
        return int(self.x0 + self.cw * (c + .5)), int(self.y0 + self.ch * (r + .5))


# ------------------------------------------------------------ 화면 읽기
def _cell(hsv, g, r, c, m=0.12):
    mx = int(g.cw * m); my = int(g.ch * m)
    x1 = int(g.x0 + g.cw * c) + mx; x2 = int(g.x0 + g.cw * (c + 1)) - mx
    y1 = int(g.y0 + g.ch * r) + my; y2 = int(g.y0 + g.ch * (r + 1)) - my
    return hsv[y1:y2, x1:x2]


def _is_tile(hsv, g, r, c):
    h = _cell(hsv, g, r, c)
    if h.size == 0: return False
    H, S, V = np.median(h[..., 0]), np.median(h[..., 1]), np.median(h[..., 2])
    return 11 <= H <= 22 and 65 <= S <= 95 and V >= 175


def _fossil(hsv, g, r, c):
    h = _cell(hsv, g, r, c, 0.06)
    H, S, V = h[..., 0].astype(int), h[..., 1].astype(int), h[..., 2].astype(int)
    if ((H >= 30) & (H <= 70) & (S >= 80) & (V >= 100)).mean() > 0.12: return True
    if ((H >= 135) & (H <= 170) & (S >= 80) & (V >= 100)).mean() > 0.12: return True
    if ((V >= 165) & (S <= 90)).mean() > 0.08: return True
    return False


def _glyph(hsv, g, r, c):
    cx = int(g.x0 + g.cw * (c + .5)); cy = int(g.y0 + g.ch * (r + .5))
    hw = int(g.cw * 0.23); hh = int(g.ch * 0.30)
    v = hsv[cy - hh:cy + hh, cx - hw:cx + hw, 2].astype(int)
    base = np.median(v)
    mask = (v < base - 18).astype(np.uint8) * 255
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best = None
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 30 * g.sx * g.sy or h < 14 * g.sy or h > 36 * g.sy: continue
        d = abs((x + w / 2) - hw) + abs((y + h / 2) - hh)
        if best is None or d < best[0]: best = (d, i, x, y, w, h)
    if best is None: return None
    _, i, x, y, w, h = best
    gl = (lab[y:y + h, x:x + w] == i).astype(np.uint8) * 255
    return cv2.resize(gl, (12, 18), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


class Board:
    pass


def read_board(img, g):
    """hp[i]: 남은 체력(부서졌으면 0, 숫자를 못 읽으면 3으로 가정), broken/R(보물 조각)/empty(빈 칸) 비트마스크"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    b = Board()
    b.geo = g
    b.hp = [0] * g.N; b.broken = 0; b.R = 0; b.empty = 0
    b.tiles = 0; b.unread = 0; b.code = []
    for r in range(g.rows):
        for c in range(g.cols):
            i = r * g.cols + c
            if _is_tile(hsv, g, r, c):
                b.tiles += 1
                gl = _glyph(hsv, g, r, c)
                k = "?"
                if gl is not None:
                    k, _ = _match(gl, TILE_T, 0.75)
                if k == "?":
                    b.unread += 1; b.hp[i] = 3
                else:
                    b.hp[i] = int(k)
                b.code.append(k)
            else:
                b.broken |= 1 << i
                if _fossil(hsv, g, r, c):
                    b.R |= 1 << i; b.code.append("F")
                else:
                    b.empty |= 1 << i; b.code.append(".")
    b.valid = b.tiles >= 3 and b.unread <= max(1, b.tiles // 20)
    b.sig = tuple(b.code)
    return b


def _digits(img, roi, lo, hi, smax, minh, thr):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 2] >= lo) & (hsv[..., 2] <= hi) & (hsv[..., 1] <= smax)).astype(np.uint8) * 255
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    cs = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 20 or h < minh: continue
        cs.append((x, y, w, h, i))
    cs.sort()
    out = []
    for x, y, w, h, i in cs:
        gl = (lab[y:y + h, x:x + w] == i).astype(np.uint8) * 255
        gl = cv2.resize(gl, (12, 18), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        out.append(_match(gl, HAM_T, thr)[0])
    return out


def read_hammers(img):
    d = _digits(img, HAMMER_ROI, 225, 255, 40, 14, 0.9)
    if not d or "?" in d: return None
    return int("".join(d))


def read_label(img):
    """'감지된 화석 (n/K)' -> (n, K) 못 읽으면 (None, None)"""
    d = _digits(img, LABEL_ROI, 185, 222, 90, 10, 0.8)
    d = [x for x in d if x != "?"]
    if len(d) == 2 and d[0].isdigit() and d[1].isdigit():
        return int(d[0]), int(d[1])
    return None, None


def popup_up(img):
    return D.ratio(img, POPUP_ROI, "green") >= 0.5


def show(b):
    g = b.geo
    return "\n".join(" ".join(b.code[r * g.cols + c] for c in range(g.cols)) for r in range(g.rows))


# ------------------------------------------------------------ 추론 / 전략
def _cover(g, unc, used, cnt, empty, K, n_seen, allow_s, rng):
    """보이는 조각(unc)을 전부 덮는 화석 배치를 무작위 역추적으로 찾기 (덮는 화석 수 = n_seen)"""
    if not unc:
        return (used, cnt) if (n_seen is None or cnt == n_seen) else None
    if cnt >= K or (n_seen is not None and cnt >= n_seen): return None
    best = None
    m = unc
    while m:
        low = (m & -m).bit_length() - 1
        m &= m - 1
        valid = [pi for pi in g.COVER[low] if (allow_s or g.PL[pi][1] != "S") and not (g.PL[pi][0] & (empty | used))]
        if best is None or len(valid) < len(best[1]): best = (low, valid)
        if len(valid) <= 1: break
    if not best[1]: return None
    cand = best[1][:]
    rng.shuffle(cand)
    for pi in cand:
        r = _cover(g, unc & ~g.PL[pi][0], used | g.PL[pi][0], cnt + 1, empty, K, n_seen, allow_s, rng)
        if r is not None: return r
    return None


def sample_worlds(g, empty, R, K, n_seen, n, rng, allow_s):
    out = []
    ok_pl = [pi for pi in range(len(g.PL)) if allow_s or g.PL[pi][1] != "S"]
    for _ in range(n):
        r = _cover(g, R, 0, 0, empty, K, n_seen, allow_s, rng)
        if r is None: break
        used, cnt = r
        ok = True
        for _ in range(K - cnt):
            valid = [pi for pi in ok_pl if not (g.PL[pi][0] & (empty | used))]
            if not valid: ok = False; break
            used |= g.PL[rng.choice(valid)][0]
        if ok: out.append(used)
    return out


def choose(b, rng, K=5, n_seen=None):
    """다음에 두드릴 칸 번호와 설명. 가정을 단계적으로 넓혀 가며 추론"""
    g = b.geo
    ws = []; tag = ""
    for allow_s, k, ns in ((False, K, n_seen), (True, K, n_seen), (True, K, None), (True, K + 1, None)):
        ws = sample_worlds(g, b.empty, b.R, k, ns, NSAMP, rng, allow_s)
        if len(ws) >= 5:
            tag = ("1x4만" if not allow_s else "2x2 포함") + ("" if ns is not None or n_seen is None else ", 감지수 무시") + (" K+1" if k != K else "")
            break
    p = np.zeros(g.N)
    for u in ws:
        for i in range(g.N):
            if u >> i & 1: p[i] += 1
    if ws: p /= len(ws)
    best = None
    for t in range(g.N):
        if b.broken >> t & 1: continue
        if ws:
            sc = 0.0
            for j, d in g.DMG[t]:
                if b.broken >> j & 1: continue
                h = b.hp[j]
                sc += p[j] * min(d, h) / h
        else:
            sc = sum(min(d, b.hp[j]) for j, d in g.DMG[t] if not b.broken >> j & 1)
        sc += rng.random() * 1e-6
        if best is None or sc > best[0]: best = (sc, t)
    if best is None: return None, "두드릴 칸 없음"
    if not ws: return best[1], "추론 실패 -> 피해 최대"
    return best[1], "%s, 표본 %d" % (tag, len(ws))


LA_TOPK = 8          # patch108: 내다볼 후보 칸 수
LA_GAMMA = 0.3       # patch108: 다음 수 점수 가중치 (0 이면 기존과 같음)


def _score_all(g, p, hp, broken):
    sc = np.full(g.N, -1.0)
    for t in range(g.N):
        if broken >> t & 1: continue
        s = 0.0
        for j, d in g.DMG[t]:
            if broken >> j & 1: continue
            h = hp[j]
            s += p[j] * min(d, h) / h
        sc[t] = s
    return sc


def choose_la(b, rng, K=5, n_seen=None):
    """patch108: 기존 점수 + 2수 앞 내다보기. 표본이 없으면 기존 choose"""
    g = b.geo
    ws = []; tag = ""
    for allow_s, k, ns in ((False, K, n_seen), (True, K, n_seen), (True, K, None), (True, K + 1, None)):
        ws = sample_worlds(g, b.empty, b.R, k, ns, NSAMP, rng, allow_s)
        if len(ws) >= 5:
            tag = ("1x4만" if not allow_s else "2x2 포함") + (" K+1" if k != K else "")
            break
    if len(ws) < 5 or LA_GAMMA <= 0:
        return choose(b, rng, K, n_seen)
    W = np.array([[u >> i & 1 for i in range(g.N)] for u in ws], dtype=np.float32)
    p = W.mean(0)
    sc = _score_all(g, p, b.hp, b.broken)
    best = None
    for t in list(np.argsort(-sc)[:LA_TOPK]):
        if sc[t] < 0: continue
        hp2 = list(b.hp); brk = 0
        for j, d in g.DMG[t]:
            if b.broken >> j & 1: continue
            hp2[j] = max(0, hp2[j] - d)
            if hp2[j] == 0: brk |= 1 << j
        broken2 = b.broken | brk
        bcells = [j for j in range(g.N) if brk >> j & 1]
        groups = {}
        for wi, u in enumerate(ws):
            groups.setdefault(tuple(u >> j & 1 for j in bcells), []).append(wi)
        fut = 0.0
        for idx in groups.values():
            m = _score_all(g, W[idx].mean(0), hp2, broken2).max()
            if m > 0: fut += len(idx) / len(ws) * m
        v = sc[t] + LA_GAMMA * fut + rng.random() * 1e-6
        if best is None or v > best[0]: best = (v, int(t))
    if best is None:
        return choose(b, rng, K, n_seen)
    return best[1], "%s, 표본 %d, 내다보기" % (tag, len(ws))


# ------------------------------------------------------------ 실행
GEO = None


def get_geo(img):
    global GEO
    if GEO is None:
        r = detect_grid(img)
        if r is None: return None
        rows, cols, x0, cw, y0, ch = r
        if rows < 3 or cols < 3: return None
        GEO = Geo(rows, cols, x0, cw, y0, ch)
        log("보드 크기 %d행 x %d열 인식" % (rows, cols))
    return GEO


def read_state(max_tries=10):
    prev = None; last = None
    for _ in range(max_tries):
        img = D.cap()
        if img is None:
            time.sleep(1.0); continue
        last = img
        if D.blocked(img): return "blocked", img, None
        if popup_up(img): return "popup", img, None
        g = get_geo(img)
        if g is not None:
            b = read_board(img, g)
            if b.valid:
                if prev is not None and b.sig == prev.sig: return "board", img, b
                prev = b
            else:
                prev = None
        time.sleep(0.5)
    return "unknown", last, None


def save_shot(img, name):
    try:
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, name), img)
    except Exception as e:
        log("스크린샷 저장 실패:", e)



# ---- 화석 발굴 창 자동 진입 ----
EV_ICON_B64 = "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"
EV_ICON_FALLBACK = (600, 430)
EV_BTN_FOSSIL = (365, 584)
EV_ROI1 = (230, 565, 500, 605)
EV_ROI2 = (230, 650, 500, 690)
EV_CLOSE = (544, 496)


def _tan(img, roi):
    x1, y1, x2, y2 = roi
    h = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = (h[..., 0] >= 8) & (h[..., 0] <= 22) & (h[..., 1] >= 70) & (h[..., 1] <= 190) & (h[..., 2] >= 110)
    return float(m.mean())


def event_popup_up(img):
    return _tan(img, EV_ROI1) > 0.35 and _tan(img, EV_ROI2) > 0.35


def find_event_icon(img):
    ic = cv2.imdecode(np.frombuffer(base64.b64decode(EV_ICON_B64), np.uint8), cv2.IMREAD_COLOR)
    ih, iw = ic.shape[:2]
    x1, y1, x2, y2 = 420, 60, 720, 720
    reg = img[y1:y2, x1:x2]
    best = (0.0, None)
    for s in (1.15, 1.25, 1.3, 1.35, 1.45):
        t = cv2.resize(ic, (int(iw * s), int(ih * s)))
        th, tw = t.shape[:2]
        if th >= reg.shape[0] or tw >= reg.shape[1]: continue
        r = cv2.matchTemplate(reg, t, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(r)
        if mv > best[0]:
            best = (mv, (x1 + ml[0] + tw // 2, y1 + ml[1] + th // 2))
    return best


def enter_fossil():
    """기본 화면 -> 이벤트 아이콘 -> 화석 발굴. 성공하면 True"""
    for attempt in range(2):
        img = D.cap()
        if img is None:
            time.sleep(1.0); continue
        if D.blocked(img):
            log("성 함락/결과 팝업 감지 -> 진입 중단"); return False
        if not event_popup_up(img):
            sc, pos = find_event_icon(img)
            if pos is None or sc < 0.5:
                log("이벤트 아이콘 템플릿 점수 %.2f -> 기본 위치 사용" % sc)
                pos = EV_ICON_FALLBACK
            else:
                log("이벤트 아이콘 인식 (점수 %.2f) %s" % (sc, pos))
            D.tap(pos, 1.5)
            img = D.cap()
            if img is None or not event_popup_up(img):
                log("이벤트 창이 안 열림 (시도 %d)" % (attempt + 1))
                if img is not None: save_shot(img, "fossil_event_fail.png")
                continue
        log("이벤트 창 -> 화석 발굴 선택")
        D.tap(EV_BTN_FOSSIL, 2.0)
        st, img, b = read_state(6)
        if st in ("board", "popup"):
            return True
        if img is not None: save_shot(img, "fossil_enter_fail.png")
    return False


FOSSIL_X = (637, 181)


def leave_fossil():
    """발굴 창/이벤트 창이 열려 있으면 닫아서 기본 화면으로 되돌린다 (메인이 이어서 돌 수 있게)"""
    for _ in range(4):
        img = D.cap()
        if img is None:
            time.sleep(1.0); continue
        if D.blocked(img):
            return
        if popup_up(img):
            D.tap(POPUP_BTN, 1.5); continue
        if event_popup_up(img):
            D.tap(EV_CLOSE, 1.2); continue
        if detect_grid(img) is not None:
            D.tap(FOSSIL_X, 1.2); continue
        break
    log("발굴 창 닫음 (기본 화면 복귀)")


def run(go, keep=0, max_boards=999):
    try:
        _run(go, keep, max_boards)
    finally:
        if go:
            try: leave_fossil()
            except Exception as e: log("창 닫기 오류:", e)


def _run(go, keep=0, max_boards=999):
    global GEO
    rng = random.Random()
    GEO = None
    st, img, b = read_state()
    if st != "board" and st != "popup":
        if st == "blocked":
            log("성 함락/결과 팝업 감지 -> 중단"); return
        log("발굴 화면이 아님 -> 이벤트 창에서 화석 발굴로 진입 시도")
        if not enter_fossil():
            log("화석 발굴 화면 진입 실패 (shots 폴더의 fossil_*.png 확인)")
            return
        GEO = None
        st, img, b = read_state()
        if st != "board" and st != "popup":
            log("진입 후에도 보드를 못 읽음 (상태: %s)" % st)
            if img is not None: save_shot(img, "fossil_unknown.png")
            return
    if not go:
        if st == "popup":
            log("보상 팝업이 떠 있음"); return
        print(show(b))
        ham = read_hammers(img)
        n_seen, K = read_label(img)
        t, why = choose_la(b, rng, K or 5, n_seen)
        g = b.geo
        log("보드 %d행x%d열, 망치 %s개, 감지된 화석 %s/%s, 다음 수: %d행 %d열 (%s)" % (
            g.rows, g.cols, ham, n_seen, K, t // g.cols + 1, t % g.cols + 1, why))
        return
    boards = 0; taps_board = 0; taps_total = 0; stuck = 0
    ham_known = None; since = 0          # 읽은 마지막 망치 수와 그 뒤 두드린 횟수 (6,7,8 은 못 읽어서 추정)
    log("시작: 망치 %s개, 남길 망치 %d개" % (read_hammers(img), keep))
    while True:
        if st == "blocked":
            log("성 함락/결과 팝업 감지 -> 중단 (메인이 처리하도록 두세요)"); return
        if st == "popup":
            boards += 1
            log("보상 확인 (이번 판 %d번 두드림, 누적 %d판)" % (taps_board, boards))
            D.tap(POPUP_BTN, 2.0)
            taps_board = 0
            ham_known = None
            GEO = None                      # 다음 판은 크기가 바뀔 수 있음
            if boards >= max_boards:
                log("요청한 %d판 완료" % boards); return
            st, img, b = read_state()
            continue
        if st != "board":
            log("알 수 없는 화면 -> 중단")
            if img is not None: save_shot(img, "fossil_unknown.png")
            return
        ham = read_hammers(img)
        if ham is not None:
            ham_known = ham; since = 0
        elif ham_known is not None:
            ham = ham_known - since          # 한 번 두드릴 때마다 망치 1개
        if ham is not None and ham <= keep:
            log("망치 %d개 (남길 수 %d개) -> 종료. 총 %d번, %d판" % (ham, keep, taps_total, boards)); return
        n_seen, K = read_label(img)
        t, why = choose_la(b, rng, K or 5, n_seen)
        if t is None:
            log("두드릴 칸이 없음 -> 중단"); return
        g = b.geo
        x, y = g.center(t)
        log("망치 %s | %d행 %d열 두드림 (%s)" % (ham, t // g.cols + 1, t % g.cols + 1, why))
        D.tap((x, y), TAP_WAIT)
        taps_board += 1; taps_total += 1; since += 1
        old = b.sig
        st, img, b = read_state()
        if st == "board" and b.sig == old:
            stuck += 1
            if stuck >= 2:
                log("두드려도 화면이 안 변함 (망치 부족?) -> 중단")
                save_shot(img, "fossil_stuck.png"); return
        else:
            stuck = 0


# ============================================================ patch127: 화석 판별 개선 + 조각 모양 인식
# 1) 빈 칸 = 회갈색 바닥(채도 ~44, 밝기 ~113). 그 색에서 벗어난 픽셀이 30% 넘으면 화석
#    (전에는 초록/보라/흰색만 봐서 빨강·파랑 화석을 빈 칸으로 읽음 -> 화석 수가 안 맞아 엉뚱한 곳을 팜)
# 2) 화석 그림은 색(등급)만 다르고 모양별로 같은 그림 -> 한 칸만 보여도 '어느 모양의 몇 번째 조각'인지 알아냄
#    V0~V3 세로 1x4 위->아래, H0~H3 가로 1x4 왼->오, S0~S3 2x2 (왼위,오위,왼아래,오아래)
#    처음 보는 조각(가로 1x4 등)은 추론으로 위치가 확실해지면 스스로 배워서 tpl\fossil_parts.npz 에 저장
PART_SEED = "V0,V1,V2,V3,S0,S1,S3,S2#eNq1mB+c60oUxwcWCoXCQqAQCFQeBB4EAoULAwuFwMJC4cGDgWBhZaFwITDwoBBYLCwGLiwECg+igUCgUCgECoWFeWdmMskkM/3c1/v53PP57Hb3225y5vz7nWxVjSyn8EUI+pk5hPgmfaN7xnJKVwO6ya5MWh33dF1dWGfHDk+3TLfCexR4NsRgHy7nATPsw4OP703OIoQmuYUXWYYws9pDZOdzdh9/upPfuo5ztHNbHH6JzzI7h7zklY2D0auRAsH9coQPPJe+v6aXIU+mwOPcR+vRH7xwzooFehnyUHB2dB48Mgib5Iydhpx/flUzu/+r8bkySoX/eg1dT6J+5LlIf+AmxtjpilfLzk5rgP1Xzy+bngfnnu9l9RMM3w96cYo+m7OKLjdDN/Ml54yVp5H/TfZ4o35q5FfaPY8YupCbo+ImLcaa87F+ARLZOTvYOQ4MnnpgHe39aXw098JBfqXPGJd6vmLjVDJf/ucIk/YuyYir4fQ4KvXY5KHOx9f5RW7UYWyLJ9i7wOYAiu3zkO0cbR6etMOlTs8PHiGFeiNAj22pnQO93g9d/bwN+2COdn3f9Oe7OGhRKO5+dPyZpyWX3PsY97vgrp4Efp1MJPtRbwF+ndb/YewCNB6bm0q2bpYV47ngYjzj/lBzXiRC7/q4sBRa6134kUG7+mnX72Ui/Z7LfnW1+lf5S+RMbJvyEA31SuWt3HZJisc6lvniXLk/4tB7L+2riE9ZdnkX+Tr5SMTneu3qpNULfRg2a36/Z6N8pN+dDla00LmTKr4KSd1z5OxUn2bZ+txzvZ6PfP41fNDY+kLV05+nG/pi6EXL4Z3aztEEb60cJixMn8LCO5uJ+TTD2EWBNgflOafgfA3nX3dYxkVF56Kaf6yvhxv8Sgd8Pupz9bveDzuo48Sq4wn5ub7LmsHxOG5/ydcJGfGo7RNtDp22jfwd9FybQ2UYnAXPXDTtk1wscc37n/B5nOr1tu/i/64fgteBjG3+pfOkzZdnWVEmgWPd4F7r/o62/UXo686CS2i+7xb+z3AvQP/DFhgscI39WejV9ZDqezTdD/Vd2VDfF2qvaE+09bxIzkNev6ne59AjjeRKd1R/Qg0Fuk59Kj9W1EUUrBjp2diPMrzhX+QV1d7Ce/1/uHPtvZPHEysmE4s/l2pt9XMv9MJSLx96n/0Wi6xxu81B3+0XCu7kR+fO+Ic3eMPriURRY76VL4Z7sr7/6nuyxp3CcocNWlie5WD+Gnsgt3W7hxjzcFHY8Kd6zgrtcXhVP3ydq/MZd3mZK77/G29WyODpa9tnhIgunYu7pyTp+4w3cvwsdT259pzr1h+8hdMZ7fV9k+dify+9MPnmFZ/wvOxR3O/XhOU/am1tUnxuew4Cx5yLwVd1ujC0met7CnXUmNeZ8bli0eVVAn35YrkvHP4pNfkS5nU65XFK68F9dzl/deC56yAvl2H+sBXH/H8P4nSHOpQ6xfc79BqBeBYTOS9Bh7+l7xex5xPY604yuhlMxe22kfHZv8CxCjXd/CdIEuUfw9/f+ABIQge9uTRvdR0Ge/CvGOXZcnJtdZpcq3PhIVeeq+njH1zOlplSoJm/Mp7jso3YP2ZrSnOYx6l1n/Ep3fQ6qQkMxrT7v8tQpxzPYydKuY7+BzSlqt8="
PART_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tpl", "fossil_parts.npz")
PART_OK = 0.80        # 이 이상 닮으면 그 조각으로 인정
PART_GAP = 0.20       # 다른 조각과의 점수 차이가 이만큼은 나야 인정
PART_MAX = 80
_parts = None         # [labels(list), masks(N,24,24 float32)]


def _fossil(hsv, g, r, c):
    h = _cell(hsv, g, r, c, 0.06)
    if h.size == 0: return False
    S = h[..., 1].astype(int); V = h[..., 2].astype(int)
    return float(((np.abs(S - 44) > 28) | (np.abs(V - 113) > 40)).mean()) > 0.30


def _pmask(img, g, r, c, m=0.08):
    mx = int(g.cw * m); my = int(g.ch * m)
    x1 = int(g.x0 + g.cw * c) + mx; x2 = int(g.x0 + g.cw * (c + 1)) - mx
    y1 = int(g.y0 + g.ch * r) + my; y2 = int(g.y0 + g.ch * (r + 1)) - my
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    S = hsv[..., 1].astype(int); V = hsv[..., 2].astype(int)
    mk = ((np.abs(S - 44) > 28) | (np.abs(V - 113) > 40)).astype(np.float32)
    return cv2.resize(mk, (24, 24), interpolation=cv2.INTER_AREA)


def _pvec(mk):
    v = cv2.GaussianBlur(mk, (3, 3), 0)
    v = v - v.mean()
    return v / (np.linalg.norm(v) + 1e-6)


def _load_parts():
    global _parts
    if _parts is not None: return _parts
    labs, arr = [], []
    try:
        if os.path.exists(PART_FILE):
            z = np.load(PART_FILE)
            labs = [str(x) for x in z["labels"]]; arr = list(z["masks"].astype(np.float32))
    except Exception as e:
        log("조각 사전 읽기 실패 -> 기본값 사용:", e); labs, arr = [], []
    if not labs:
        names, data = PART_SEED.split("#")
        a = np.frombuffer(zlib.decompress(base64.b64decode(data)), np.uint8).reshape(-1, 24, 24)
        labs = names.split(","); arr = list(a.astype(np.float32) / 255)
    _parts = [labs, arr, [_pvec(m) for m in arr]]
    return _parts


def _save_parts():
    try:
        labs, arr, _ = _parts
        os.makedirs(os.path.dirname(PART_FILE), exist_ok=True)
        np.savez_compressed(PART_FILE, labels=np.array(labs), masks=np.array(arr, np.float32))
    except Exception as e:
        log("조각 사전 저장 실패:", e)


def _part_of(mk):
    """-> (조각 이름, 점수) 또는 (None, 점수)"""
    labs, _, vecs = _load_parts()
    v = _pvec(mk)
    best = {}
    for lb, t in zip(labs, vecs):
        s = float((v * t).sum())
        if s > best.get(lb, -9): best[lb] = s
    if not best: return None, 0.0
    order = sorted(best.items(), key=lambda kv: -kv[1])
    top, sc = order[0]
    sec = order[1][1] if len(order) > 1 else -1.0
    if sc >= PART_OK and sc - sec >= PART_GAP: return top, sc
    return None, sc


def _pl_index(g):
    if not hasattr(g, "PLIDX"):
        d = {}
        for pi, (m, s) in enumerate(g.PL):
            low = (m & -m).bit_length() - 1
            d[(s, low)] = pi
        g.PLIDX = d
    return g.PLIDX


def _pl_of(g, i, lab):
    """i 번 칸이 lab 조각이면 그 화석의 배치 번호 (판 밖이면 None)"""
    r, c = divmod(i, g.cols)
    s, k = lab[0], int(lab[1])
    if s == "V": r0, c0 = r - k, c
    elif s == "H": r0, c0 = r, c - k
    else: r0, c0 = r - k // 2, c - k % 2
    if r0 < 0 or c0 < 0: return None
    return _pl_index(g).get((s, r0 * g.cols + c0))


def _part_label(g, pi, i):
    m, s = g.PL[pi]
    low = (m & -m).bit_length() - 1
    r0, c0 = divmod(low, g.cols); r, c = divmod(i, g.cols)
    if s == "V": k = r - r0
    elif s == "H": k = c - c0
    else: k = (r - r0) * 2 + (c - c0)
    return "%s%d" % (s, k)


_read_board_old = read_board


def read_board(img, g):
    b = _read_board_old(img, g)
    b.part = {}; b.mk = {}
    for i in range(g.N):
        if b.R >> i & 1:
            r, c = divmod(i, g.cols)
            try:
                mk = _pmask(img, g, r, c)
            except Exception:
                continue
            b.mk[i] = mk
            lab, sc = _part_of(mk)
            if lab: b.part[i] = lab
    return b


def _forced(b):
    """알아본 조각들로 확정된 배치. 서로 겹치거나 빈 칸에 걸치면 그 판은 조각 정보를 안 씀"""
    g = b.geo
    pls = set()
    for i, lab in b.part.items():
        pi = _pl_of(g, i, lab)
        if pi is None: return set(), "조각 위치가 판 밖"
        pls.add(pi)
    used = 0
    for pi in pls:
        m = g.PL[pi][0]
        if m & used or m & b.empty: return set(), "조각끼리 충돌"
        used |= m
    return pls, ""


def _cover(g, unc, used, cnt, empty, K, n_seen, allow_s, rng, chosen=()):
    if not unc:
        return (used, cnt, chosen) if (n_seen is None or cnt == n_seen) else None
    if cnt >= K or (n_seen is not None and cnt >= n_seen): return None
    best = None
    m = unc
    while m:
        low = (m & -m).bit_length() - 1
        m &= m - 1
        valid = [pi for pi in g.COVER[low] if (allow_s or g.PL[pi][1] != "S") and not (g.PL[pi][0] & (empty | used))]
        if best is None or len(valid) < len(best[1]): best = (low, valid)
        if len(valid) <= 1: break
    if not best[1]: return None
    cand = best[1][:]
    rng.shuffle(cand)
    for pi in cand:
        r = _cover(g, unc & ~g.PL[pi][0], used | g.PL[pi][0], cnt + 1, empty, K, n_seen, allow_s, rng, chosen + (pi,))
        if r is not None: return r
    return None


_FORCE = [set()]      # 지금 판에서 조각 모양으로 확정된 배치 (sample_worlds 가 씀)
_LAST_PL = []         # 마지막 표본들의 '보이는 조각을 덮은 배치' 목록 (배우기용)
_LAST_ARGS = [0, None]   # 마지막 표본의 (화석 수, 감지수)


def sample_worlds(g, empty, R, K, n_seen, n, rng, allow_s):
    out = []; pls_out = []
    fset = _FORCE[0]
    if not allow_s and any(g.PL[pi][1] == "S" for pi in fset):
        return []                        # 2x2 가 확실히 있으면 '1x4만' 가정은 건너뜀
    fused = 0
    for pi in fset: fused |= g.PL[pi][0]
    ok_pl = [pi for pi in range(len(g.PL)) if allow_s or g.PL[pi][1] != "S"]
    for _ in range(n):
        r = _cover(g, R & ~fused, fused, len(fset), empty, K, n_seen, allow_s, rng, tuple(fset))
        if r is None: break
        used, cnt, chosen = r
        ok = True
        for _ in range(K - cnt):
            valid = [pi for pi in ok_pl if not (g.PL[pi][0] & (empty | used))]
            if not valid: ok = False; break
            used |= g.PL[rng.choice(valid)][0]
        if ok:
            out.append(used); pls_out.append(chosen)
    _LAST_PL[:] = pls_out
    _LAST_ARGS[:] = [K, n_seen]
    return out


def _learn(b, n_seen, K):
    """표본 전부가 같은 배치로 덮는 조각은 위치가 확실 -> 아직 모르는 조각이면 사전에 추가"""
    if n_seen is None or n_seen != K or len(_LAST_PL) < 30: return
    if _LAST_ARGS != [K, n_seen]: return          # 가정을 넓힌 표본(감지수 무시, K+1)으로는 안 배움
    g = b.geo
    labs, arr, vecs = _load_parts()
    added = []
    for i, mk in b.mk.items():
        if i in b.part: continue
        who = set()
        for ch in _LAST_PL:
            hit = [pi for pi in ch if g.PL[pi][0] >> i & 1]
            who.add(hit[0] if hit else -1)
            if len(who) > 1: break
        if len(who) != 1 or -1 in who: continue
        lab = _part_label(g, who.pop(), i)
        v = _pvec(mk)
        sims = [(float((v * t).sum()), lb) for lb, t in zip(labs, vecs)]
        if any(s >= PART_OK - 0.1 and lb != lab for s, lb in sims): continue   # 다른 조각과 헷갈림 -> 안 배움
        if any(s >= 0.95 and lb == lab for s, lb in sims): continue            # 이미 아는 모양
        if float(mk.mean()) < 0.15: continue
        labs.append(lab); arr.append(mk); vecs.append(v); added.append(lab)
    if added:
        if len(labs) > PART_MAX:
            del labs[8:8 + len(labs) - PART_MAX]; del arr[8:8 + len(arr) - PART_MAX]; del vecs[8:8 + len(vecs) - PART_MAX]
        _save_parts()
        log("새 조각 모양 배움: %s (사전 %d개)" % (",".join(added), len(labs)))


_choose_la_old = choose_la


def choose_la(b, rng, K=5, n_seen=None):
    g = b.geo
    fset, why = _forced(b) if getattr(b, "part", None) else (set(), "")
    if len(fset) > K: fset, why = set(), "조각 수가 너무 많음"
    _FORCE[0] = fset
    t, tag = _choose_la_old(b, rng, K, n_seen)
    if fset and ("추론 실패" in tag or _LAST_ARGS != [K, n_seen]):
        _FORCE[0] = set()                # 조각 정보로는 맞는 배치가 없음 -> 조각 정보 없이 다시
        t, tag = _choose_la_old(b, rng, K, n_seen)
        tag += ", 조각정보 버림"
        fset = set()
    else:
        try: _learn(b, n_seen, K)
        except Exception as e: log("조각 배우기 오류:", e)
    _FORCE[0] = set()
    if fset: tag += ", 조각으로 확정 %d개" % len(fset)
    if why: tag += ", " + why
    return t, tag


if __name__ == "__main__":
    go = "go" in sys.argv
    keep = 0; mb = 999
    for a in sys.argv[1:]:
        if a.startswith("keep="): keep = int(a[5:])
        if a.startswith("boards="): mb = int(a[7:])
    run(go, keep, mb)
