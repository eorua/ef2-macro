# patch60.py - 환생 직후 프리셋 설정이 실패할 때 열린 창(영웅 상세 등)을 닫고 재시도 (C:\macro 에서 py patch60.py)
#  1) preset.py : '탭 선택 확인 실패' 때 취소 버튼을 무조건 누르지 않음 (팝업이 이미 닫혀 있으면 그 자리의 영웅 목록이 눌려 영웅 상세창이 뜸)
#  2) main.py   : 환생 후 프리셋 설정이 실패할 때마다 열린 빨간 X 창을 닫고 다음 시도 (전엔 3번째/8번째 실패 때 하단 X만 확인했음)
#                 1번째 실패 때도 화면을 shots\preset_fail_1.png 로 저장 (원인 확인용)
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
PRESET = os.path.join(HERE, "preset.py")

P_OLD = '''        print("탭 선택 확인 실패 → 취소로 닫고 중단")
        tap(PRE_CANCEL, "취소")
        return False
'''
P_NEW = '''        print("탭 선택 확인 실패 → 취소로 닫고 중단")
        cur = capture()
        if cur is not None and preset_open(cur):      # 팝업이 아직 열려 있을 때만 취소 (닫혀 있으면 뒤의 영웅 목록이 눌림)
            tap(PRE_CANCEL, "취소")
        else:
            print("  (팝업이 이미 닫혀 있어 취소는 누르지 않음)")
        return False
'''
M_OLD = '''                        if low_fails in (3, 8):
                            snap_fail("preset_fail_%d" % low_fails)
                            daily.close_panels()
'''
M_NEW = '''                        if low_fails in (1, 3, 8):
                            snap_fail("preset_fail_%d" % low_fails)
                        try:
                            import closer
                            nclosed = closer.close_all()
                            if nclosed:
                                log("프리셋 실패 후 열린 창 %d개 닫음" % nclosed)
                        except Abort:
                            raise
                        except Exception as e:
                            log("창 닫기 오류: %r" % (e,))
                        if low_fails in (3, 8):
                            daily.close_panels()
'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    for p in (MAIN, PRESET):
        if not os.path.exists(p):
            print(os.path.basename(p), "가 없습니다. C:\\macro 에서 실행하세요."); return 1
    if not os.path.exists(os.path.join(HERE, "closer.py")):
        print("closer.py 가 없습니다. patch50~53 을 먼저 적용하세요."); return 1
    ms = open(MAIN, encoding="utf-8").read()
    ps = open(PRESET, encoding="utf-8").read()
    done_m = "프리셋 실패 후 열린 창" in ms
    done_p = "팝업이 이미 닫혀 있어 취소는 누르지 않음" in ps
    if not done_m and ms.count(M_OLD) != 1:
        print("main.py 앵커 불일치 (%d) -> main.py 를 올려 주세요" % ms.count(M_OLD)); return 1
    if not done_p and ps.count(P_OLD) != 1:
        print("preset.py 앵커 불일치 (%d) -> preset.py 를 올려 주세요" % ps.count(P_OLD)); return 1
    if not done_m:
        print("main.py 백업:", backup(MAIN))
        open(MAIN, "w", encoding="utf-8").write(ms.replace(M_OLD, M_NEW, 1))
        print("main.py 패치 완료")
    else:
        print("main.py 는 이미 최신")
    if not done_p:
        print("preset.py 백업:", backup(PRESET))
        open(PRESET, "w", encoding="utf-8").write(ps.replace(P_OLD, P_NEW, 1))
        print("preset.py 패치 완료")
    else:
        print("preset.py 는 이미 최신")
    print("메인 매크로를 껐다 켜야 반영됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
