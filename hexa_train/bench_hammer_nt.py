# -*- coding: utf-8 -*-
"""bench_hammer_nt.py - n-tuple 가중치 기반 실전급 AI 시뮬레이터로 망치 전략 비교
전략:
  A: Baseline (새 합성점 규칙만 적용, 망치 미사용)
  B: Emergency Hammer (게임오버 직전, 현재 조각을 둘 수 있게 만드는 최저티어 칸 파괴)
  C: Proactive Hammer (★8 이상에서 고립된 저티어 1~3성 선제 파괴)
"""
import time, random, os, sys
import hexa_engine as E
import hexa_nt as NT

random.seed(42)

# Load n-tuple weights
NT._load()

def gen_piece_with_dot(unlocked):
    p = E.rand_piece(unlocked, random)
    tiers = [t for (q, r), t in p]
    dot_idx = 0
    if len(p) > 1:
        same = [i for i, t in enumerate(tiers) if tiers.count(t) >= 2]
        if same:
            dot_idx = random.choice(same)
        else:
            dot_idx = 0
    return p, dot_idx

def smart_hammer_candidates(b, piece):
    offs = [c for c, t in piece]
    cands = []
    for k in range(6):
        ro = E.rot(offs, k)
        for cells in E.placements(ro):
            blocked = [c for c in cells if b[c] > 0]
            if len(blocked) == 1:
                target = blocked[0]
                tier = b[target]
                cands.append((tier, target))
    if not cands:
        lowest = min((b[i], i) for i in range(E.N) if b[i] > 0)
        return [lowest]
    cands.sort(key=lambda x: x[0])
    return cands

def sim_one(strategy="none", max_moves=3000):
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
        
        # Strategy C (Proactive): If field has star8/star9 and hammer available
        if strategy == "proactive" and hammer_left > 0 and any(x >= 8 for x in b):
            # Check for isolated low-tier (1..3)
            for i in range(E.N):
                if 1 <= b[i] <= 3:
                    nb_tiers = [b[n] for n in E.NB[i]]
                    if b[i] not in nb_tiers:
                        b = E.hammer(b, i)
                        hammer_left = 0
                        ms = E.moves(b, cur)
                        break
        
        if not ms:
            if hammer_left > 0:
                cands = smart_hammer_candidates(b, cur)
                if cands:
                    target_cell = cands[0][1]
                    b = E.hammer(b, target_cell)
                    hammer_left = 0
                    ms = E.moves(b, cur)
            
            if not ms:
                break
        
        # NT best move (1-step afterstate evaluation with n-tuple)
        best_val = -1e9
        best_choice = None
        for k, cells, ts in ms:
            dot_cell = cells[cur_dot] if cur_dot < len(cells) else cells[0]
            nb, made, _ = E.apply(b, cells, ts, dot_cell=dot_cell)
            u2 = E.new_unlocked(unlocked, made)
            v = float(NT.values([nb], [u2])[0])
            for t, cnt, nt in made:
                if nt == 10:
                    v += 200.0  # huge bonus for 10-star
                elif nt == 9:
                    v += 50.0
                elif nt == 8:
                    v += 15.0
            if v > best_val:
                best_val = v
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
    
    print(f"=== n-tuple AI Simulation: {n_games} games per strategy ===")
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

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    run_bench(n)
