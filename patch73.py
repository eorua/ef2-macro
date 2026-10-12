# patch73.py - 일괄 레벨업이 '모든 영웅 최대 레벨'로 잘못 판단해 한 번도 안 누르는 문제 보완 (C:\macro 에서 py patch73.py)
#   * 원인(추정): 버튼 아래 비용 글자가 '0'처럼 짧게 보이면 최대 레벨로 보고 바로 종료함 (짧은 비용 글자도 같은 모양으로 읽힐 수 있음)
#   * 수정: 0으로 보여도 바로 끝내지 않고 한 번 눌러 본 뒤, 레벨 열이 안 변할 때만 최대 레벨로 판단
#           (0으로 의심된 순간의 화면은 shots\bulk_zero.png 로 저장 -> 원인 확인용)
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PRESET = os.path.join(HERE, "preset.py")

O1 = '            before = None\n            why = "한도"\n'
N1 = '            before = None\n            zero = 0\n            why = "한도"\n'
O2 = '                if levels_maxed(now):\n                    maxed = True\n                    why = "모든 영웅 최대 레벨"\n                    break\n'
N2 = '''                if levels_maxed(now):
                    zero += 1
                    if zero == 1:
                        print("  비용이 0으로 보이지만 한 번 눌러서 확인 (shots\\\\bulk_zero.png 저장)")
                        try:
                            os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
                            cv2.imwrite(os.path.join(BASE, "shots", "bulk_zero.png"), now)
                        except Exception:
                            pass
                    if zero >= 2 and before is not None and float(np.abs(level_crop(now) - before).mean()) <= thr:
                        maxed = True
                        why = "모든 영웅 최대 레벨(눌러 봐도 변화 없음)"
                        break
'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    s = open(PRESET, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if "bulk_zero.png" in s:
        print("preset.py 는 이미 최신"); return 0
    if s.count(O1) != 1 or s.count(O2) != 1:
        print("preset.py 앵커 불일치", s.count(O1), s.count(O2), "-> preset.py 를 올려 주세요"); return 1
    print("preset.py 백업:", backup(PRESET))
    s = s.replace(O1, N1, 1).replace(O2, N2, 1)
    open(PRESET, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("preset.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
