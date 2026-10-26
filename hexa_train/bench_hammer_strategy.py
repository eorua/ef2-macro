# -*- coding: utf-8 -*-
"""bench_hammer_strategy.py - 망치 활용 전략 정밀 비교 시뮬레이션
전략 비교:
  A: Baseline (망치 없음)
  B: Emergency (죽기 직전 최저티어 파괴)
  C: Low-tier Isolation (8성 이상일 때 고립된 1~3성 파괴)
  D: Star10 Hub Finisher (유저 제안: 8성 2+2 쌍 사이에 낀 장애물을 깨서 5개 합치기 ★10 직행 길을 여는 전략)
"""
import time, random, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hexa_engine as E

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
    """★8이 3개 또는 4개 이상 있을 때, 어떤 칸 i를 깨면 그 빈칸을 중심으로
    주변의 ★8들이 모여 4~5개 합각(허브)이 형성되는 장애물 칸 i를 찾음"""
    cnt = sum(1 for x in b if x == target_tier)
    if cnt < 3:
        return None
    
    # 23개 칸 중 기물이 있는 칸 i를 가상으로 비워본 뒤 허브 가치 계산
    best_cand = None
    best_gain = 0
    
    for i in range(E.N):
        if b[i] == 0 or b[i] >= target_tier:
            continue  # 이미 빈칸이거나 타겟 티어 자체는 깨지 않음
        
        # 칸 i 주변에 ★8 이웃이 몇 개나 붙어있는지 확인
        nb8 = [n for n in E.NB[i] if b[n] == target_tier]
        if len(nb8) >= 2:
            # i 칸을 깨면 최소 2개 이상의 ★8 덩어리가 i 칸을 매개로 인접하게 됨!
            # i 주변의 ★8 덩어리 크기 합산
            comp_seen = set()
            total_connected = 0
            for n in nb8:
                g = E.group(b, n)
                g_key = tuple(sorted(g))
                if g_key not in comp_seen:
                    comp_seen.add(g_key)
                    total_connected += len(g)
            
            # 만약 i 칸을 비웠을 때 연결 가능한 ★8 합계가 4개 이상이면 (5개 합치기 ★10 직행 각!)
            if total_connected >= 4:
                gain = total_connected * 100 - b[i] * 5
                if gain > best_gain:
                    best_gain = gain
                    best_cand = i
            elif total_connected == 3 and best_gain < 200:
                # 3개 연결 (4개 합치기 각)
                gain = 50 - b[i] * 5
                if gain > best_gain:
                    best_gain = gain
                    best_cand = i
                    
    return best_cand

def find_star9_obstacle(b):
    """★9가 2개 이상 있을 때, 그 사이를 막고 있는 칸을 찾아 파괴 (3개 합치기 ★10 완성)"""
    cnt9 = sum(1 for x in b if x == 9)
    if cnt9 < 2:
        return None
    for i in range(E.N):
        if b[i] == 0 or b[i] >= 9:
            continue
        nb9 = [n for n in E.NB[i] if b[n] == 9]
        if len(nb9) >= 2:
            # 두 ★9 사이에 낀 장애물!
            return i
    return None

def sim_one(strategy="none", max_moves=2500):
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
        
        # ---------------- 전략 D (유저 제안: ★10 피니셔/허브 완성형 망치) ----------------
        if strategy == "finisher" and hammer_left > 0:
            # 1순위: ★9 가 2개 있고 그 사이를 막고 있는 장애물 칸 파괴
            obs9 = find_star9_obstacle(b)
            if obs9 is not None:
                b = E.hammer(b, obs9)
                hammer_left = 0
                ms = E.moves(b, cur)
            else:
                # 2순위: ★8 2+2 쌍 사이에 낀 장애물 칸 파괴 (5개 합치기 ★10 직행 길 열기)
                obs8 = find_hub_obstacle(b, 8)
                if obs8 is not None:
                    b = E.hammer(b, obs8)
                    hammer_left = 0
                    ms = E.moves(b, cur)
                    
        # ---------------- 전략 C (기존: 고립 저티어 1~3성 선제 파괴) ----------------
        elif strategy == "proactive" and hammer_left > 0 and any(x >= 8 for x in b):
            for i in range(E.N):
                if 1 <= b[i] <= 3:
                    nb_tiers = [b[n] for n in E.NB[i]]
                    if b[i] not in nb_tiers:
                        b = E.hammer(b, i)
                        hammer_left = 0
                        ms = E.moves(b, cur)
                        break
        
        # ---------------- 게임오버 방지 (전략 B / D의 비상 백업) ----------------
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
        
        # AI 수 선택 (허브 가중치 + 합성점 확정 평가)
        best_sc = -1e9
        best_choice = None
        for k, cells, ts in ms:
            dot_cell = cells[cur_dot] if cur_dot < len(cells) else cells[0]
            nb, made, _ = E.apply(b, cells, ts, dot_cell=dot_cell)
            sc = 0
            for t, count, nt in made:
                sc += (1 << nt) * 10
                if nt == 10:
                    sc += 100000  # ★10 절대 우선
                elif nt == 9:
                    sc += 20000
                elif nt == 8:
                    sc += 5000
            
            # 허브 구조 보너스 (8성 2+2 인접 유도)
            n8 = sum(1 for x in nb if x == 8)
            n9 = sum(1 for x in nb if x == 9)
            sc += n8 * 80 + n9 * 300
            
            # 빈칸 여유 보너스
            empty = sum(1 for x in nb if x == 0)
            sc += empty * 18
            
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

def run_bench(n_games=500):
    strategies = [
        ("A (Baseline, 망치 없음)", "none"),
        ("B (Emergency, 죽기 직전 비상 탈출)", "emergency"),
        ("C (Proactive, 고립 1~3성 선제 파괴)", "proactive"),
        ("D (Finisher, ★10 허브 길뚫기 파괴 - 유저 제안)", "finisher")
    ]
    
    print(f"=== 망치 활용 전략 4종 비교 시뮬레이션: 각 {n_games}판 ===")
    results = {}
    for label, strat in strategies:
        t0 = time.time()
        games = [sim_one(strategy=strat) for _ in range(n_games)]
        elapsed = time.time() - t0
        s10_rate = sum(1 for g in games if g["star10"]) / n_games * 100.0
        s9_rate = sum(1 for g in games if g["star9"]) / n_games * 100.0
        avg_moves = sum(g["moves"] for g in games) / n_games
        avg_score = sum(g["score"] for g in games) / n_games
        max_moves = max(g["moves"] for g in games)
        print(f"[{label}]")
        print(f"  ★10 달성률: {s10_rate:.1f}% ({sum(1 for g in games if g['star10'])}/{n_games})")
        print(f"  ★9 달성률:  {s9_rate:.1f}% ({sum(1 for g in games if g['star9'])}/{n_games})")
        print(f"  평균 수: {avg_moves:.1f}수 (최대 {max_moves}수), 평균 점수: {avg_score:.0f}")
        print(f"  소요 시간: {elapsed:.1f}초\n")
        results[label] = {
            "s10_rate": s10_rate,
            "s9_rate": s9_rate,
            "avg_moves": avg_moves,
            "avg_score": avg_score
        }
    return results

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_bench(n)
