# -*- coding: utf-8 -*-
"""유물 공방 상한 실험 (Oracle Lookahead Benchmark)
시뮬레이터에서 봇에게 앞으로 나올 조각 N개(0, 1, 2, 3, 5)를 미리 알려 줬을 때
평균 판 길이(수)가 얼마나 늘어나는지 측정합니다.

사용법:
  py bench_oracle.py [판수]      (기본 100판, bench_oracle.bat 에서 실행)
"""
import os, sys, time, json, random, statistics
import multiprocessing as mp
from multiprocessing import shared_memory
import numpy as np

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
if MAC not in sys.path:
    sys.path.insert(0, MAC)

import hexa_engine as E
import hexa_nt as NT

OUT = os.path.join(TR, "bench_oracle_result.txt")
W_BIN = os.path.join(MAC, "hexa_nt_w.bin")
W_JSON = os.path.join(MAC, "hexa_nt_w.json")

# 실전과 동일한 조각 분포 (core4.inc / hexa_nt.py 기준: 1/2/3칸 = 29/36/35%, lo/lo+1/hi = 58/22/20%)
W_N = (0.29, 0.65)
W_T = (0.58, 0.80)


def say(*a):
    s = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


# ---------------- 빠른 조각 생성 (시드 고정, 해금 등급 u 에 맞춰 실현) ----------------
def gen_raw_stream(seed, length=4000):
    """판마다 미리 난수 스트림을 만들어 두어 N=0,1,2,3,5 비교 시 완전히 같은 조각 순서가 나오게 함"""
    rng = random.Random(seed)
    stream = []
    for _ in range(length):
        x = rng.random()
        if x < W_N[0]:
            offs = [(0, 0)]
        elif x < W_N[1]:
            offs = E.rot([(0, 0), (1, 0)], rng.randrange(6))
        else:
            offs = E.rot(list(rng.choice(E.SH3)), rng.randrange(6))
        ys = [rng.random() for _ in range(len(offs))]
        ch_rnd = rng.randrange(6)
        stream.append((offs, ys, ch_rnd))
    return stream


def realize_piece(raw, u):
    offs, ys, _ = raw
    hi = E.spawn_hi(u)
    lo = max(1, hi - 2)
    if hi - lo == 2:
        return [(o, lo if y < W_T[0] else (lo + 1 if y < W_T[1] else hi)) for o, y in zip(offs, ys)]
    else:
        span = hi - lo + 1
        return [(o, lo + int(y * span)) for o, y in zip(offs, ys)]


# ---------------- 빠른 수 생성 및 적용 ----------------
_SHAPE_MOVES = {}


def get_piece_moves(piece, only_k0=False):
    """piece: [((q,r), t), ...] -> [(k, cells_tuple, ts_tuple), ...]"""
    key = (tuple(piece), only_k0)
    res = _SHAPE_MOVES.get(key)
    if res is not None:
        return res
    res = E.moves([0] * E.N, piece, only_k0=only_k0)
    _SHAPE_MOVES[key] = res
    return res


def fast_outs(b, u, cells, ts):
    """합침 가능성 여부를 먼저 검사해 합침이 없는 수(~75%)는 즉시 처리"""
    n = len(cells)
    can_merge = (n == 3 and ts[0] == ts[1] == ts[2])
    if not can_merge:
        for i in range(n):
            c = cells[i]
            t = ts[i]
            for v in E.NB[c]:
                if b[v] == t:
                    can_merge = True
                    break
            if can_merge:
                break
    if not can_merge:
        nb = list(b)
        for i in range(n):
            nb[cells[i]] = ts[i]
        return [(nb, 1.0, u)]
    res = []
    nbr, ch = 1, 0
    while ch < nbr:
        nb, made, nbr = E.apply(b, cells, ts, ch)
        u2 = E.new_unlocked(u, made)
        r = 1.0 + 0.002 * float(sum(1 << nt for _, _, nt in made))
        res.append((nb, r, u2))
        ch += 1
    return res


# ---------------- 공유 메모리 기반 n-tuple 평가 ----------------
_G_TABS = None
_G_INST = None
_G_SHM = None


