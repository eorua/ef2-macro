# -*- coding: utf-8 -*-
"""유물 공방(헥사 머지) 규칙 엔진 + 탐색 AI.
규칙(영상 분석으로 확인):
- 판: 5열 육각, 짝수열 5칸(위로 붙음) / 홀수열 4칸(반 칸 아래) = 23칸
- 조각(1~3칸)을 놓으면, 같은 등급이 3개 이상 이어진 덩어리는 하나로 합쳐짐
  3~4개 -> +1등급, 5개 이상 -> +2등급. 합쳐진 칸은 놓은 칸 중 하나에 생김. 연쇄 있음
- 새 조각 등급 = [hi-2, hi], hi = min(해금 최고-1, 6)  -> hi-2 미만 등급은 영영 짝이 안 옴(죽은 칸)
"""
import random

COLS = 5
CELLS = []                      # (col,row)
for c in range(COLS):
    for r in range(5 if c % 2 == 0 else 4):
        CELLS.append((c, r))
N = len(CELLS)
XS = [157, 259, 360, 462, 564]


def pix(i):
    c, r = CELLS[i]
    return XS[c], 388 + 104 * r + (52 if c % 2 else 0)


def to_ax(c, r):
    return (c, r - (c - (c & 1)) // 2)


AX = [to_ax(c, r) for c, r in CELLS]
AXI = {a: i for i, a in enumerate(AX)}
DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
NB = [[AXI[(a[0] + d[0], a[1] + d[1])] for d in DIRS if (a[0] + d[0], a[1] + d[1]) in AXI] for a in AX]
MAXT = 10


def rot(offs, k):
    out = []
    for q, r in offs:
        x, z = q, r
        y = -x - z
        for _ in range(k % 6):
            x, y, z = -z, -x, -y
        out.append((x, z))
    return out


_PL = {}


def placements(offs):
    """offs: 축좌표 상대위치 리스트 -> 놓을 수 있는 칸 인덱스 튜플 목록(판 모양만 고려)"""
    key = tuple(offs)
    if key in _PL:
        return _PL[key]
    res = []
    # patch225: 첫 칸을 판의 모든 칸에 맞춰 봄 (예전엔 (0,0) 자리를 판 칸에 맞춰서, 정규화된 휘어진/삼각 모양은
    #           (0,0)이 판 밖으로 나가는 자리를 통째로 빠뜨림 -> 회전 뒤 '둘 곳 없음' 반복의 원인)
    q0, r0 = offs[0]
    for c in AX:
        a = (c[0] - q0, c[1] - r0)
        idx = []
        for q, r in offs:
            j = AXI.get((a[0] + q, a[1] + r))
            if j is None:
                break
            idx.append(j)
        else:
            res.append(tuple(idx))
    _PL[key] = res
    return res


def group(b, i):
    t = b[i]
    seen = {i}
    st = [i]
    while st:
        u = st.pop()
        for v in NB[u]:
            if v not in seen and b[v] == t:
                seen.add(v)
                st.append(v)
    return seen


def gain(n):
    return 2 if n >= 5 else 1


def resolve(b, placed, choice=0, info=None, dot_cell=None):
    """b(list) 를 직접 바꿈. 반환: (만든 등급 목록, 갈림 수)
    choice: 첫 '갈림'(합쳐질 칸 후보 여러 개)에서 고를 후보 번호
    dot_cell: 조각에 찍힌 점(●)의 보드 칸 인덱스 (patch283: 점 찍힌 칸 우선 확정)"""
    made = []
    branches = 1
    front = list(placed)
    first_amb = True
    chain = None
    # patch269: 한 번에 한 그룹씩 처리 - 낮은 등급 그룹 먼저(같으면 놓은 순서), 연쇄면 직전 결과 칸이 결과 칸.
    #   실전 로그 2458수 재현: 예전(그룹 동시 처리) 불일치 52수 -> 26수, 새로 틀린 수 0
    #   (예: ★5·★4·★5 를 놓으면 ★4 그룹이 먼저 ★5 가 되고, 그 칸이 ★5 그룹과 이어져 ★6 이 그 자리에)
    while True:
        best = None
        done = set()
        for a in front:
            if a in done or b[a] <= 0:
                continue
            g = group(b, a)
            done |= g
            if len(g) >= 3 and b[a] < MAXT and (best is None or b[a] < best[0]):
                best = (b[a], g)
        if best is None:
            break
        t, g = best
        cands = [x for x in front if x in g]
        if chain is not None and chain in g:
            cands = [chain]
        # patch283: 점 찍힌 카드(dot_cell)가 후보군에 있으면 그 칸으로 100% 확정 합성
        elif dot_cell is not None and dot_cell in cands:
            cands = [dot_cell]
        # patch230: 3칸 사슬(직선·휘어진) 조각이 셋 다 합쳐지면 결과는 항상 양 끝 중 하나(실전 12/12, 가운데 0)
        elif len(cands) == 3 and first_amb and len(placed) == 3:
            deg = {c: sum(1 for d in cands if d != c and d in NB[c]) for c in cands}
            if sorted(deg.values()) == [1, 1, 2]:
                cands = [c for c in cands if deg[c] == 1]
        if len(cands) > 1 and first_amb:
            first_amb = False
            branches = len(cands)
            tgt = cands[choice % len(cands)]
        else:
            tgt = cands[0]
        for x in g:
            b[x] = 0
        nt = min(MAXT, t + gain(len(g)))
        b[tgt] = nt
        made.append((t, len(g), nt))
        chain = tgt
        front = [tgt] + [x for x in front if x not in g and x != tgt]
    if info is not None:
        info['branches'] = branches
    return made, branches


def spawn_hi(unlocked):
    return max(2, min(unlocked - 1, 6))


# ---------------- 평가 ----------------
W = dict(empty=10.0, dead=-14.0, pair=5.0, bridge5=9.0, bridge4=2.0, mob=0.35, hole=-6.0,
         mass=1.0, high_adj=1.5, lone=-2.0, nextdead=-4.0)
TRI_SHAPES = None


def _shapes3():
    base = [[(0, 0), (1, 0), (2, 0)], [(0, 0), (1, 0), (0, 1)], [(0, 0), (1, 0), (1, 1)]]
    out = set()
    for s in base:
        for k in range(6):
            o = rot(s, k)
            q0, r0 = o[0]
            out.add(tuple(sorted((q - q0, r - r0) for q, r in o)))
    return [list(s) for s in out]


SH3 = _shapes3()
PL3 = []
for s in SH3:
    PL3.extend(placements(s))
PL3 = list(set(tuple(sorted(p)) for p in PL3))


def evaluate(b, unlocked, w=W):
    hi = spawn_hi(unlocked)
    lo = max(1, hi - 2)
    e = 0.0
    empties = [i for i in range(N) if b[i] == 0]
    e += w['empty'] * len(empties)
    seen = set()
    groups = {}
    for i in range(N):
        t = b[i]
        if t == 0 or i in seen:
            continue
        g = group(b, i)
        seen |= g
        if t < lo:
            e += w['dead'] * len(g)
            continue
        if t == lo and unlocked < 7:
            e += w['nextdead'] * len(g) * 0.5
        groups.setdefault(t, []).append(g)
        if len(g) == 2:
            e += w['pair'] * (1.0 + 0.15 * t)
        else:
            # 혼자인 칸: 옆에 빈칸 없으면 더 나쁨
            if not any(b[v] == 0 for v in NB[i]):
                e += w['lone']
        e += w['mass'] * (3 ** (t - lo)) * len(g) * 0.05
    # 빈칸 하나에 같은 등급 덩어리 여러 개가 닿는가 (5합 준비)
    gid = {}
    for t, gs in groups.items():
        for k, g in enumerate(gs):
            for x in g:
                gid[x] = (t, k, len(g))
    for i in empties:
        touch = {}
        nb_empty = 0
        for v in NB[i]:
            if b[v] == 0:
                nb_empty += 1
            elif v in gid:
                t, k, n = gid[v]
                touch.setdefault(t, {})[k] = n
        if nb_empty == 0:
            e += w['hole']
        for t, d in touch.items():
            tot = sum(d.values())
            if len(d) >= 2 and tot >= 4:
                e += w['bridge5'] * (1 + 0.2 * (t - lo))
            elif tot >= 2:
                e += w['bridge4'] * 0.5
    # 높은 등급(새로 안 나오는 등급)끼리 가까이: 같은 등급 사이 거리 2 이내면 보너스, 빈칸 없이 갇히면 감점
    if w.get('hi_near', 0) or w.get('hi_stuck', 0):
        for t, gs in groups.items():
            if t <= hi:
                continue
            cells = [x for g in gs for x in g]
            for i in cells:
                if not any(b[v] == 0 for v in NB[i]):
                    e += w.get('hi_stuck', 0) * (t - hi)
            if len(gs) >= 2:
                for a in range(len(gs)):
                    for c in range(a + 1, len(gs)):
                        near = any(v in gs[c] for x in gs[a] for u in NB[x] for v in NB[u])
                        if near:
                            e += w.get('hi_near', 0) * (t - hi)
    # 3칸 조각이 들어갈 자리 수
    mob = 0
    for p in PL3:
        if b[p[0]] == 0 and b[p[1]] == 0 and b[p[2]] == 0:
            mob += 1
    e += w['mob'] * min(mob, 30)
    if mob == 0:
        e -= 60
    return e


def made_value(made, unlocked):
    hi = spawn_hi(unlocked)
    lo = max(1, hi - 2)
    v = 0.0
    for t, n, nt in made:
        v += 3 ** max(0, nt - lo) * 0.4 - 3 ** max(0, t - lo) * n * 0.1
        if nt - t >= 2:
            v += 6.0 * (1 + 0.3 * (nt - lo))
    return v


def unique_rots(offs):
    seen = {}
    for k in range(6):
        o = rot(offs, k)
        q0, r0 = o[0]
        key = tuple(sorted((q - q0, r - r0) for q, r in o))
        if key not in seen:
            seen[key] = k
    return list(seen.values())


def moves(b, piece, only_k0=False):
    """piece: [((q,r),tier),...] -> [(k, cells(tuple), tiers)]"""
    offs = [o for o, t in piece]
    ts = [t for o, t in piece]
    out = []
    ks = range(6) if len(set(ts)) > 1 else unique_rots(offs)
    if only_k0:
        ks = [0]
    seen = set()
    for k in ks:
        ro = rot(offs, k)
        for cells in placements(ro):
            if all(b[c] == 0 for c in cells):
                key = tuple(sorted(zip(cells, ts)))
                if key in seen:
                    continue
                seen.add(key)
                out.append((k, cells, ts))
    return out


def apply(b, cells, ts, choice=0, dot_cell=None):
    nb = list(b)
    for c, t in zip(cells, ts):
        nb[c] = t
    made, br = resolve(nb, list(cells), choice, dot_cell=dot_cell)
    return nb, made, br


def hammer(b, i):
    """b(list)의 i번째 칸을 빈칸(0)으로 파괴 (patch283: 망치 기능)"""
    nb = list(b)
    nb[i] = 0
    return nb


def new_unlocked(unlocked, made):
    for t, n, nt in made:
        if nt > unlocked:
            unlocked = nt
    return unlocked


def best_move(b, unlocked, piece, nxt=None, w=W, beam=18):
    """2수 탐색. 반환 (k, cells, ts, 점수)"""
    ms = moves(b, piece)
    if not ms:
        return None
    first = []
    for k, cells, ts in ms:
        outs = []
        nbr = 1
        ch = 0
        while ch < nbr:
            nb, made, nbr = apply(b, cells, ts, ch)
            u2 = new_unlocked(unlocked, made)
            outs.append((nb, made, u2))
            ch += 1
        sc = sum(made_value(m, unlocked) + evaluate(nb2, u2, w) for nb2, m, u2 in outs) / len(outs)
        first.append((sc, k, cells, ts, outs))
    first.sort(key=lambda x: -x[0])
    if not nxt:
        s, k, cells, ts, _ = first[0]
        return k, cells, ts, s
    best = None
    for sc, k, cells, ts, outs in first[:beam]:
        tot = 0.0
        for nb, made, u2 in outs:
            r1 = made_value(made, unlocked)
            ms2 = moves(nb, nxt)
            if not ms2:
                tot += r1 + evaluate(nb, u2, w) - 400
                continue
            bb = -1e9
            for k2, c2, t2 in ms2:
                nb2, m2, _ = apply(nb, c2, t2, 0)
                v = made_value(m2, u2) + evaluate(nb2, new_unlocked(u2, m2), w)
                if v > bb:
                    bb = v
            tot += r1 + bb
        tot /= len(outs)
        if best is None or tot > best[3]:
            best = (k, cells, ts, tot)
    return best


# ---------------- 시뮬레이터(전략 조정용) ----------------
SH2 = [[(0, 0), (1, 0)]]
SPAWN_W = [0.58, 0.22, 0.20]


def rand_piece(unlocked, rng):
    hi = spawn_hi(unlocked)
    lo = max(1, hi - 2)
    n = rng.choices([1, 2, 3], [0.37, 0.34, 0.29])[0]
    if n == 1:
        offs = [(0, 0)]
    elif n == 2:
        offs = rot([(0, 0), (1, 0)], rng.randrange(6))
    else:
        offs = list(rng.choice(SH3))
        offs = rot(offs, rng.randrange(6))
    # 실전 영상 75조각: 낮은 등급이 많이 나옴 (해금8: 4등급 60%, 5·6등급 각 20%)
    return [(o, rng.choices([lo, lo + 1, hi], SPAWN_W)[0] if hi - lo == 2 else rng.randint(lo, hi)) for o in offs]


def play(seed=0, w=W, beam=18, verbose=False, maxmoves=3000):
    rng = random.Random(seed)
    b = [0] * N
    unlocked = 3
    cur, nxt = rand_piece(unlocked, rng), rand_piece(unlocked, rng)
    moves_n = 0
    best_t = 0
    big = 0
    while moves_n < maxmoves:
        mv = best_move(b, unlocked, cur, nxt, w, beam)
        if mv is None:
            break
        k, cells, ts, _ = mv
        b, made, _ = apply(b, cells, ts, rng.randrange(6))
        unlocked = new_unlocked(unlocked, made)
        for t, n, nt in made:
            best_t = max(best_t, nt)
            if nt - t >= 2:
                big += 1
        moves_n += 1
        cur, nxt = nxt, rand_piece(unlocked, rng)
    return dict(moves=moves_n, best=best_t, unlocked=unlocked, big=big)


def _scored_moves(b, unlocked, piece, w):
    out = []
    for k, cells, ts in moves(b, piece):
        nb, made, nbr = apply(b, cells, ts, 0)
        u2 = new_unlocked(unlocked, made)
        out.append((made_value(made, unlocked) + evaluate(nb, u2, w), k, cells, ts, nb, u2, made))
    out.sort(key=lambda x: -x[0])
    return out


def best_move3(b, unlocked, piece, nxt=None, w=W, B1=10, B2=5, K=8, seed=0, only_k0=False, budget=None):
    """3수 탐색: 지금 조각, 다음 조각(알면), 그다음은 무작위 K개 평균.
    budget(초): 좋은 후보부터 계산하다 시간이 넘으면 거기서 멈춤(최소 3개는 계산, 1.3배 넘으면 즉시)"""
    import time as _t
    t_start = _t.time()
    rng = random.Random(seed)
    first = []
    for k, cells, ts in moves(b, piece, only_k0):
        outs = []
        nbr, ch = 1, 0
        while ch < nbr:
            nb, made, nbr = apply(b, cells, ts, ch)
            outs.append((nb, made, new_unlocked(unlocked, made)))
            ch += 1
        sc = sum(made_value(m, unlocked) + evaluate(nb2, u2, w) for nb2, m, u2 in outs) / len(outs)
        first.append((sc, k, cells, ts, outs))
    if not first:
        return None
    first.sort(key=lambda x: -x[0])
    best = None
    samples_cache = {}
    done = 0
    for sc, k, cells, ts, outs in first[:B1]:
        if budget and done >= 3 and _t.time() - t_start > budget:
            break
        done += 1
        tot = 0.0
        for nb, made, u2 in outs:
            r1 = made_value(made, unlocked)
            p2s = [nxt] if nxt else [rand_piece(u2, rng) for _ in range(K)]
            v2sum = 0.0
            for p2 in p2s:
                sm = _scored_moves(nb, u2, p2, w)
                if not sm:
                    v2sum += -400 + evaluate(nb, u2, w)
                    continue
                bestv2 = -1e9
                for s2, k2, c2, t2, nb2, u3, m2 in sm[:B2]:
                    r2 = made_value(m2, u2)
                    key = u3
                    if key not in samples_cache:
                        samples_cache[key] = [rand_piece(u3, rng) for _ in range(K)]
                    acc = 0.0
                    n3 = 0
                    for p3 in samples_cache[key]:
                        if budget and n3 >= 3 and _t.time() - t_start > 1.3 * budget:
                            break
                        n3 += 1
                        bb = -400 + evaluate(nb2, u3, w)
                        for k3, c3, t3 in moves(nb2, p3):
                            nb3, m3, _ = apply(nb2, c3, t3, 0)
                            v = made_value(m3, u3) + evaluate(nb3, new_unlocked(u3, m3), w)
                            if v > bb:
                                bb = v
                        acc += bb
                    v = r2 + acc / max(1, n3)
                    if v > bestv2:
                        bestv2 = v
                v2sum += bestv2
            tot += r1 + v2sum / len(p2s)
        tot /= len(outs)
        if best is None or tot > best[3]:
            best = (k, cells, ts, tot)
    return best


def play3(seed=0, w=W, maxmoves=3000, **kw):
    rng = random.Random(seed)
    b = [0] * N
    unlocked = 3
    cur, nxt = rand_piece(unlocked, rng), rand_piece(unlocked, rng)
    n = 0
    best_t = 0
    while n < maxmoves:
        mv = best_move3(b, unlocked, cur, nxt, w, seed=n, **kw)
        if mv is None:
            break
        k, cells, ts, _ = mv
        b, made, _ = apply(b, cells, ts, rng.randrange(6))
        unlocked = new_unlocked(unlocked, made)
        for t, nn, nt in made:
            best_t = max(best_t, nt)
        n += 1
        cur, nxt = nxt, rand_piece(unlocked, rng)
    return dict(moves=n, best=best_t, unlocked=unlocked)
