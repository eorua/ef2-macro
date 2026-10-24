# -*- coding: utf-8 -*-
"""patch233: 튜플 구성을 hexa_nt_w.json/.tup 로 (PC 큰 두뇌 학습 결과 bin 을 바로 씀).
patch232: 보상 = 오래 버티기(한 수마다 1 + 0.002x등급점수). 가중치 meta 의 reward 로 자동 선택(없으면 예전 2^등급).
patch231: 유물 공방 n-tuple 학습 평가로 수 고르기.
가중치 hexa_nt_w.npz (Claude 쪽에서 가상 대전 수백만 판으로 TD 학습, 규칙은 hexa_engine 과 같음)
탐색: best_move3 = 지금 조각 x 다음 조각(미리보기) x 그다음 무작위 8개 평균(3수), 합쳐질 칸 갈림은 평균. 다음 조각 모르면 1수."""
import os
import json
import numpy as np
import hexa_engine as E

HERE = os.path.dirname(os.path.abspath(__file__))
NV = 9
_W = None


def _paths():
    return (os.path.join(HERE, "hexa_nt_w.bin"), os.path.join(HERE, "hexa_nt_w.json"),
            os.path.join(HERE, "hexa_nt_w.npz"))


def _use_bin():
    """patch233: hexa_nt_w.bin + .json(튜플·대칭·보상)이 npz 보다 새로우면 그것을 씀(PC 학습 결과)"""
    bn, js, nz = _paths()
    if not (os.path.exists(bn) and os.path.exists(js)):
        return False
    return (not os.path.exists(nz)) or os.path.getmtime(bn) >= os.path.getmtime(nz) - 1


def _meta():
    bn, js, nz = _paths()
    if _use_bin():
        return json.load(open(js, encoding="utf-8"))
    z = np.load(nz)
    return json.loads(str(z["meta"]))


def _load():
    global _W, _RMODE, _BONUS
    if _W is None:
        bn, js, nz = _paths()
        if _use_bin():
            meta = json.load(open(js, encoding="utf-8"))
            raw = np.fromfile(bn, dtype=np.float32)
            tabs, off = [], 0
            for cells in meta["base"]:
                n = NV ** len(cells)
                tabs.append(raw[off:off + n])
                off += n
            if off != len(raw):
                raise RuntimeError("hexa_nt_w.bin 크기가 튜플 구성과 다름")
        else:
            z = np.load(nz)
            meta = json.loads(str(z["meta"]))
            tabs = [z["t%d" % i] for i in range(len(meta["base"]))]
        inst = []  # (표 번호, 칸 목록)
        for ti, cells in enumerate(meta["base"]):
            for s in meta["sym"]:
                inst.append((ti, [s[c] for c in cells]))
        _W = (tabs, inst)
        rm = meta.get("reward") or {}
        _RMODE = 1 if rm.get("mode") == "survive" else 0
        _BONUS = float(rm.get("bonus", 0.002))
    return _W


def _reward_meta():
    """표를 읽지 않고 보상 모드만"""
    global _RMODE, _BONUS
    rm = _meta().get("reward") or {}
    _RMODE = 1 if rm.get("mode") == "survive" else 0
    _BONUS = float(rm.get("bonus", 0.002))


def available():
    bn, js, nz = _paths()
    return os.path.exists(nz) or (os.path.exists(bn) and os.path.exists(js))


def _enc(boards, us):
    """boards: (n,23) int, us: (n,) -> (n,23) 인코딩"""
    b = np.asarray(boards, dtype=np.int64)
    lo = np.array([max(1, E.spawn_hi(u) - 2) for u in us], dtype=np.int64)[:, None]
    e = np.where(b == 0, 0, np.where(b < lo, 1, np.minimum(b - lo + 2, 8)))
    return e


def values(boards, us):
    if not boards:
        return np.zeros(0)
    tabs, inst = _load()
    e = _enc(boards, us)
    v = np.zeros(len(boards))
    for ti, cells in inst:
        idx = np.zeros(len(boards), dtype=np.int64)
        for c in cells:
            idx = idx * NV + e[:, c]
        v += tabs[ti][idx]
    return v


_RMODE = None
_BONUS = 0.002


def reward(made):
    if _RMODE is None:
        _reward_meta()
    raw = float(sum(2 ** nt for t, n, nt in made))
    return 1.0 + _BONUS * raw if _RMODE else raw