def init_worker(shm_name, meta):
    global _G_TABS, _G_INST, _G_SHM
    _G_SHM = shared_memory.SharedMemory(name=shm_name)
    raw = np.ndarray((meta["total_floats"],), dtype=np.float32, buffer=_G_SHM.buf)
    tabs, off = [], 0
    for cells in meta["base"]:
        n = (9 ** len(cells))
        tabs.append(raw[off:off + n])
        off += n
    inst = []
    for ti, cells in enumerate(meta["base"]):
        for s in meta["sym"]:
            inst.append((ti, [s[c] for c in cells]))
    _G_TABS = tabs
    _G_INST = inst


def eval_boards(boards, us):
    if not boards:
        return np.zeros(0, dtype=np.float64)
    b = np.asarray(boards, dtype=np.int64)
    u_arr = np.asarray(us, dtype=np.int64)
    hi = np.clip(u_arr - 1, 2, 6)
    lo = np.maximum(1, hi - 2)[:, None]
    e = np.where(b == 0, 0, np.where(b < lo, 1, np.minimum(b - lo + 2, 8)))
    v = np.zeros(len(boards), dtype=np.float64)
    for ti, cells in _G_INST:
        idx = e[:, cells[0]].copy()
        for c in cells[1:]:
            idx = idx * 9 + e[:, c]
        v += _G_TABS[ti][idx]
    return v


