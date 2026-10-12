# patch57.py - 6200 웨이브 원래(비 병영) 고레벨 단계도 영웅 프리셋은 그대로 두고 유물만 변경 (C:\macro 에서 py patch57.py)
#  전: 영웅 최대레벨 + 유물 영웅강화골드 -> 일괄 레벨업 -> 영웅 렙뻥 + 유물 기본
#  후: 유물 영웅강화골드 -> 일괄 레벨업 -> 유물 기본  (영웅 프리셋 미변경)
#  재시작 후 복구도 고레벨 완료 상태면 영웅 프리셋은 건드리지 않음
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")

OLD1 = '''    ok = preset.set_presets("최대레벨", "영웅강화골드")
    if not ok:
        return False
    bulk_ok = preset.bulk_levelup()
    final_ok = preset.set_presets("렙뻥", "기본")
    return bulk_ok and final_ok
'''
NEW1 = '''    ok = preset.set_presets(None, "영웅강화골드")      # 영웅 프리셋은 그대로 (바꾸면 레벨이 다시 바뀌어 골드 손실)
    if not ok:
        return False
    bulk_ok = preset.bulk_levelup()
    final_ok = False
    for _ in range(3):                                   # 유물이 영웅강화골드로 남지 않게 복귀는 재시도
        if preset.set_presets(None, "기본"):
            final_ok = True
            break
        time.sleep(2)
    return bulk_ok and final_ok
'''
OLD2 = '''    hero, relic = (None, "기본") if (st.get("high_done") and opt_on("barracks_swap")) else \\
        (("렙뻥", "기본") if st.get("high_done") else ("기본", "시간"))
'''
NEW2 = '''    hero, relic = (None, "기본") if st.get("high_done") else ("기본", "시간")
'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(MAIN):
        print("main.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    s = open(MAIN, encoding="utf-8").read()
    if NEW1 in s and NEW2 in s:
        print("main.py 는 이미 최신"); return 0
    if s.count(OLD1) != 1 or s.count(OLD2) != 1:
        print("앵커 불일치 (고레벨 %d, 재시작 %d) -> main.py 를 올려 주세요" % (s.count(OLD1), s.count(OLD2))); return 1
    h = open(os.path.join(HERE, "preset.py"), encoding="utf-8").read()
    if "hero is None or cur_h == hero" not in h:
        print("먼저 patch46.py 를 적용하세요"); return 1
    print("main.py 백업:", backup(MAIN))
    open(MAIN, "w", encoding="utf-8").write(s.replace(OLD1, NEW1, 1).replace(OLD2, NEW2, 1))
    print("패치 완료 (메인 매크로를 껐다 켜세요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