def _outs(b, u, cells, ts):
    res = []
    nbr, ch = 1, 0
    while ch < nbr:
        nb, made, nbr = E.apply(b, cells, ts, ch)
        res.append((nb, made, E.new_unlocked(u, made)))
        ch += 1
    return res


def best_move(b, unlocked, piece, nxt=None, only_k0=False):
    """반환 (k, cells, ts, 점수) 또는 None. b 의 모르는 칸(<0)은 호출 쪽에서 처리된 판을 넘길 것"""
    ms = E.moves(b, piece, only_k0)
    if not ms:
        return None
    first = [(k, cells, ts, _outs(b, unlocked, cells, ts)) for k, cells, ts in ms]
    if not nxt:
        boards, us, own = [], [], []
        for mi, (k, cells, ts, outs) in enumerate(first):
            for nb, made, u2 in outs:
                boards.append(nb); us.append(u2); own.append((mi, reward(made), len(outs)))
        vs = values(boards, us)
        sc = [0.0] * len(first)
        for (mi, r, n), v in zip(own, vs):
            sc[mi] += (r + v) / n
        i = max(range(len(first)), key=lambda j: sc[j])
        k, cells, ts, _ = first[i]
        return k, cells, ts, sc[i]
    # 2수: 모든 (1수 결과, 2수 결과) 판을 한 번에 평가
    boards, us, tag = [], [], []
    dead = []  # 다음 조각을 못 놓는 1수 결과
    for mi, (k, cells, ts, outs) in enumerate(first):
        for oi, (nb, made, u2) in enumerate(outs):
            ms2 = E.moves(nb, nxt)
            if not ms2:
                dead.append((mi, oi))
                continue
            for m2i, (k2, c2, t2) in enumerate(ms2):
                for nb2, m2, u3 in _outs(nb, u2, c2, t2):
                    boards.append(nb2); us.append(u3); tag.append((mi, oi, m2i, reward(m2)))
    vs = values(boards, us) if boards else []
    # (mi,oi,m2i) -> 갈림 평균
    acc = {}
    for (mi, oi, m2i, r2), v in zip(tag, vs):
        a = acc.setdefault((mi, oi, m2i), [0.0, 0])
        a[0] += r2 + v
        a[1] += 1
    best2 = {}
    for (mi, oi, m2i), (s, n) in acc.items():
        x = s / n
        if (mi, oi) not in best2 or x > best2[(mi, oi)]:
            best2[(mi, oi)] = x
    for key in dead:
        best2[key] = 0.0
    sc = []
    for mi, (k, cells, ts, outs) in enumerate(first):
        s = 0.0
        for oi, (nb, made, u2) in enumerate(outs):
            s += reward(made) + best2[(mi, oi)]
        sc.append(s / len(outs))
    i = max(range(len(first)), key=lambda j: sc[j])
    k, cells, ts, _ = first[i]
    return k, cells, ts, sc[i]


# ---------------- 3수 (지금 -> 다음(앎) -> 그다음 무작위 K개 평균) ----------------
import random as _random


def rand_piece(unlocked, rng):
    """학습 때와 같은 분포: 1/2/3칸 29/36/35%, 등급 lo 58% / lo+1 22% / hi 20%"""
    hi = E.spawn_hi(unlocked)
    lo = max(1, hi - 2)
    x = rng.random()
    n = 1 if x < 0.29 else (2 if x < 0.65 else 3)
    if n == 1:
        offs = [(0, 0)]
    elif n == 2:
        offs = E.rot([(0, 0), (1, 0)], rng.randrange(6))
    else:
        offs = E.rot(list(rng.choice(E.SH3)), rng.randrange(6))
    out = []
    for o in offs:
        if hi - lo == 2:
            y = rng.random()
            t = lo if y < 0.58 else (lo + 1 if y < 0.80 else hi)
        else:
            t = rng.randint(lo, hi)
        out.append((o, t))
    return out


def _one_ply(b, u, piece):
    """[(평균점수, k, cells, ts, outs)] 1수 평가(갈림 평균)"""
    ms = E.moves(b, piece)
    first = [(k, cells, ts, _outs(b, u, cells, ts)) for k, cells, ts in ms]
    boards, us, own = [], [], []
    for mi, (k, cells, ts, outs) in enumerate(first):
        for nb, made, u2 in outs:
            boards.append(nb); us.append(u2); own.append((mi, reward(made), len(outs)))
    vs = values(boards, us)
    sc = [0.0] * len(first)
    for (mi, r, n), v in zip(own, vs):
        sc[mi] += (r + v) / n
    return [(sc[i],) + first[i] for i in range(len(first))]


