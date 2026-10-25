# patch266 검증: (1) 화면 판독 전/후 비교 (2) 로그 재현으로 '못 읽은 칸 채우기' 효과·정확도
import sys, glob, json, importlib.util
import cv2
from collections import defaultdict, Counter
sys.path.insert(0, r"C:\macro")
import hexa_engine as E
import hexa_vision as NEW


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


OLD = load(r"C:\macro\hexa_vision.py.bak266", "old_vision")

print("=== (1) 화면 판독 전/후 (BlueStacks 캡처) ===")
chg = Counter()
for f in sorted(glob.glob('C:/macro/shots/hexa_err_*.png')):
    im = cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2RGB)
    a, _ = OLD.read_board(im)
    b, _ = NEW.read_board(im)
    d = [(i, a[i], b[i]) for i in range(E.N) if a[i] != b[i]]
    for i, x, y in d:
        chg[(x, y)] += 1
    print(f.split('/')[-1], "바뀐 칸(칸, 전, 후):", d)
print("요약 (전->후: 횟수)", dict(chg))

print("\n=== (2) 로그 재현: 못 읽은 칸을 예상 판으로 채우기 ===")


def bfp(b):
    return [(-100 - i) if t < 0 else t for i, t in enumerate(b)]


games = defaultdict(list)
for line in open('C:/macro/shots/hexa_spawn.jsonl', encoding='utf-8'):
    if not line.strip():
        continue
    o = json.loads(line)
    if o.get('kind') == 'move':
        games[o['gid']].append(o)
raw_unk = known_unk = filled = 0
check_ok = check_bad = 0
for g in games.values():
    g.sort(key=lambda m: m['mv'])
    known = None
    fill_val = {}
    for a, b in zip(g, g[1:]):
        if b['mv'] != a['mv'] + 1 or not a.get('tray'):
            known = None
            fill_val = {}
            continue
        bd = list(a['board'])
        if known is not None and len(known) == E.N:
            # 실전 코드와 같음: 다음 수의 판 = 채운 판
            bd = known
        piece = [(tuple(p[0]), p[1]) for p in a['tray']]
        obs = list(b['board'])
        raw_unk += sum(1 for v in obs if v < 0)
        # 이전에 채운 칸이 이번엔 읽혔으면 맞았는지 (그 칸이 이번 수에 안 바뀐 경우만)
        hit_pred = None
        bp = bfp(bd)
        for k, cells, ts in E.moves(bp, piece):
            br = E.apply(bp, cells, ts, 0)[2]
            for ch in range(br):
                nb = E.apply(bp, cells, ts, ch)[0]
                if all(nb[i] == obs[i] or obs[i] < 0 or nb[i] < 0 for i in range(E.N)):
                    hit_pred = nb
                    break
            if hit_pred:
                break
        new = list(obs)
        if hit_pred:
            for i in range(E.N):
                if i in fill_val and obs[i] >= 0 and hit_pred[i] == fill_val[i]:
                    if obs[i] == fill_val[i]:
                        check_ok += 1
                    else:
                        check_bad += 1
            fill_val = {}
            for i in range(E.N):
                if new[i] < 0 and 0 < hit_pred[i] < 9:
                    new[i] = hit_pred[i]
                    fill_val[i] = hit_pred[i]
                    filled += 1
        else:
            fill_val = {}
        known_unk += sum(1 for v in new if v < 0)
        known = new
print("판독 그대로의 -1 칸 수:", raw_unk, "/ 채운 뒤 -1 칸 수:", known_unk, "/ 채운 칸:", filled)
print("채운 값이 나중에 실제로 읽혔을 때 맞음 %d / 틀림 %d" % (check_ok, check_bad))
