# -*- coding: utf-8 -*-
"""bench_hammer.py - 신규 공방 규칙(합성점 확정 + 망치 1회) 시뮬레이션 벤치마크
전략 비교:
  A: Baseline (새 합성점 규칙만 적용, 망치 미사용)
  B: Emergency Hammer (게임오버 직전, 현재 조각을 둘 수 있게 만드는 최저티어 칸 파괴)
  C: Proactive Hammer (★8 이상에서 고립된 저티어 1~3성 선제 파괴)
"""
import time, random, os, sys
import hexa_engine as E
import hexa_nt as NT

random.seed(42)

def gen_piece_with_dot(unlocked):
    p = E.rand_piece(unlocked, random)  # [((q,r), tier)...]
    # Check if multiple tiles have the same tier
    tiers = [t for (q, r), t in p]
    dot_idx = 0
    if len(p) > 1:
        # If any tier appears >= 2 times, choose one of those as dot
        same = [i for i, t in enumerate(tiers) if tiers.count(t) >= 2]
        if same:
            dot_idx = random.choice(same)
        else:
            dot_idx = 0
    return p, dot_idx

def can_place_any(b, piece):
    offs = [c for c, t in piece]
    for k in range(6):
        ro = E.rot(offs, k)
        for cells in E.placements(ro):
            if all(b[c] == 0 for c in cells):
                return True
    return False

def smart_hammer_candidates(b, piece):
    """현재 piece를 둘 수 있게 만들어주는 파괴 대상 칸 후보들 (가장 낮은 등급 순)"""
    offs = [c for c, t in piece]
    cands = []
    for k in range(6):
        ro = E.rot(offs, k)
        for cells in E.placements(ro):
            # If exactly 1 cell is blocked, destroying that cell makes this placement valid!
            blocked = [c for c in cells if b[c] > 0]
            if len(blocked) == 1:
                target = blocked[0]
                tier = b[target]
                cands.append((tier, target))
    if not cands:
        # If no single-cell break works, pick any cell with lowest tier
        lowest = min((b[i], i) for i in range(E.N) if b[i] > 0)
        return [lowest]
    cands.sort(key=lambda x: x[0])  # lowest tier first
    return cands

def sim_one(strategy="none", max_moves=2000):
    b = [0] * E.N
    unlocked = 3
    moves = 0
    hammer_left = 1 if strategy != "none" else 0
    star10_count = 0
    max_tier = 3
    total_score = 0
    
    cur, cur_dot = gen_piece_with_dot(unlocked)
    nxt, nxt_dot = gen_piece_with_dot(unlocked)
    
    while moves < max_moves:
        ms = E.moves(b, cur)
        
        # Strategy C (Proactive): If field has star8/star9 and hammer available,
        # check if there is an isolated low-tier (1..3) cell blocking merges
        if strategy == "proactive" and hammer_left > 0 and any(x >= 8 for x in b):
            # find isolated low tier
            for i in range(E.N):
                if 1 <= b[i] <= 3:
                    # check neighbors: if surrounded by empty or high tier without same tier
                    nb_tiers = [b[n] for n in E.NB[i]]
                    if b[i] not in nb_tiers:
                        # Destroy this isolated low-tier cell!
                        b = E.hammer(b, i)
                        hammer_left = 0
                        ms = E.moves(b, cur)
                        break
        
        if not ms:
            # Game over condition!
            if hammer_left > 0:
                # Emergency hammer!
                cands = smart_hammer_candidates(b, cur)
                if cands:
                    target_cell = cands[0][1]
                    b = E.hammer(b, target_cell)
                    hammer_left = 0
                    ms = E.moves(b, cur)
            
            if not ms:
                break  # No moves even after hammer
        
        # Pick best move (1-step heuristic fast simulation)
        best_sc = -1e9
        best_choice = None
        for k, cells, ts in ms:
            dot_cell = cells[cur_dot] if cur_dot < len(cells) else cells[0]
            nb, made, _ = E.apply(b, cells, ts, dot_cell=dot_cell)
            sc = 0
            for t, count, nt in made:
                sc += (1 << nt) * 10
                if nt == 10:
                    sc += 50000
                elif nt == 9:
                    sc += 8000
                elif nt == 8:
                    sc += 2000
            # Space penalty
            empty = sum(1 for x in nb if x == 0)
            sc += empty * 15
            if sc > best_sc:
                best_sc = sc
                best_choice = (k, cells, ts, dot_cell)
        
        if not best_choice:
            break
            
        k, cells, ts, dot_cell = best_choice
        b, made, _ = E.apply(b, cells, ts, dot_cell=dot_cell)
        unlocked = E.new_unlocked(unlocked, made)
        for t, count, nt in made:
            total_score += (1 << nt)
            if nt > max_tier:
                max_tier = nt
            if nt == 10:
                star10_count += 1
                
        moves += 1
        cur, cur_dot = nxt, nxt_dot
        nxt, nxt_dot = gen_piece_with_dot(unlocked)
        
    return {
        "moves": moves,
        "score": total_score,
        "max_tier": max_tier,
        "star10": star10_count > 0
    }

def run_bench(n_games=300):
    strategies = [
        ("A (Baseline, No Hammer)", "none"),
        ("B (Emergency Hammer)", "emergency"),
        ("C (Proactive Hammer)", "proactive")
    ]
    
    print(f"=== Running Simulation: {n_games} games per strategy ===")
    results = {}
    for label, strat in strategies:
        t0 = time.time()
        games = [sim_one(strategy=strat) for _ in range(n_games)]
        elapsed = time.time() - t0
        s10_rate = sum(1 for g in games if g["star10"]) / n_games * 100.0
        avg_moves = sum(g["moves"] for g in games) / n_games
        avg_score = sum(g["score"] for g in games) / n_games
        max_moves = max(g["moves"] for g in games)
        print(f"[{label}]")
        print(f"  ★10 달성률: {s10_rate:.1f}% ({sum(1 for g in games if g['star10'])}/{n_games})")
        print(f"  평균 수: {avg_moves:.1f}수 (최대 {max_moves}수), 평균 점수: {avg_score:.0f}")
        print(f"  소요 시간: {elapsed:.1f}초")
        results[label] = {
            "s10_rate": s10_rate,
            "avg_moves": avg_moves,
            "avg_score": avg_score,
            "elapsed": elapsed
        }
    return results

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    run_bench(n)