def best_move3(b, unlocked, piece, nxt, only_k0=False, B1=8, B2=6, K=8, seed=0, budget=8.0):
    import time as _t
    t0 = _t.time()
    two = best_move_scores(b, unlocked, piece, nxt, only_k0)
    if not two:
        return None
    two.sort(key=lambda x: -x[0])
    rng = _random.Random(seed)
    best = (two[0][1], two[0][2], two[0][3], two[0][0])
    best_v = None
    done = 0
    for sc2, k, cells, ts, outs in two[:B1]:
        if done >= 2 and _t.time() - t0 > budget:
            break
        done += 1
        tot = 0.0
        for nb, made, u2 in outs:
            cand = _one_ply(nb, u2, nxt)
            if not cand:
                tot += reward(made)
                continue
            cand.sort(key=lambda x: -x[0])
            bestv2 = -1e18
            for s2, k2, c2, t2, outs2 in cand[:B2]:
                acc2 = 0.0
                for nb2, m2, u3 in outs2:
                    acc = 0.0
                    for _ in range(K):
                        p3 = rand_piece(u3, rng)
                        sm = _one_ply(nb2, u3, p3)
                        acc += max(x[0] for x in sm) if sm else 0.0
                    acc2 += reward(m2) + acc / K
                v2 = acc2 / len(outs2)
                if v2 > bestv2:
                    bestv2 = v2
            tot += reward(made) + bestv2
        v = tot / len(outs)
        if best_v is None or v > best_v:
            best_v = v
            best = (k, cells, ts, v)
    return best


def best_move_scores(b, unlocked, piece, nxt, only_k0=False):
    """2수 점수 목록 [(점수, k, cells, ts, outs)]"""
    ms = E.moves(b, piece, only_k0)
    if not ms:
        return []
    first = [(k, cells, ts, _outs(b, unlocked, cells, ts)) for k, cells, ts in ms]
    boards, us, tag, dead = [], [], [], []
    for mi, (k, cells, ts, outs) in enumerate(first):
        for oi, (nb, made, u2) in enumerate(outs):
            ms2 = E.moves(nb, nxt)
            if not ms2:
                dead.append((mi, oi))
                continue
            for m2i, (k2, c2, t2) in enumerate(ms2):
                for nb2, m2, u3 in _outs(nb, u2, c2, t2):
                    boards.append(nb2); us.append(u3); tag.append((mi, oi, m2i, reward(m2)))
    vs = values(boards, us) if boards else []
    acc = {}
    for (mi, oi, m2i, r2), v in zip(tag, vs):
        a = acc.setdefault((mi, oi, m2i), [0.0, 0])
        a[0] += r2 + v
        a[1] += 1
    best2 = {}
    for (mi, oi, m2i), (s, n) in acc.items():
        x = s / n
        if (mi, oi) not in best2 or x > best2[(mi, oi)]:
            best2[(mi, oi)] = x
    for key in dead:
        best2[key] = 0.0
    out = []
    for mi, (k, cells, ts, outs) in enumerate(first):
        s = sum(reward(made) + best2[(mi, oi)] for oi, (nb, made, u2) in enumerate(outs)) / len(outs)
        out.append((s, k, cells, ts, outs))
    return out


# ---------------- patch232: C 수 읽기 (hexa_search.exe + hexa_nt_w.bin) ----------------
import subprocess as _sp
_CP = None


def _exe_path():
    if os.name == "nt":
        # patch244: 낮은 등급 벌점(c_deadp)을 아는 새 수 읽기가 있으면 그것 (벌점 0 이면 예전과 같음)
        v2 = os.path.join(HERE, "hexa_search_v2.exe")
        v3 = os.path.join(HERE, "hexa_search_v3.exe")   # patch246: v2 + 3수째 조각 전부 가중평균(c_exact). 끄면 v2 와 같음
        if os.path.exists(v3):
            return v3
        return v2 if os.path.exists(v2) else os.path.join(HERE, "hexa_search.exe")
    return os.path.join(HERE, "hs")


def c_available():
    return os.path.exists(_exe_path()) and available()


