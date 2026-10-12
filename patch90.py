# patch90.py - 정체 감시가 웨이브가 빨리 오르는 동안 '최고' 값을 못 올려서 가짜 정체 로그를 내던 문제 수정
#   * 원인: 같은 숫자가 연속 2번 읽혀야 갱신 -> 웨이브가 읽을 때마다 바뀌면 영영 갱신 안 됨
#   * 수정: 연속 두 값이 서로 60 이내(오독이 아님)이고 최고보다 크면 갱신
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
OLD = '''        if w == self.last:                       # 같은 값이 연속 2번 읽힐 때만 인정 (오독 방지)
            if w > self.best or (self.best and w < self.best - 500):
                self.best = w
                self.since = now
'''
NEW = '''        if self.last is not None and abs(w - self.last) <= 60:      # 연속 두 값이 서로 가까울 때만 인정 (오독 방지)
            if w > self.best or (self.best and w < self.best - 500):
                self.best = w
                self.since = now
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
    if NEW in s:
        print("main.py 는 이미 최신"); return 0
    if s.count(OLD) != 1:
        print("main.py 앵커 불일치", s.count(OLD)); return 1
    new = s.replace(OLD, NEW)
    compile(new, "main.py", "exec")
    print("main.py 백업:", backup(MAIN))
    open(MAIN, "w", encoding="utf-8", newline="").write(new.replace("\n", "\r\n") if crlf else new)
    print("main.py 패치 완료 (메인 재시작 필요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