# ---------------- N개 미래 조각 오라클 탐색 ----------------
def choose_move_oracle(b, u, stream, mv_idx, n_future, B1=16, B=8, plus_chance_k=0):
    """
    n_future: 미리 알려 주는 미래 조각 수 (0 = 지금 조각만, 1 = 오른쪽 상자 1개, 3 = 앞으로 3개, 5 = 앞으로 5개)
    plus_chance_k: 마지막 알려진 조각 뒤에 무작위 조각 K개 평균(1수)을 더 볼지 여부 (현재 봇 = n_future=1, plus_chance_k=8)
    """
    p0 = realize_piece(stream[mv_idx], u)
    ms0 = [m for m in get_piece_moves(p0) if all(b[c] == 0 for c in m[1])]
    if not ms0:
        return None

    # 1수(지금 조각) 전개 및 평가
    first = []
    boards, us, tags = [], [], []
    for mi, (k, cells, ts) in enumerate(ms0):
        outs = fast_outs(b, u, cells, ts)
        first.append((k, cells, ts, outs))
        for oi, (nb, r1, u1) in enumerate(outs):
            boards.append(nb)
            us.append(u1)
            tags.append((mi, oi, r1))

    vs = eval_boards(boards, us)
    sc0 = [0.0] * len(first)
    branch_scores = {}
    for (mi, oi, r1), v in zip(tags, vs):
        branch_scores[(mi, oi)] = r1 + float(v)
        sc0[mi] += (r1 + float(v)) / len(first[mi][3])

    if n_future == 0 and plus_chance_k == 0:
        best_mi = max(range(len(first)), key=lambda i: sc0[i])
        k, cells, ts, _ = first[best_mi]
        return k, cells, ts

    # 상위 B1개 루트 후보 선택
    ord_mi = sorted(range(len(first)), key=lambda i: -sc0[i])[:B1]

    # 각 루트 후보의 갈림(oi)별로 (누적보상, board, u) 빔 유지
    # beams[(mi, oi)] = [(점수, 누적보상, nb, u_cur), ...]
    beams = {}
    for mi in ord_mi:
        outs = first[mi][3]
        for oi, (nb, r1, u1) in enumerate(outs):
            beams[(mi, oi)] = [(branch_scores[(mi, oi)], r1, nb, u1)]

    # step = 1 .. n_future (알려진 미래 조각 p_1 .. p_{n_future} 순서대로 배치)
    for step in range(1, n_future + 1):
        raw_step = stream[mv_idx + step]
        exp_boards, exp_us, exp_meta = [], [], []
        dead_keys = []
        for key, state_list in beams.items():
            for si, (_, cum_r, nb, u_cur) in enumerate(state_list):
                if nb is None:
                    dead_keys.append((key, si, cum_r))
                    continue
                p_step = realize_piece(raw_step, u_cur)
                ms = [m for m in get_piece_moves(p_step) if all(nb[c] == 0 for c in m[1])]
                if not ms:
                    dead_keys.append((key, si, cum_r))
                    continue
                for m_idx, (_, c_step, t_step) in enumerate(ms):
                    outs_s = fast_outs(nb, u_cur, c_step, t_step)
                    n_br = len(outs_s)
                    for br_i, (nb2, r_s, u2) in enumerate(outs_s):
                        exp_boards.append(nb2)
                        exp_us.append(u2)
                        exp_meta.append((key, si, m_idx, n_br, cum_r + r_s, nb2, u2))

        vs_step = eval_boards(exp_boards, exp_us) if exp_boards else []

        # (key, si, m_idx) 별로 갈림 평균 계산
        move_acc = {}
        for (key, si, m_idx, n_br, new_cum_r, nb2, u2), v in zip(exp_meta, vs_step):
            mk = (key, si, m_idx)
            tot_v = new_cum_r + float(v)
            if mk not in move_acc:
                move_acc[mk] = [tot_v / n_br, new_cum_r / n_br, nb2, u2]
            else:
                move_acc[mk][0] += tot_v / n_br
                move_acc[mk][1] += new_cum_r / n_br

        new_beams = {key: [] for key in beams}
        for (key, si, m_idx), (tot_v, new_cum_r, nb2, u2) in move_acc.items():
            new_beams[key].append((tot_v, new_cum_r, nb2, u2))
        for key, si, cum_r in dead_keys:
            new_beams[key].append((cum_r, cum_r, None, 0))

        is_last = (step == n_future and plus_chance_k == 0)
        keep = 1 if is_last else B
        for key, cand_list in new_beams.items():
            if not cand_list:
                beams[key] = [(0.0, 0.0, None, 0)]
            else:
                cand_list.sort(key=lambda x: -x[0])
                beams[key] = cand_list[:keep]

    # plus_chance_k > 0 이면 마지막에 무작위 조각 K개 평균 1수 추가 (현재 봇의 3수 탐색 구조)
    if plus_chance_k > 0:
        rng = random.Random((mv_idx + 1) * 1000003)
        # 해금 등급별 무작위 조각 K개 미리 샘플링 (공정 비교 CRN)
        samp_by_u = {}
        exp_boards, exp_us, exp_meta = [], [], []
        for key, state_list in beams.items():
            for si, (est_v, cum_r, nb, u_cur) in enumerate(state_list):
                if nb is None:
                    continue
                if u_cur not in samp_by_u:
                    samp_by_u[u_cur] = [NT.rand_piece(u_cur, rng) for _ in range(plus_chance_k)]
                for ki, pk in enumerate(samp_by_u[u_cur]):
                    ms = [m for m in get_piece_moves(pk) if all(nb[c] == 0 for c in m[1])]
                    if not ms:
                        continue
                    for m_idx, (_, ck, tk) in enumerate(ms):
                        outs_k = fast_outs(nb, u_cur, ck, tk)
                        n_br = len(outs_k)
                        for _, (nb3, rk, u3) in enumerate(outs_k):
                            exp_boards.append(nb3)
                            exp_us.append(u3)
                            exp_meta.append((key, si, ki, m_idx, n_br, rk))
        vs_ch = eval_boards(exp_boards, exp_us) if exp_boards else []
        ch_move = {}
        for (key, si, ki, m_idx, n_br, rk), v in zip(exp_meta, vs_ch):
            mk = (key, si, ki, m_idx)
            ch_move[mk] = ch_move.get(mk, 0.0) + (rk + float(v)) / n_br
        ch_best = {}
        for (key, si, ki, m_idx), val in ch_move.items():
            ck = (key, si, ki)
            if ck not in ch_best or val > ch_best[ck]:
                ch_best[ck] = val
        for key, state_list in beams.items():
            best_si = -1e18
            for si, (est_v, cum_r, nb, u_cur) in enumerate(state_list):
                if nb is None:
                    val = cum_r
                else:
                    acc = sum(ch_best.get((key, si, ki), 0.0) for ki in range(plus_chance_k))
                    val = cum_r + acc / plus_chance_k
                if val > best_si:
                    best_si = val
            beams[key] = [(best_si, 0.0, None, 0)]

    # 각 루트 후보 mi 의 최종 점수 = 갈림 oi 평균
    best_mi = ord_mi[0]
    best_val = -1e18
    for mi in ord_mi:
        outs = first[mi][3]
        tot = sum(beams[(mi, oi)][0][0] for oi in range(len(outs))) / len(outs)
        if tot > best_val:
            best_val = tot
            best_mi = mi

    k, cells, ts, _ = first[best_mi]
    return k, cells, ts


