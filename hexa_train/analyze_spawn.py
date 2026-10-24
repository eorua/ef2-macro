# -*- coding: utf-8 -*-
r"""유물 공방 조각 출현 규칙 가설 검정 스크립트
대상 파일:
  1. C:\macro\shots\hexa_learn.jsonl (383줄: 갈림 합침 target 354줄 + mismatch 29줄)
  2. C:\macro\shots\hexa_spawn.jsonl (287줄: patch246 이후 2판의 모든 수 연속 기록 285수)
"""
import os, sys, json, math, collections
import numpy as np

TR = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.dirname(TR)
if MAC not in sys.path:
    sys.path.insert(0, MAC)

import hexa_engine as E

LEARN_PATH = os.path.join(MAC, "shots", "hexa_learn.jsonl")
SPAWN_PATH = os.path.join(MAC, "shots", "hexa_spawn.jsonl")


def norm_offs(offs):
    """축좌표 목록을 첫 칸(사전순 최소) 기준으로 정규화"""
    s = sorted((int(q), int(r)) for q, r in offs)
    q0, r0 = s[0]
    return tuple((q - q0, r - r0) for q, r in s)


def canon_shape(offs):
    """회전 대칭을 묶은 5가지 기본 모양 분류 및 회전 방향(0..5)"""
    n = len(offs)
    if n == 1:
        return "1칸", 0
    if n == 2:
        no = norm_offs(offs)
        for k in range(6):
            ro = norm_offs(E.rot([(0, 0), (1, 0)], k))
            if ro == no:
                return "2칸", k % 3
        return "2칸", 0
    # 3칸: 직선 / 삼각 / 꺾임 구분
    # 세 칸 사이의 인접(거리 1) 쌍 개수 세기
    s = [(int(q), int(r)) for q, r in offs]
    adj = 0
    for i in range(3):
        for j in range(i + 1, 3):
            dq = s[i][0] - s[j][0]
            dr = s[i][1] - s[j][1]
            if (dq, dr) in E.DIRS:
                adj += 1
    if adj == 3:
        kind = "3칸-삼각"
        base = [(0, 0), (1, 0), (0, 1)]
        sym = 2
    else:
        # 직선인지 확인: 양 끝점 중점 == 가운데 점
        ss = sorted(s)
        if ss[0][0] + ss[2][0] == 2 * ss[1][0] and ss[0][1] + ss[2][1] == 2 * ss[1][1]:
            kind = "3칸-직선"
            base = [(0, 0), (1, 0), (2, 0)]
            sym = 3
        else:
            kind = "3칸-꺾임"
            base = [(0, 0), (1, 0), (1, 1)]
            sym = 6
    no = norm_offs(offs)
    for k in range(6):
        if norm_offs(E.rot(base, k)) == no:
            return kind, k % sym
    return kind, 0


