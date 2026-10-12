# patch53.py - closer.py 의 X 인식 개선 (C:\\macro 에서 py patch53.py)
# 어두운 공지 창의 X(분홍 X + 어두운 빨강)를 못 잡던 문제 수정. 흰 글자가 실제 'X' 모양인지(대각선) 확인해서 둥근 버튼/전투 버튼 오인식도 막음
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "closer.py")
DATA = """
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
"""


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(os.path.join(HERE, "preset.py")):
        print("preset.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    data = zlib.decompress(base64.b64decode("".join(DATA.split())))
    if os.path.exists(DST):
        if open(DST, "rb").read() == data:
            print("closer.py 는 이미 최신"); return 0
        print("백업:", backup(DST))
    open(DST, "wb").write(data)
    print("closer.py 갱신 완료. 메인 매크로는 껐다 켜세요. 확인: py closer.py (창이 떠 있을 때)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