def _ensure_bin():
    """C 용 hexa_nt_w.bin(+.tup, .json)이 없거나 npz 가 더 새로우면 npz 에서 만듦"""
    bn, js, nz = _paths()
    if _use_bin():
        _write_tup(json.load(open(js, encoding="utf-8")), bn)
        return bn
    z = np.load(nz)
    meta = json.loads(str(z["meta"]))
    tmp = bn + ".tmp"
    with open(tmp, "wb") as f:
        for i in range(len(meta["base"])):
            np.asarray(z["t%d" % i], dtype=np.float32).tofile(f)
    os.replace(tmp, bn)
    json.dump(meta, open(js, "w", encoding="utf-8"))
    _write_tup(meta, bn)
    return bn


def _write_tup(meta, bn):
    tf = bn + ".tup"
    txt = "%d\n" % len(meta["base"]) + "".join("%d %s\n" % (len(c), " ".join(map(str, c))) for c in meta["base"])
    if not os.path.exists(tf) or open(tf).read() != txt:
        open(tf, "w").write(txt)


def _cproc():
    global _CP
    if _CP is not None and _CP.poll() is None:
        return _CP
    bn = _ensure_bin()
    _reward_meta()
    env = dict(os.environ)
    env["RMODE"] = str(_RMODE)
    # patch242: 깊은 수 읽기 설정 (hexa_cfg.json 의 c_crn / c_K2 / c_B2)
    try:
        _cfg = json.load(open(os.path.join(HERE, "hexa_cfg.json"), encoding="utf-8"))
    except Exception:
        _cfg = {}
    for _k, _e in (("c_crn", "CRN"), ("c_K2", "K2"), ("c_B2", "B2")):
        if _k in _cfg:
            env[_e] = str(int(_cfg[_k]))
    # patch244: 낮은 등급(1~c_deadg 성) 칸 벌점 (hexa_cfg.json 의 c_deadp / c_deadg, bench_dead 가 정함)
    if _cfg.get("c_deadp"):
        env["DEADP"] = str(float(_cfg["c_deadp"]))
        env["DEADG"] = str(int(_cfg.get("c_deadg", 3)))
    # patch246: 3수째(첫 무작위 단계) 조각을 표본 K개 대신 모든 경우 가중평균 (hexa_cfg.json c_exact, bench_exact 가 정함)
    if _cfg.get("c_exact"):
        env["EXACT"] = "1"
    kw = {}
    if os.name == "nt":
        # 창 없이, 낮은 우선순위로 (다른 프로그램·블루스택 방해 최소화)
        kw["creationflags"] = 0x08000000 | 0x00004000
    _CP = _sp.Popen([_exe_path(), bn], stdin=_sp.PIPE, stdout=_sp.PIPE,
                    text=True, env=env, cwd=HERE, **kw)
    first = _CP.stdout.readline().strip()
    if first != "READY":
        _CP.kill()
        _CP = None
        raise RuntimeError("hexa_search 시작 실패: %r" % first)
    return _CP


def best_move_c(b, unlocked, piece, nxt, only_k0=False, D=3, B=8, K=8, budget_ms=4000, threads=6, seed=0):
    """반환 (k, cells, ts, 점수, 정보) / None(둘 곳 없음). 실패하면 예외 -> 호출 쪽에서 Python 탐색으로"""
    p = _cproc()
    enc = lambda pc: [str(len(pc))] + ["%d %d %d" % (o[0], o[1], t) for o, t in pc]
    line = " ".join([str(unlocked)] + [str(int(x)) for x in b] + enc(piece) + enc(nxt or []) +
                    [str(D), str(B), str(K), "1" if only_k0 else "0", str(int(budget_ms)), str(threads), str(seed)])
    p.stdin.write(line + "\n")
    p.stdin.flush()
    r = p.stdout.readline().split()
    if not r:
        raise RuntimeError("hexa_search 응답 없음")
    if r[0] == "NONE":
        return None
    if r[0] != "OK":
        raise RuntimeError("hexa_search: " + " ".join(r))
    n = int(r[1])
    cells = [int(r[2 + 2 * i]) for i in range(n)]
    ts = [int(r[3 + 2 * i]) for i in range(n)]
    key = tuple(sorted(zip(cells, ts)))
    for k, c2, t2 in E.moves(b, piece, only_k0):
        if tuple(sorted(zip(c2, t2))) == key:
            return k, c2, t2, float(r[2 + 2 * n]), "C D%d %s후보 %sms" % (D, r[3 + 2 * n], r[4 + 2 * n])
    raise RuntimeError("hexa_search 수를 목록에서 못 찾음")


def c_close():
    global _CP
    if _CP is not None:
        try:
            _CP.kill()
        except Exception:
            pass
        _CP = None