def chi2_sf(x, df):
    """카이제곱 분포 우측 꼬리 확률 P(Chi2_df >= x) 근사 (정규/감마 급수)"""
    if x <= 0 or df <= 0:
        return 1.0
    # Wilson-Hilferty 근사 (df >= 1 에서 매우 정확)
    z = ((x / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / math.sqrt(2.0 / (9.0 * df))
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def norm_sf_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def load_learn():
    rows = [json.loads(line) for line in open(LEARN_PATH, encoding="utf-8") if line.strip()]
    # 시간 간격(> 300초) 또는 판 리셋으로 판(game) 분리
    games = []
    cur_g = []
    last_t = None
    for r in rows:
        t = r.get("t", 0)
        if last_t is not None and t - last_t > 300:
            if cur_g:
                games.append(cur_g)
            cur_g = []
        cur_g.append(r)
        last_t = t
    if cur_g:
        games.append(cur_g)

    parsed = []
    for gi, g in enumerate(games):
        # 판 안에서 추정한 해금 최고 등급(board 및 조각의 최고 등급 누적)
        u_est = 3
        for mi, r in enumerate(g):
            b = r["board"]
            for x in b:
                if x > u_est:
                    u_est = x
            if "meta" in r and "spawn" in r["meta"]:
                sp = r["meta"]["spawn"]
                offs = [tuple(o) for o, t in sp]
                ts = [int(t) for o, t in sp]
                has_spawn = True
                taps = r["meta"].get("taps", 0)
            else:
                cells = r["cells"]
                offs = [E.AX[c] for c in cells]
                ts = [int(t) for t in r["ts"]]
                has_spawn = False
                taps = None
            for t in ts:
                if t + 1 > u_est:
                    u_est = t + 1
            sh, rot_k = canon_shape(offs)
            empty_cnt = sum(1 for x in b if x == 0)
            # 이 조각으로 즉시 합침이 가능한지 여부 (learn.jsonl 의 target 은 모두 합침 발생 수)
            piece = list(zip(offs, ts))
            can_m = False
            b_clean = [0 if x < 0 else x for x in b]
            for _, c_mv, t_mv in E.moves(b_clean, piece):
                _, made, _ = E.apply(b_clean, c_mv, t_mv, 0)
                if made:
                    can_m = True
                    break
            parsed.append({
                "gi": gi, "mi": mi, "kind": r["kind"], "has_spawn": has_spawn,
                "n_cells": len(offs), "shape": sh, "rot": rot_k, "taps": taps,
                "ts": ts, "board": b, "empty": empty_cnt, "u": u_est, "can_merge": can_m,
                "t": r.get("t", 0)
            })
    return games, parsed


def load_spawn():
    if not os.path.exists(SPAWN_PATH):
        return [], []
    rows = [json.loads(line) for line in open(SPAWN_PATH, encoding="utf-8") if line.strip()]
    games = collections.defaultdict(list)
    for r in rows:
        if r.get("kind") == "move":
            games[r["gid"]].append(r)
    parsed = []
    for gi, (gid, g) in enumerate(sorted(games.items())):
        for r in g:
            b = r["board"]
            sp = r["tray"]
            offs = [tuple(o) for o, t in sp]
            ts = [int(t) for o, t in sp]
            sh, rot_k = canon_shape(offs)
            empty_cnt = sum(1 for x in b if x == 0)
            u = max([r.get("u") or 3] + [x for x in b if x > 0] + [t + 1 for t in ts])
            piece = list(zip(offs, ts))
            can_m = False
            b_clean = [0 if x < 0 else x for x in b]
            for _, c_mv, t_mv in E.moves(b_clean, piece):
                _, made, _ = E.apply(b_clean, c_mv, t_mv, 0)
                if made:
                    can_m = True
                    break
            parsed.append({
                "gi": gi, "gid": gid, "mv": r["mv"], "n_cells": len(offs),
                "shape": sh, "rot": rot_k, "ts": ts, "board": b,
                "empty": empty_cnt, "u": u, "can_merge": can_m
            })
    return list(games.values()), parsed


def analyze_dataset(name, recs, is_consecutive=False):
    print("================================================================")
    print("데이터셋: %s (총 %d수, 판 수 %d)" % (name, len(recs), len(set(r["gi"] for r in recs))))
    print("================================================================")

    # 기본 모양 분포
    sh_cnt = collections.Counter(r["shape"] for r in recs)
    nc_cnt = collections.Counter(r["n_cells"] for r in recs)
    print("[기본 분포] 칸 수:", dict(sorted(nc_cnt.items())),
          "비율:", {k: round(v / len(recs), 3) for k, v in sorted(nc_cnt.items())})
    print("[기본 분포] 모양:", dict(sorted(sh_cnt.items())),
          "비율:", {k: round(v / len(recs), 3) for k, v in sorted(sh_cnt.items())})

    # 회전 분포 (has_spawn 인 것 또는 전체)
    sp_recs = [r for r in recs if r.get("has_spawn", True)]
    for sh in ("2칸", "3칸-직선", "3칸-꺾임", "3칸-삼각"):
        sub = [r["rot"] for r in sp_recs if r["shape"] == sh]
        if sub:
            c = collections.Counter(sub)
            k_sym = len(c)
            exp = len(sub) / k_sym
            chi2 = sum((v - exp) ** 2 / exp for v in c.values())
            p = chi2_sf(chi2, max(1, k_sym - 1))
            print("  회전 균등성 [%s] n=%d, 분포=%s, chi2=%.2f (p=%.3f)" % (sh, len(sub), dict(sorted(c.items())), chi2, p))

    # ① 묶음(가방) 방식 검정: 판별 연속 구간을 크기 W (5, 6, 10, 15) 블록으로 잘라
    #    각 모양 출현 횟수의 분산/평균 비율(Index of Dispersion = Var / E[Var_iid]) 확인
    #    가방 방식이면 블록 내 모양 개수가 일정해져 Var_obs / Var_iid << 1 이 됨
    print("\n--- ① 묶음(가방) 방식 검정 ---")
    by_game = collections.defaultdict(list)
    for r in recs:
        by_game[r["gi"]].append(r["shape"])
    shapes_list = sorted(sh_cnt.keys())
    p_sh = {s: sh_cnt[s] / len(recs) for s in shapes_list}

    for W in (5, 8, 10, 15):
        blocks = []
        for g_seq in by_game.values():
            for i in range(0, len(g_seq) - W + 1, W):
                blocks.append(g_seq[i:i + W])
        if len(blocks) < 5:
            continue
        # 각 블록의 카이제곱 통계량 합: 이항/다항 i.i.d. 귀무가설 하에서 df = len(blocks) * (K - 1)
        # 가방 방식이면 chi2_sum 이 기댓값(df)보다 유의하게 작음 (과소산포 underdispersion)
        chi2_sum = 0.0
        ratios = []
        for s in shapes_list:
            p = p_sh[s]
            if p <= 0 or p >= 1:
                continue
            cnts = [b.count(s) for b in blocks]
            obs_var = np.var(cnts, ddof=1)
            iid_var = W * p * (1.0 - p)
            ratios.append(obs_var / iid_var)
        for b in blocks:
            for s in shapes_list:
                exp = W * p_sh[s]
                if exp > 0:
                    chi2_sum += (b.count(s) - exp) ** 2 / exp
        df = len(blocks) * (len(shapes_list) - 1)
        mean_disp = float(np.mean(ratios))
        print("  블록 크기 N=%2d: 블록 수=%2d (표본 %3d수), 평균 분산비( 관측Var / 독립Var ) = %.3f, 총 Chi2=%.1f (기대 df=%d)" %
              (W, len(blocks), len(blocks) * W, mean_disp, chi2_sum, df))

    # ② 같은 모양 연속 출현 제한 검정
    print("\n--- ② 같은 모양 연속 출현 제한 검정 ---")
    pairs_total = 0
    same_shape = 0
    same_ncells = 0
    run_lengths = []
    for g_seq in by_game.values():
        if len(g_seq) < 2:
            continue
        cur_len = 1
        for i in range(1, len(g_seq)):
            pairs_total += 1
            if g_seq[i] == g_seq[i - 1]:
                same_shape += 1
                cur_len += 1
            else:
                run_lengths.append(cur_len)
                cur_len = 1
        run_lengths.append(cur_len)
    exp_same_shape = sum(p ** 2 for p in p_sh.values())
    p_nc = {k: v / len(recs) for k, v in nc_cnt.items()}
    # 칸 수 연속 동일
    for g in by_game:
        pass
    by_game_nc = collections.defaultdict(list)
    for r in recs:
        by_game_nc[r["gi"]].append(r["n_cells"])
    for g_seq in by_game_nc.values():
        for i in range(1, len(g_seq)):
            if g_seq[i] == g_seq[i - 1]:
                same_ncells += 1
    exp_same_nc = sum(p ** 2 for p in p_nc.values())
    if pairs_total > 0:
        obs_rate = same_shape / pairs_total
        se = math.sqrt(exp_same_shape * (1.0 - exp_same_shape) / pairs_total)
        z = (obs_rate - exp_same_shape) / se
        p_val = norm_sf_two_sided(z)
        obs_nc_rate = same_ncells / pairs_total
        se_nc = math.sqrt(exp_same_nc * (1.0 - exp_same_nc) / pairs_total)
        z_nc = (obs_nc_rate - exp_same_nc) / se_nc
        p_nc_val = norm_sf_two_sided(z_nc)
        rl_cnt = collections.Counter(run_lengths)
        print("  연속 쌍 수=%d | 같은 5종모양 연속: 관측 %.1f%% (%d회) vs 독립기대 %.1f%% (z=%+.2f, p=%.3f) | 연속 길이 분포=%s" %
              (pairs_total, 100 * obs_rate, same_shape, 100 * exp_same_shape, z, p_val, dict(sorted(rl_cnt.items()))))
        print("  연속 쌍 수=%d | 같은 칸수(1/2/3) 연속: 관측 %.1f%% (%d회) vs 독립기대 %.1f%% (z=%+.2f, p=%.3f)" %
              (pairs_total, 100 * obs_nc_rate, same_ncells, 100 * exp_same_nc, z_nc, p_nc_val))

    # ③ 판이 꽉 찰수록 1칸 조각 · 합칠 수 있는 등급 비율 증가 검정
    print("\n--- ③ 판이 꽉 찰수록(빈 칸 적을수록) 1칸 조각 · 합칠 수 있는 등급 비율 증가 검정 ---")
    # 빈 칸 구간: 여유(empty >= 14), 보통(9 <= empty <= 13), 혼잡(empty <= 8)
    bins = [
        ("여유(빈칸 14~23)", [r for r in recs if r["empty"] >= 14]),
        ("보통(빈칸 9~13)", [r for r in recs if 9 <= r["empty"] <= 13]),
        ("혼잡(빈칸 0~8)", [r for r in recs if r["empty"] <= 8]),
    ]
    for bname, sub in bins:
        if not sub:
            continue
        r_1cell = sum(1 for r in sub if r["n_cells"] == 1) / len(sub)
        r_2cell = sum(1 for r in sub if r["n_cells"] == 2) / len(sub)
        r_3cell = sum(1 for r in sub if r["n_cells"] == 3) / len(sub)
        r_merge = sum(1 for r in sub if r["can_merge"]) / len(sub)
        # 판에 이미 있는 등급과 조각 등급이 겹치는 비율(칸 단위)
        match_t = 0
        tot_t = 0
        for r in sub:
            b_counts = collections.Counter(x for x in r["board"] if x > 0)
            for t in r["ts"]:
                tot_t += 1
                if b_counts[t] >= 1:
                    match_t += 1
        print("  %-18s : n=%3d | 1칸 %.1f%%, 2칸 %.1f%%, 3칸 %.1f%% | 즉시합침가능 %.1f%% | 판보유등급일치 %.1f%%" %
              (bname, len(sub), 100 * r_1cell, 100 * r_2cell, 100 * r_3cell, 100 * r_merge, 100 * match_t / max(1, tot_t)))
    # 상관계수 (빈 칸 수 vs 1칸 여부, 빈 칸 수 vs 판 보유 등급 일치)
    empties = np.array([r["empty"] for r in recs], dtype=float)
    is_1c = np.array([1.0 if r["n_cells"] == 1 else 0.0 for r in recs])
    if is_1c.std() > 0 and empties.std() > 0:
        corr_1c = float(np.corrcoef(empties, is_1c)[0, 1])
        t_stat = corr_1c * math.sqrt((len(recs) - 2) / max(1e-9, 1.0 - corr_1c ** 2))
        print("  상관계수 r(빈칸수, 1칸조각) = %+.3f (z/t=%+.2f, p=%.3f)" % (corr_1c, t_stat, norm_sf_two_sided(t_stat)))
    else:
        print("  상관계수 r(빈칸수, 1칸조각): 1칸 조각 변동 없음 (target 전용 로그는 1칸 제외 구조)")

    # ④ 판에 많은 등급이 더 자주 나오는지, 모양과 등급의 관련성
    print("\n--- ④-A 판에 많은 등급이 더 자주 나오는지 검정 ---")
    # hi - lo == 2 인 안정 구간(u >= 4, 스폰 가능 등급 3개: lo, lo+1, hi)에서
    # 상대 등급 offset = 0(lo), 1(lo+1), 2(hi) 별로 판에 해당 등급 칸 수가 많을 때(>=2칸) vs 적을 때(0~1칸) 출현 비율 비교
    # (단순히 전체를 섞으면 원래 자주 나오는 lo(58%)가 판에도 많아서 가짜 양의 상관이 생기므로, 반드시 offset 별로 층화 검정!)
    u4_recs = [r for r in recs if r["u"] >= 4]
    cells_u4 = []
    for r in u4_recs:
        hi = E.spawn_hi(r["u"])
        lo = max(1, hi - 2)
        if hi - lo != 2:
            continue
        b_cnt = collections.Counter(x for x in r["board"] if x > 0)
        for t in r["ts"]:
            if lo <= t <= hi:
                cells_u4.append((t - lo, b_cnt[lo], b_cnt[lo + 1], b_cnt[hi]))
    print("  해금 4+ 유효 조각 칸 표본 수: %d칸 (조각 %d개)" % (len(cells_u4), len(u4_recs)))
    if cells_u4:
        off_cnt = collections.Counter(x[0] for x in cells_u4)
        n_tot = len(cells_u4)
        print("  상대 등급 전체 비율: lo(0)=%.1f%% (%d), lo+1(1)=%.1f%% (%d), hi(2)=%.1f%% (%d)" %
              (100 * off_cnt[0] / n_tot, off_cnt[0], 100 * off_cnt[1] / n_tot, off_cnt[1], 100 * off_cnt[2] / n_tot, off_cnt[2]))
        for off, label in ((0, "lo(최저)"), (1, "lo+1(중간)"), (2, "hi(최고)")):
            # 판에 해당 등급이 0칸일 때 vs 1칸일 때 vs 2칸 이상일 때 실제 해당 등급이 스폰된 비율
            g0 = [1 if x[0] == off else 0 for x in cells_u4 if x[1 + off] == 0]
            g1 = [1 if x[0] == off else 0 for x in cells_u4 if x[1 + off] == 1]
            g2 = [1 if x[0] == off else 0 for x in cells_u4 if x[1 + off] >= 2]
            p0 = sum(g0) / max(1, len(g0))
            p1 = sum(g1) / max(1, len(g1))
            p2 = sum(g2) / max(1, len(g2))
            # 0~1칸 vs 2칸 이상 차이 z-검정
            g_low = g0 + g1
            p_low = sum(g_low) / max(1, len(g_low))
            p_pool = (sum(g_low) + sum(g2)) / max(1, len(g_low) + len(g2))
            se = math.sqrt(max(1e-9, p_pool * (1 - p_pool) * (1 / max(1, len(g_low)) + 1 / max(1, len(g2)))))
            z = (p2 - p_low) / se if len(g2) > 0 and len(g_low) > 0 else 0.0
            print("    [%s] 판에 0칸(n=%3d): %.1f%% | 1칸(n=%3d): %.1f%% | 2+칸(n=%3d): %.1f%%  (2+칸 vs 0~1칸 z=%+.2f, p=%.3f)" %
                  (label, len(g0), 100 * p0, len(g1), 100 * p1, len(g2), 100 * p2, z, norm_sf_two_sided(z)))

    print("\n--- ④-B 모양과 등급의 관련성 검정 ---")
    # 1) 모양(칸 수 / 5종 모양)별 상대 등급(lo, lo+1, hi) 비율 차이 카이제곱 검정
    sh_off = collections.defaultdict(lambda: [0, 0, 0])
    for r in u4_recs:
        hi = E.spawn_hi(r["u"])
        lo = max(1, hi - 2)
        if hi - lo != 2:
            continue
        for t in r["ts"]:
            if lo <= t <= hi:
                sh_off[r["shape"]][t - lo] += 1
    tot_by_off = [sum(v[i] for v in sh_off.values()) for i in range(3)]
    grand_tot = sum(tot_by_off)
    chi2_sh_t = 0.0
    for sh, cnts in sorted(sh_off.items()):
        row_tot = sum(cnts)
        if row_tot == 0:
            continue
        for i in range(3):
            exp = row_tot * tot_by_off[i] / max(1, grand_tot)
            if exp > 0:
                chi2_sh_t += (cnts[i] - exp) ** 2 / exp
        print("    모양 %-10s (칸 n=%3d): lo %.1f%%, lo+1 %.1f%%, hi %.1f%%" %
              (sh, row_tot, 100 * cnts[0] / row_tot, 100 * cnts[1] / row_tot, 100 * cnts[2] / row_tot))
    df_st = max(1, (len(sh_off) - 1) * 2)
    print("    모양 x 등급 독립성 카이제곱: chi2=%.2f, df=%d, p=%.3f" % (chi2_sh_t, df_st, chi2_sf(chi2_sh_t, df_st)))

    # 2) 다칸 조각(2칸, 3칸) 내 같은 등급 동질성(모두 같은 등급으로 묶여 나오는 비율) 검정
    if grand_tot > 0:
        p_probs = [tot_by_off[i] / grand_tot for i in range(3)]
        for nc in (2, 3):
            sub = [r for r in u4_recs if r["n_cells"] == nc and all(max(1, E.spawn_hi(r["u"]) - 2) <= t <= E.spawn_hi(r["u"]) for t in r["ts"])]
            if not sub:
                continue
            same_all = sum(1 for r in sub if len(set(r["ts"])) == 1)
            obs_p = same_all / len(sub)
            exp_p = sum(p ** nc for p in p_probs)
            se = math.sqrt(exp_p * (1 - exp_p) / len(sub))
            z = (obs_p - exp_p) / se
            print("    %d칸 조각 단일등급(모두 같은 등급) 비율: 관측 %.1f%% (%d/%d) vs 독립추출 기대 %.1f%% (z=%+.2f, p=%.4f)" %
                  (nc, 100 * obs_p, same_all, len(sub), 100 * exp_p, z, norm_sf_two_sided(z)))


if __name__ == "__main__":
    g_learn, p_learn = load_learn()
    analyze_dataset("shots\\hexa_learn.jsonl (전체 기록)", p_learn, is_consecutive=False)
    g_spawn, p_spawn = load_spawn()
    if p_spawn:
        print("\n")
        analyze_dataset("shots\\hexa_spawn.jsonl (연속 전수 기록)", p_spawn, is_consecutive=True)
