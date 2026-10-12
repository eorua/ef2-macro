# patch70.py - 출석 보상 창을 '글자'로 찾아서 받기/닫기 (창 모양이 달라도 인식) (C:\macro 에서 py patch70.py)
#   * 원인: 기존 인식은 '제목/받기 버튼 그림'이 정해진 위치(짧은 창)에 있어야 했는데, 연속/누적 접속 + 10일 보상이 붙은 큰 출석 창은
#           제목과 받기 버튼 위치가 달라서 인식을 못 했음. 9시와는 무관
#   * ocrx.py 신규: 윈도우 내장 OCR 로 글자와 위치를 읽어 '출석/접속/받기' 가 있으면 출석 창으로 보고 '받기'를 누름.
#           창이 남아 있으면 다음에 빨간 X 를 누름 (제목줄의 작은 X 도 인식)
#   * main.py: find_popup 이 그림으로 못 찾으면 ocrx 로 한 번 더 확인 (게임 재시작 복귀 때와 평소 루프 모두)
#   * 시험:  py ocrx.py words (글자와 위치) / py ocrx.py look (출석 창인지) / py ocrx.py go (실제로 받기 + 닫기)
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
OCRX = os.path.join(HERE, "ocrx.py")
OCRX_DATA = """
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
"""

M_OLD1 = "def find_popup(img):\n"
M_NEW1 = '''def _ocr_popup(img):
    """그림으로 못 찾은 출석 보상 창을 글자(OCR)로 찾음 -> (이름, 누를 좌표) 또는 None"""
    try:
        import ocrx
        return ocrx.find_attendance(img)
    except Exception as e:
        log("글자로 팝업 찾기 오류: %r" % (e,))
        return None


def find_popup(img):
'''
M_OLD2 = "        if ts >= 0.85 and bs >= 0.90:\n            return name, pos\n    return None\n"
M_NEW2 = "        if ts >= 0.85 and bs >= 0.90:\n            return name, pos\n    return _ocr_popup(img)\n"


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(MAIN):
        print("main.py 가 없습니다 (C:\\macro 에서 실행)"); return 1
    s = open(MAIN, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    done = "def _ocr_popup(" in s
    if not done and (s.count(M_OLD1) != 1 or s.count(M_OLD2) != 1):
        print("main.py 앵커 불일치", s.count(M_OLD1), s.count(M_OLD2), "-> main.py 를 올려 주세요"); return 1
    raw = zlib.decompress(base64.b64decode("".join(OCRX_DATA.split())))
    if not os.path.exists(OCRX) or open(OCRX, "rb").read() != raw:
        if os.path.exists(OCRX):
            print("백업:", backup(OCRX))
        open(OCRX, "wb").write(raw)
        print("ocrx.py 갱신")
    else:
        print("ocrx.py 는 이미 최신")
    if not done:
        print("main.py 백업:", backup(MAIN))
        s = s.replace(M_OLD1, M_NEW1, 1).replace(M_OLD2, M_NEW2, 1)
        open(MAIN, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
        print("main.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    else:
        print("main.py 는 이미 최신")
    print("출석 창이 떠 있을 때 py ocrx.py look 으로 판별을 확인해 보세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
