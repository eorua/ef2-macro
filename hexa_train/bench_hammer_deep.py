# -*- coding: utf-8 -*-
"""bench_hammer_deep.py - C 3수 깊은 탐색(search11) 기반 망치 전략 4종 비교
A: Baseline (망치 없음)
B: Emergency (죽기 직전 최저티어 파괴)
C: Proactive (8성 이상 고립 1~3성 파괴)
D: Finisher (8성 2+2 허브 장애물 파괴)
"""
import os, sys, time, random, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hexa_engine as E
import hexa_nt as NT

random.seed(2026)

def gen_piece_with_dot(unlocked):
    p = E.rand_piece(unlocked, random)
    tiers = [t for (q, r), t in p]
    dot_idx = 0
    if len(p) > 1:
        same = [i for i, t in enumerate(tiers) if tiers.count(t) >= 2]
        if same:
            dot_idx = random.choice(same)
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
                cands.append((b[target], target))
    if not cands:
        lowest = min((b[i], i) for i in range(E.N) if b[i] > 0)
        return [lowest]
    cands.sort(key=lambda x: x[0])
    return cands

def find_hub_obstacle(b, target_tier=8):
    cnt = sum(1 for x in b if x == target_tier)
    if cnt < 3:
        return None
    best_cand = None
    best_gain = 0
    for i in range(E.N):
        if b[i] == 0 or b[i] >= target_tier:
            continue
        nb8 = [n for n in E.NB[i] if b[n] == target_tier]
        if len(nb8) >= 2:
            comp_seen = set()
            total_connected = 0
            for n in nb8:
                g = E.group(b, n)
                g_key = tuple(sorted(g))
                if g_key not in comp_seen:
                    comp_seen.add(g_key)
                    total_connected += len(g)
            if total_connected >= 4:
                gain = total_connected * 100 - b[i] * 5
                if gain > best_gain:
                    best_gain = gain
                    best_cand = i
            elif total_connected == 3 and best_gain < 200:
                gain = 50 - b[i] * 5
                if gain > best_gain:
                    best_gain = gain
                    best_cand = i
    return best_cand

def find_star9_obstacle(b):
    cnt9 = sum(1 for x in b if x == 9)
    if cnt9 < 2:
        return None
    for i in range(E.N):
        if b[i] == 0 or b[i] >= 9:
            continue
        nb9 = [n for n in E.NB[i] if b[n] == 9]
        if len(nb9) >= 2:
            return i
    return None

def sim_one(strategy="none", max_moves=2000):
    b = [0] * E.N
    unlocked = 3
    moves = 0
    hammer_left = 1 if strategy != "none" else 0
    star10_count = 0
    star9_count = 0
    max_tier = 3
    total_score = 0
    
    cur, cur_dot = gen_piece_with_dot(unlocked)
    nxt, nxt_dot = gen_piece_with_dot(unlocked)
    
    while moves < max_moves:
        ms = E.moves(b, cur)
        
        # 전략 D (★10 허브 피니셔)
        if strategy == "finisher" and hammer_left > 0:
            obs9 = find_star9_obstacle(b)
            if obs9 is not None:
                b = E.hammer(b, obs9)
                hammer_left = 0
                ms = E.moves(b, cur)
            else:
                obs8 = find_hub_obstacle(b, 8)
                if obs8 is not None:
                    b = E.hammer(b, obs8)
                    hammer_left = 0
                    ms = E.moves(b, cur)
                    
        # 전략 C (고립 저티어 1~3성)
        elif strategy == "proactive" and hammer_left > 0 and any(x >= 8 for x in b):
            for i in range(E.N):
                if 1 <= b[i] <= 3:
                    nb_tiers = [b[n] for n in E.NB[i]]
                    if b[i] not in nb_tiers:
                        b = E.hammer(b, i)
                        hammer_left = 0
                        ms = E.moves(b, cur)
                        break
        
        # 비상 탈출 (게임오버 방지)
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
                
        # C 탐색기 호출 (D=3, B=8, K=8)
        mv = None
        if NT is not None and hasattr(NT, "best_move_c") and NT.c_available():
            try:
                mv = NT.best_move_c(b, unlocked, cur, nxt, D=3, B=8, K=8, budget_ms=1000)
                if mv is not None:
                    mv = mv[:4]
            except Exception:
                mv = None
                
        if mv is None:
            # Fallback to python best_move
            mv = E.best_move(b, unlocked, cur, nxt)
            
        if not mv:
            break
            
        k, cells, ts = mv[0], mv[1], mv[2]
        dot_cell = cells[cur_dot] if cur_dot < len(cells) else cells[0]
        b, made, _ = E.apply(b, cells, ts, dot_cell=dot_cell)
        unlocked = E.new_unlocked(unlocked, made)
        for t, count, nt in made:
            total_score += (1 << nt)
            if nt > max_tier:
                max_tier = nt
            if nt == 10:
                star10_count += 1
            elif nt == 9:
                star9_count += 1
                
        moves += 1
        cur, cur_dot = nxt, nxt_dot
        nxt, nxt_dot = gen_piece_with_dot(unlocked)
        
    return {
        "moves": moves,
        "score": total_score,
        "max_tier": max_tier,
        "star10": star10_count > 0,
        "star9": star9_count > 0
    }

def run_bench(n_games=60):
    strategies = [
        ("A (Baseline, 망치 없음)", "none"),
        ("B (Emergency, 비상 탈출)", "emergency"),
        ("C (Proactive, 고립 1~3성 선제 파괴)", "proactive"),
        ("D (Finisher, ★10 허브 길뚫기 - 유저 제안)", "finisher")
    ]
    
    print(f"=== C 3수 깊은 탐색(search11) 기반 전략 4종 비교: 각 {n_games}판 ===")
    for label, strat in strategies:
        t0 = time.time()
        games = [sim_one(strategy=strat) for _ in range(n_games)]
        elapsed = time.time() - t0
        s10_rate = sum(1 for g in games if g["star10"]) / n_games * 100.0
        s9_rate = sum(1 for g in games if g["star9"]) / n_games * 100.0
        avg_moves = sum(g["moves"] for g in games) / n_games
        avg_score = sum(g["score"] for g in games) / n_games
        print(f"[{label}]")
        print(f"  ★10 달성률: {s10_rate:.1f}% ({sum(1 for g in games if g['star10'])}/{n_games})")
        print(f"  ★9 달성률:  {s9_rate:.1f}% ({sum(1 for g in games if g['star9'])}/{n_games})")
        print(f"  평균 수: {avg_moves:.1f}수, 평균 점수: {avg_score:.0f}")
        print(f"  소요 시간: {elapsed:.1f}초\n")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    run_bench(n)
