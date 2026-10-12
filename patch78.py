# patch78.py - 성 함락 '환생 클릭'이 안 먹혔을 때 몇 초 안에 다시 누르기 (C:\macro 에서 py patch78.py)
#   * 지금까지: 클릭 후 2초 기다리고 환생결과 팝업을 최대 25초 기다림 -> 클릭이 무시돼도 약 30초 뒤에야 다음 시도, 그 사이 '환생 기록'도 잘못 남음
#   * 수정: 클릭 후 2.5초 뒤에도 '성 함락' 팝업이 그대로면 다시 클릭 (최대 3번까지, 환생결과 팝업이 보이면 하지 않음)
#           그래도 팝업이 남아 있으면 환생 기록은 남기지 않고 다음 루프에서 다시 시도
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
OLD = '''                log("성 함락 감지 → 환생 클릭")
                if GO:
                    rebirth.tap(gx, gy)
                    time.sleep(2)
                    rebirth.after_click()
                    record_rebirth(st, "환생"); st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0)
'''
NEW = '''                log("성 함락 감지 → 환생 클릭")
                if GO:
                    rebirth.tap(gx, gy)
                    time.sleep(2.5)
                    for _try in range(2):
                        _chk = cap()
                        if _chk is None or result_popup(_chk)[0]:
                            break
                        _ok2, (_gx2, _gy2) = fall_popup(_chk)
                        if not _ok2:
                            break
                        log("환생 클릭이 안 먹힌 것 같음 → 다시 클릭 (%d/2)" % (_try + 1))
                        rebirth.tap(_gx2, _gy2)
                        time.sleep(2.5)
                    rebirth.after_click()
                    _chk = cap()
                    if _chk is not None and fall_popup(_chk)[0] and not result_popup(_chk)[0]:
                        log("성 함락 팝업이 그대로 남아 있음 → 환생 기록 없이 다음 루프에서 재시도")
                        continue
                    record_rebirth(st, "환생"); st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0)
'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    s = open(MAIN, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if "환생 클릭이 안 먹힌 것 같음" in s:
        print("main.py 는 이미 최신"); return 0
    if s.count(OLD) != 1:
        print("main.py 앵커 불일치", s.count(OLD), "-> main.py 를 올려 주세요"); return 1
    print("main.py 백업:", backup(MAIN))
    s = s.replace(OLD, NEW, 1)
    open(MAIN, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("main.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
