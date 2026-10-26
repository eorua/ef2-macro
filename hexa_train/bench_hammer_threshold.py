# -*- coding: utf-8 -*-
"""bench_hammer_threshold.py - 망치 발동 임계 빈칸 수 튜닝 시뮬레이션
비상 탈출 시 빈칸이 몇 개 이하일 때 망치를 쓰는 것이 ★10 달성률에 가장 유리한지 정밀 비교:
  1) zero     : 둘 곳이 전혀 없을 때만 (not ms)
  2) free_1   : 빈칸 <= 1개 이하일 때
  3) free_2   : 빈칸 <= 2개 이하일 때
  4) free_3   : 빈칸 <= 3개 이하일 때
  5) hub_zero : 8성 허브 블로커 우선 파괴 + 둘 곳 없을 때 (현재 하이브리드)
  6) hub_free2: 8성 허브 블로커 우선 파괴 + 빈칸 <= 2개 이하일 때
"""
import os, sys, time, random, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hexa_engine as E
import hexa_nt as NT

def gen_piece_with_dot(unlocked, rng):
    p = E.rand_piece(unlocked, rng)
    tiers = [t for (q, r), t in p]
    dot_idx = 0
    if len(p) > 1:
        same = [i for i, t in enumerate(tiers) if tiers.count(t) >= 2]
        if same:
            dot_idx = rng.choice(same)
    return p, dot_idx

def smart_hammer_escape(b, piece):
    """둘 곳이 없을 때 즉시 배치를 가능하게 만들어주는 최저 등급 칸"""
    offs = [c for c, t in piece]
    cands = []
    for k in range(6):
        ro = E.rot(offs, k)
        for cells in E.placements(ro):
            blocked = [c for c in cells if b[c] > 0]
            if len(blocked) == 1:
                target = blocked[0]
                cands.append((b[target], target))
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[0][1]
    # 전체 최저 등급 칸
    lowest = min((b[i], i) for i in range(E.N) if b[i] > 0)
    return lowest[1]

def pick_space_hammer(b):
    """빈칸 확보용 최적 파괴 칸: 고립된 최저 등급(1~3성) 칸 우선"""
    lows = []
    for i in range(E.N):
        if 1 <= b[i] <= 3:
            nb_tiers = [b[n] for n in E.NB[i]]
            iso = 1 if b[i] not in nb_tiers else 0
            lows.append((iso, -b[i], i))
    if lows:
        lows.sort(reverse=True)
        return lows[0][2]
    # 아무 최저 등급 칸
    return min((b[i], i) for i in range(E.N) if b[i] > 0)[1]

def find_hub_obstacle(b):
    """★8 2+2 허브 중심을 막고 있는 1~3성 장애물 칸 탐색"""
    cnt8 = sum(1 for x in b if x == 8)
    if cnt8 < 3:
        return None
    for i in range(E.N):
        if 1 <= b[i] <= 3:
            nb8 = [n for n in E.NB[i] if b[n] == 8]
            if len(nb8) >= 2:
                comp_seen = set()
                total_conn = 0
                for n in nb8:
                    g = E.group(b, n)
                    gk = tuple(sorted(g))
                    if gk not in comp_seen:
                        comp_seen.add(gk)
                        total_conn += len(g)
                if total_conn >= 4:
                    return i
    return None

