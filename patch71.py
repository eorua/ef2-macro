# patch71.py - 바뀐 '무한 랭킹전' 화면 대응 + 화면이 열린 채 멈추면 자동으로 닫고 넘어가기 (C:\macro 에서 py patch71.py)
#   * 원인: 새 화면은 전투 버튼 위치(y 903/1027/1150)와 X 위치가 달라서, 예전 좌표로 눌러 엉뚱한 곳(티켓 구매 등)을 누르거나
#           화면을 못 닫고 열어 둔 채 다음 단계로 못 넘어갔음
#   * inf2.py 신규: 빨간 전투 버튼/X 를 색으로 찾고, 레벨/티켓/무료 새로고침은 윈도우 OCR 로 읽음
#           (OCR 이 안 되면 맨 위 상대와 전투, 무료 새로고침은 안 누름 -> 다이아 소모 없음)
#   * daily.py: 무한랭킹전 진입 직후 새 화면이면 inf2.run 으로 처리, 일일 작업 뒤에는 열린 화면이 있으면 닫음
#   * main.py: 이 화면이 열린 채 멈춰 있으면 20초 안에 닫음 / 웨이브를 90초 넘게 못 읽으면 열린 창을 닫아 봄
#   * 시험:  py inf2.py look (판별만, 안 누름) / py inf2.py close (열려 있으면 닫기) / py inf2.py go (실제 진행)
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
DAILY = os.path.join(HERE, "daily.py")
INF2 = os.path.join(HERE, "inf2.py")
INF2_DATA = """
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
"""

D_OLD1 = '    tap(ROW_INF, 1.5)\n    img = cap()\n    if img is None or not has_x(img, INF_X_ROI):\n        log("무한랭킹전 상대 목록 화면을 못 찾음 -> 중단")\n'
D_NEW1 = ('    tap(ROW_INF, 1.5)\n    img = cap()\n'
          '    try:\n        import inf2\n        if inf2.is_open(img):\n            return inf2.run(go, img)\n'
          '    except Exception as e:\n        log("새 무한랭킹전 처리 오류: %r" % (e,))\n'
          '    if img is None or not has_x(img, INF_X_ROI):\n        log("무한랭킹전 상대 목록 화면을 못 찾음 -> 중단")\n')
D_OLD2 = '            r = do_infinite(True)\n'
D_NEW2 = ('            r = do_infinite(True)\n'
          '            try:\n                import inf2\n                inf2.close_if_open()\n'
          '            except Exception as e:\n                log("무한랭킹전 화면 닫기 오류: %r" % (e,))\n')
M_OLD1 = "            if popup_open(img):\n                continue                     # 프리셋/일괄 레벨업 창이 열려 있으면 건드리지 않음\n"
M_NEW1 = ('            if GO:\n                try:\n                    import inf2\n                    if inf2.idle_check(img):\n'
          '                        hist.clear()\n                        stuck.reset()\n                        continue\n'
          '                except Abort:\n                    raise\n'
          '                except Exception as e:\n                    log("무한랭킹전 화면 확인 오류: %r" % (e,))\n') + M_OLD1
M_OLD2 = "            w = wave.read_wave(img)\n            if w is not None:\n                hist.append(w)\n"
M_NEW2 = ('            w = wave.read_wave(img)\n            if GO:\n                try:\n                    import inf2\n                    if inf2.nowave_watch(img, w):\n'
          '                        hist.clear()\n                        stuck.reset()\n                        continue\n'
          '                except Abort:\n                    raise\n'
          '                except Exception as e:\n                    log("웨이브 미인식 처리 오류: %r" % (e,))\n'
          '            if w is not None:\n                hist.append(w)\n')


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def load(path):
    s = open(path, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), "\r\n" in s


def save(path, s, crlf):
    open(path, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)


def main():
    for p in (MAIN, DAILY):
        if not os.path.exists(p):
            print(os.path.basename(p), "가 없습니다 (C:\\macro 에서 실행)"); return 1
    m, mcrlf = load(MAIN)
    d, dcrlf = load(DAILY)
    mdone = "inf2.idle_check" in m
    ddone = "inf2.is_open" in d
    if not mdone and (m.count(M_OLD1) != 1 or m.count(M_OLD2) != 1):
        print("main.py 앵커 불일치", m.count(M_OLD1), m.count(M_OLD2), "-> main.py 를 올려 주세요"); return 1
    if not ddone and (d.count(D_OLD1) != 1 or d.count(D_OLD2) != 1):
        print("daily.py 앵커 불일치", d.count(D_OLD1), d.count(D_OLD2), "-> daily.py 를 올려 주세요"); return 1
    raw = zlib.decompress(base64.b64decode("".join(INF2_DATA.split())))
    if not os.path.exists(INF2) or open(INF2, "rb").read() != raw:
        if os.path.exists(INF2):
            print("백업:", backup(INF2))
        open(INF2, "wb").write(raw)
        print("inf2.py 갱신")
    else:
        print("inf2.py 는 이미 최신")
    if not ddone:
        print("daily.py 백업:", backup(DAILY))
        d = d.replace(D_OLD1, D_NEW1, 1).replace(D_OLD2, D_NEW2, 1)
        save(DAILY, d, dcrlf)
        print("daily.py 패치 완료")
    else:
        print("daily.py 는 이미 최신")
    if not mdone:
        print("main.py 백업:", backup(MAIN))
        m = m.replace(M_OLD1, M_NEW1, 1).replace(M_OLD2, M_NEW2, 1)
        save(MAIN, m, mcrlf)
        print("main.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    else:
        print("main.py 는 이미 최신")
    print("무한랭킹전 화면을 띄워 놓고 py inf2.py look 으로 판별을 확인해 보세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
