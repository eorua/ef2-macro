"""apply162.py - patch162 (ADB 공통화) 적용 / 되돌리기
  py apply162.py        _next162 폴더의 새 파일을 적용 (지금 파일은 *.py.bak162 로 백업)
  py apply162.py undo   백업(*.py.bak162)으로 되돌림
적용/되돌린 뒤에는 패널에서 '메인 재시작'
"""
import os, sys, shutil, py_compile

BASE = os.path.dirname(os.path.abspath(__file__))
NEXT = os.path.join(BASE, "_next162")


def main():
    if "undo" in sys.argv[1:]:
        n = 0
        for f in sorted(os.listdir(BASE)):
            if f.endswith(".py.bak162"):
                shutil.copy2(os.path.join(BASE, f), os.path.join(BASE, f[:-7]))
                n += 1
        p = os.path.join(BASE, "dev.py")
        if os.path.exists(p) and not os.path.exists(p + ".bak162"):
            os.remove(p)
        print("되돌림: %d개 파일 (dev.py 제거). 패널에서 메인 재시작" % n)
        return
    files = sorted(f for f in os.listdir(NEXT) if f.endswith(".py"))
    for f in files:                                   # 먼저 전부 문법 확인
        py_compile.compile(os.path.join(NEXT, f), doraise=True)
    for f in files:
        dst = os.path.join(BASE, f)
        if os.path.exists(dst) and not os.path.exists(dst + ".bak162"):
            shutil.copy2(dst, dst + ".bak162")
    for f in sorted(files, key=lambda x: x != "dev.py"):   # dev.py 를 맨 먼저
        shutil.copy2(os.path.join(NEXT, f), os.path.join(BASE, f))
        print("적용", f)
    print("완료: %d개. 패널에서 '메인 재시작' (문제 있으면: py apply162.py undo)" % len(files))


if __name__ == "__main__":
    main()
