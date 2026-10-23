"""adbport.py - 오환2 BlueStacks(Pie64_3)의 ADB 주소를 찾아 모든 모듈에 반영 (patch202)
  BlueStacks 를 다시 켜면 ADB 포트가 바뀔 수 있음 (10-19: 5585 -> 5586, 이후 다시 변경)
  1순위: C:\\ProgramData\\BlueStacks_nxt\\bluestacks.conf 의 bst.instance.Pie64_3.status.adb_port
  2순위: 후보 포트에 붙어서 오환2 게임(com.ekkorr.ef2)이 깔린 기기를 찾음
  py adbport.py      지금 찾은 주소 출력
"""
import os, re, sys, subprocess

ADB_EXE = r"C:\platform-tools\adb.exe"
CONF = r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"
INSTANCE = "Pie64_3"
PKG = "com.ekkorr.ef2"
FALLBACK = "127.0.0.1:5586"
CANDS = [5555, 5556, 5565, 5566, 5575, 5576, 5585, 5586, 5595, 5596, 5605, 5606]


def _run(args, timeout=6):
    try:
        r = subprocess.run([ADB_EXE] + args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


def port_from_conf():
    try:
        with open(CONF, encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except OSError:
        return None
    m = re.search(r'bst\.instance\.%s\.status\.adb_port="(\d+)"' % re.escape(INSTANCE), txt)
    return int(m.group(1)) if m else None


def port_by_scan():
    for p in CANDS:
        dev = "127.0.0.1:%d" % p
        out = _run(["connect", dev], 4)
        if "connected" not in out:
            continue
        if PKG in _run(["-s", dev, "shell", "pm", "path", PKG], 6):
            return p
    return None


def find(scan=False):
    p = port_from_conf()
    if p is None and scan:
        p = port_by_scan()
    return None if p is None else "127.0.0.1:%d" % p


DEV = find() or FALLBACK


def apply(dev):
    """이미 불러온 모듈들의 ADB 주소를 새 주소로 바꿈 (ADB 리스트, DEV / SERIAL 글자)"""
    global DEV
    old = DEV
    DEV = dev
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None) or ""
        if not f.lower().startswith(r"c:\macro"):
            continue
        for name in ("DEV", "SERIAL"):
            v = getattr(m, name, None)
            if isinstance(v, str) and v.startswith("127.0.0.1:") and m is not sys.modules[__name__]:
                setattr(m, name, dev)
        lst = getattr(m, "ADB", None)
        if isinstance(lst, list):
            for i, v in enumerate(lst):
                if isinstance(v, str) and v.startswith("127.0.0.1:"):
                    lst[i] = dev
    return old


def sync(say=print, scan=False):
    """지금 주소를 다시 찾아 바뀌었으면 반영하고 connect. 반환: 지금 주소"""
    dev = find(scan=scan)
    if dev and dev != DEV:
        old = apply(dev)
        say("ADB 주소 바뀜: %s -> %s (BlueStacks 설정에서 확인)" % (old, dev))
    _run(["connect", DEV], 6)
    return DEV


if __name__ == "__main__":
    print("설정 파일:", port_from_conf(), "/ 지금 주소:", DEV)
    if "scan" in sys.argv[1:]:
        print("후보 포트 검색:", port_by_scan())
