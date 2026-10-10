# patch46.py - 프리셋 변경 시 영웅 프리셋을 건드리지 않는 옵션 (C:\macro 에서 py patch46.py)
# preset.set_presets(None, "유물이름") 또는 py preset.py set - 유물이름 go  -> 영웅 탭은 누르지 않고 유물만 바꿔 저장
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "preset.py")

EDITS = [
    ("    if cur_h == hero and cur_r == relic:\n",
     "    if (hero is None or cur_h == hero) and cur_r == relic:\n"),
    ("    if cur_h != hero:\n        tap(HERO_TABS[hero], f\"영웅 {hero}\")\n",
     "    if hero is not None and cur_h != hero:\n        tap(HERO_TABS[hero], f\"영웅 {hero}\")\n"),
    ("    img = wait_for(lambda im: selected(im, HERO_TABS) == hero and selected(im, RELIC_TABS) == relic, 4.0, first=0.5)\n"
     "    if img is None or selected(img, HERO_TABS) != hero or selected(img, RELIC_TABS) != relic:\n",
     "    img = wait_for(lambda im: (hero is None or selected(im, HERO_TABS) == hero) and selected(im, RELIC_TABS) == relic, 4.0, first=0.5)\n"
     "    if img is None or (hero is not None and selected(img, HERO_TABS) != hero) or selected(img, RELIC_TABS) != relic:\n"),
    ("        set_presets(args[1], args[2])\n",
     "        set_presets(None if args[1] in ('-', '유지') else args[1], args[2])\n"),
]


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(P):
        print("preset.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    s = open(P, encoding="utf-8").read()
    if "hero is None or cur_h == hero" in s:
        print("preset.py 는 이미 최신"); return 0
    for a, _ in EDITS:
        if s.count(a) != 1:
            print("앵커 불일치 -> preset.py 를 올려 주세요:", a.strip()[:50]); return 1
    for a, b in EDITS:
        s = s.replace(a, b, 1)
    print("백업:", backup(P))
    open(P, "w", encoding="utf-8").write(s)
    print("preset.py 패치 완료. 사용: py preset.py set - 영웅강화골드 go  (영웅 프리셋은 그대로 두고 유물만 변경)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