def play_one_game(args):
    game_idx, seed_base, n_future, B1, B, plus_chance_k = args
    stream = gen_raw_stream(seed_base + game_idx, length=3500)
    b = [0] * E.N
    u = 3
    mv_idx = 0
    best_t = 3
    while mv_idx < 3000:
        mv = choose_move_oracle(b, u, stream, mv_idx, n_future, B1=B1, B=B, plus_chance_k=plus_chance_k)
        if mv is None:
            break
        k, cells, ts = mv
        ch_rnd = stream[mv_idx][2]
        b, made, _ = E.apply(b, cells, ts, ch_rnd)
        u = E.new_unlocked(u, made)
        for _, _, nt in made:
            if nt > best_t:
                best_t = nt
        mv_idx += 1
    return mv_idx, best_t


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    workers = min(12, max(2, (os.cpu_count() or 4) - 2))
    seed_base = 20261024

    NT._ensure_bin()
    meta = json.load(open(W_JSON, encoding="utf-8"))
    raw = np.fromfile(W_BIN, dtype=np.float32)
    meta["total_floats"] = len(raw)

    shm = shared_memory.SharedMemory(create=True, size=raw.nbytes)
    shm_arr = np.ndarray(raw.shape, dtype=np.float32, buffer=shm.buf)
    shm_arr[:] = raw[:]
    del raw

    # 비교할 설정:
    # (이름, n_future, B1, B, plus_chance_k)
    # 참고: 동일 시드 24판에서 '현재 봇(N=1 확정 + 3수째 확률평균 K=8)'은 평균 180.1수 (C 100판 벤치에서도 180.1수)
    configs = [
        ("N=0 (지금 조각만, 1수)", 0, 16, 8, 0),
        ("N=1 (다음 1개 확정, 2수 = 오른쪽 상자만)", 1, 16, 8, 0),
        ("N=2 (다음 2개 확정, 3수 = 상자+1개 더)", 2, 16, 8, 0),
        ("N=3 (다음 3개 확정, 4수 = 상자+2개 더)", 3, 16, 8, 0),
        ("N=5 (다음 5개 확정, 6수 = 상자+4개 더)", 5, 16, 8, 0),
    ]
    if "--with-chance" in sys.argv:
        configs.insert(2, ("현재 봇 (N=1 확정 + 3수째 확률평균 K=8)", 1, 16, 8, 8))

    say("=== 유물 공방 미래 조각 N개 사전 인지 상한 실험 시작 (%d판, 워커 %d개) ===" % (games, workers))
    try:
        with mp.Pool(processes=workers, initializer=init_worker, initargs=(shm.name, meta)) as pool:
            results = {}
            for name, nf, b1, b, pck in configs:
                t0 = time.time()
                tasks = [(g, seed_base, nf, b1, b, pck) for g in range(games)]
                out = pool.map(play_one_game, tasks)
                mvs = [x[0] for x in out]
                bests = [x[1] for x in out]
                avg_mv = statistics.mean(mvs)
                med_mv = statistics.median(mvs)
                r9 = 100.0 * sum(1 for x in bests if x >= 9) / games
                r10 = 100.0 * sum(1 for x in bests if x >= 10) / games
                el = time.time() - t0
                results[name] = avg_mv
                say("  %-40s : 평균 %6.1f수 (중앙값 %5.1f, ★9+ %4.0f%%, ★10 %4.0f%%) [%.1f초]" %
                    (name, avg_mv, med_mv, r9, r10, el))

            base_n1 = results["N=1 (다음 1개 확정, 2수 = 오른쪽 상자만)"]
            base_cur = results.get("현재 봇 (N=1 확정 + 3수째 확률평균 K=8)", 180.1)
            say("--- 요약 (기준: N=1 2수 확정 = %.1f수 / 현재 3수 봇 = %.1f수) ---" % (base_n1, base_cur))
            for name, _, _, _, _ in configs:
                v = results[name]
                say("  %-40s : %6.1f수 | N=1(2수) 대비 %+5.1f%% | 현재 봇(3수) 대비 %+5.1f%%" %
                    (name, v, (v / base_n1 - 1) * 100, (v / base_cur - 1) * 100))
    finally:
        shm.close()
        shm.unlink()


if __name__ == "__main__":
    mp.freeze_support()
    main()
