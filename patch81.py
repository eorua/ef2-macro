# patch81.py - arrange.py 드래그 보정 (patch80 다음)
#   * 원인: 아이콘 기준점(깃발 아래 막대 끝)과 얼굴 중심이 달라 놓은 곳과 목표가 어긋남 -> 놓을 지점을 보정하고 오차를 측정해 재보정
import os, sys, shutil, base64, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
ARR = os.path.join(HERE, "arrange.py")
PAYLOAD = "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"

def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst

def main():
    if not os.path.exists(ARR):
        print("arrange.py 가 없습니다 (patch79 먼저)"); return 1
    cur = open(ARR, encoding="utf-8").read().replace("\r\n", "\n")
    if "OFF = [-12, 33]" in cur and '("run" if GO else "look")' in cur:
        print("arrange.py 는 이미 최신"); return 0
    if "def run():" not in cur:
        print("arrange.py 내용이 예상과 다름"); return 1
    new = zlib.decompress(base64.b64decode(PAYLOAD)).decode("utf-8")
    print("arrange.py 백업:", backup(ARR))
    open(ARR, "w", encoding="utf-8", newline="").write(new.replace("\n", "\r\n"))
    print("arrange.py 패치 완료")
    return 0

if __name__ == "__main__":
    sys.exit(main())
