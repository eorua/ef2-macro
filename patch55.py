# patch55.py - 무한랭킹전 전투 결과 대기 20초로 단축 + 시간 초과 시 화면 저장 (C:\macro 에서 py patch55.py)
#  * daily.py: INF_BATTLE_TIMEOUT 200 -> 20 (전투는 보통 10초 안팎)
#  * 시간 안에 결과가 안 잡히면 그 화면을 shots\inf_timeout.png 로 저장 (결과 창 인식 개선용)
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY = os.path.join(HERE, "daily.py")

A1 = "INF_BATTLE_TIMEOUT = 200"
B1 = "INF_BATTLE_TIMEOUT = 20"
A2 = '    log("전투 결과가 %d초 안에 안 뜸 -> 중단" % INF_BATTLE_TIMEOUT)\n    return "abort"\n'
B2 = ('    try:\n'
      '        img = cap()\n'
      '        if img is not None:\n'
      '            os.makedirs(SHOTS, exist_ok=True)\n'
      '            cv2.imwrite(os.path.join(SHOTS, "inf_timeout.png"), img)\n'
      '            log("그때 화면 저장: shots\\\\inf_timeout.png")\n'
      '    except Exception:\n'
      '        pass\n'
      '    log("전투 결과가 %d초 안에 안 뜸 -> 중단" % INF_BATTLE_TIMEOUT)\n    return "abort"\n')


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(DAILY):
        print("daily.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    d = open(DAILY, encoding="utf-8").read()
    done = B1 in d and "inf_timeout.png" in d
    if done:
        print("daily.py 는 이미 최신"); return 0
    if d.count(A1) != 1 or d.count(A2) != 1:
        print("앵커 불일치 (%d, %d) -> daily.py 를 올려 주세요" % (d.count(A1), d.count(A2))); return 1
    print("daily.py 백업:", backup(DAILY))
    open(DAILY, "w", encoding="utf-8").write(d.replace(A1, B1, 1).replace(A2, B2, 1))
    print("패치 완료 (메인 매크로를 껐다 켜세요; 패널의 단발 실행은 바로 적용)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