def sim_game(mode, seed, max_moves=2000):
    rng = random.Random(seed)
    b = [0] * E.N
    unlocked = 3
    moves = 0
    hammer_left = 1
    has_star10 = False
    star10_moves = []
    total_score = 0
    max_tier = 3

    cur, cur_dot = gen_piece_with_dot(unlocked, rng)
    nxt, nxt_dot = gen_piece_with_dot(unlocked, rng)

    while moves < max_moves:
        free_cells = sum(1 for x in b if x == 0)
        has_star10 = any(x >= 10 for x in b) or (len(star10_moves) > 0)

        # 1) 허브 블로커 선제 파괴 체크 (hub_ 계열 모드, 10성 미달성 시만)
        if hammer_left > 0 and not has_star10 and mode.startswith("hub_"):
            target = find_hub_obstacle(b)
            if target is not None:
                b = E.hammer(b, target)
                hammer_left = 0

        # 2) 빈칸 임계치에 따른 망치 선제 발동
        if hammer_left > 0:
            should_hammer = False
            if mode in ("free_1", "hub_free1") and free_cells <= 1:
                should_hammer = True
            elif mode in ("free_2", "hub_free2") and free_cells <= 2:
                should_hammer = True
            elif mode in ("free_3", "hub_free3") and free_cells <= 3:
                should_hammer = True

            if should_hammer:
                target = pick_space_hammer(b)
                b = E.hammer(b, target)
                hammer_left = 0

        ms = E.moves(b, cur)

        # 3) 둘 곳이 없을 때 비상 탈출
        if not ms:
            if hammer_left > 0:
                target = smart_hammer_escape(b, cur)
                b = E.hammer(b, target)
                hammer_left = 0
                ms = E.moves(b, cur)
            if not ms:
                break

        # 4) C 수읽기 탐색
        mv = NT.best_move_c(b, unlocked, cur, nxt, D=3, B=8, K=8, budget_ms=1000, seed=moves)
        if mv is None:
            # 둘 곳 없음
            if hammer_left > 0:
                target = smart_hammer_escape(b, cur)
                b = E.hammer(b, target)
                hammer_left = 0
                mv = NT.best_move_c(b, unlocked, cur, nxt, D=3, B=8, K=8, budget_ms=1000, seed=moves)
            if mv is None:
                break

        k, cells, ts = mv[0], mv[1], mv[2]
        nb, made, nbr = E.apply(b, cells, ts, choice=0, dot_cell=cells[cur_dot] if cur_dot < len(cells) else None)
        b = nb

        # 점수 및 해금/10성 추적
        for t, n, nt in made:
            total_score += 2 ** nt
            max_tier = max(max_tier, nt)
            if nt >= 10 and not has_star10:
                star10_moves.append(moves + 1)
                has_star10 = True
        unlocked = E.new_unlocked(unlocked, made)

        cur, cur_dot = nxt, nxt_dot
        nxt, nxt_dot = gen_piece_with_dot(unlocked, rng)
        moves += 1

    return {
        "moves": moves,
        "score": total_score,
        "max_tier": max_tier,
        "star10": len(star10_moves) > 0,
        "star10_move": star10_moves[0] if star10_moves else None,
        "hammer_used": 1 - hammer_left
    }

def run_bench(n_games=60):
    modes = [
        ("A: zero     (둘 곳 없을 때만)", "zero"),
        ("B: free_1   (빈칸 <= 1개일 때)", "free_1"),
        ("C: free_2   (빈칸 <= 2개일 때)", "free_2"),
        ("D: free_3   (빈칸 <= 3개일 때)", "free_3"),
        ("E: hub_zero (8성허브 우선 + 둘곳없을때)", "hub_zero"),
        ("F: hub_free2(8성허브 우선 + 빈칸<=2개)", "hub_free2"),
    ]
    
    seeds = [1000 + i * 37 for i in range(n_games)]
    out_path = os.path.join(os.path.dirname(__file__), "bench_hammer_threshold_result.txt")
    with open(out_path, "w", encoding="utf-8") as f_out:
        def log_msg(msg):
            print(msg, flush=True)
            f_out.write(msg + "\n")
            f_out.flush()

        log_msg("=" * 75)
        log_msg(f" [망치 발동 임계 빈칸 수 튜닝 벤치마크] ({n_games}판 동일 시드 비교)")
        log_msg("=" * 75)
        
        results = {}
        for label, mode in modes:
            t0 = time.time()
            stats = []
            for idx, s in enumerate(seeds):
                r = sim_game(mode, s)
                stats.append(r)
                if (idx + 1) % 10 == 0:
                    print(f"  [{label[:12]}] 진행 중: {idx + 1}/{len(seeds)}판 완료...", flush=True)
            dur = time.time() - t0
            
            n = len(stats)
            avg_moves = sum(s["moves"] for s in stats) / n
            avg_score = sum(s["score"] for s in stats) / n
            s10_rate = sum(1 for s in stats if s["star10"]) / n * 100
            s9_rate = sum(1 for s in stats if s["max_tier"] >= 9) / n * 100
            hammer_rate = sum(1 for s in stats if s["hammer_used"]) / n * 100
            s10_games = [s for s in stats if s["star10"]]
            avg_s10_move = sum(s["star10_move"] for s in s10_games) / len(s10_games) if s10_games else 0
            
            results[mode] = {
                "label": label, "moves": avg_moves, "score": avg_score,
                "s10_rate": s10_rate, "s9_rate": s9_rate, "s10_move": avg_s10_move,
                "hammer_rate": hammer_rate, "dur": dur
            }
            line = f"{label:38s} | ★10달성: {s10_rate:5.1f}% | ★9+: {s9_rate:5.1f}% | 평균수: {avg_moves:5.1f} | 점수: {avg_score:6.0f} ({dur:.1f}초)"
            log_msg(line)

        log_msg("=" * 75)
        log_msg(" [최종 분석 요약]")
        best_s10 = max(results.values(), key=lambda x: x["s10_rate"])
        best_score = max(results.values(), key=lambda x: x["score"])
        log_msg(f" • ★10 달성률 1위: {best_s10['label']} ({best_s10['s10_rate']:.1f}%)")
        log_msg(f" • 평균 득점 1위  : {best_score['label']} ({best_score['score']:.0f}점)")
        log_msg("=" * 75)
    print(f"\n결과가 저장되었습니다: {out_path}", flush=True)
    return results

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    run_bench(n)
