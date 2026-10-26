"""adbport.py - 오환2 에뮬레이터의 ADB 주소를 찾아 모든 모듈에 반영 (patch202, patch250: 뮤뮤 지원)
  어떤 에뮬레이터를 쓸지는 C:\\macro\\emu.json 의 "emu" 로 정함 (파일이 없거나 읽기 실패 -> bluestacks)
    {"emu": "bluestacks"}   기존 BlueStacks(Pie64_3) 방식 그대로 (롤백은 이 한 단어만 바꾸면 됨)
    {"emu": "mumu", "mumu_port": 16384, "mumu_index": 0}   뮤뮤 플레이어
  환경변수 MACRO_EMU=mumu / bluestacks 가 있으면 emu.json 보다 우선 (단발 시험용)

  [BlueStacks] 다시 켜면 ADB 포트가 바뀔 수 있음 (10-19: 5585 -> 5586, 이후 다시 변경)
    1순위: C:\\ProgramData\\BlueStacks_nxt\\bluestacks.conf 의 bst.instance.Pie64_3.status.adb_port
    2순위: 후보 포트에 붙어서 오환2 게임(com.ekkorr.ef2)이 깔린 기기를 찾음
  [뮤뮤] (patch250)
    기본: emu.json 의 mumu_port (16384 = 1번째 인스턴스, 인스턴스 번호마다 +32)
    scan 일 때: MuMuManager info 로 실제 포트 확인 -> 그래도 없으면 후보 포트(16384/16416/.../5555/7555) 검색
  py adbport.py        지금 찾은 주소 출력
  py adbport.py scan   후보 포트까지 검색
"""
import os, re, sys, json, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
ADB_EXE = os.path.join(BASE, "adb.exe") if os.path.exists(os.path.join(BASE, "adb.exe")) else (
    r"C:\platform-tools\adb.exe" if os.path.exists(r"C:\platform-tools\adb.exe") else "adb"
)
PKG = "com.ekkorr.ef2"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------------------------------------------------------------- 에뮬레이터 선택 (patch250)
EMU_CFG = os.path.join(BASE, "emu.json")


def _load_emu():
    cfg = {"emu": "bluestacks", "mumu_port": 16384, "mumu_index": 0, "mumu_manager": ""}
    try:
        with open(EMU_CFG, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            cfg.update(d)
    except (OSError, ValueError):
        pass
    if os.environ.get("MACRO_EMU"):
        cfg["emu"] = os.environ["MACRO_EMU"]
    cfg["emu"] = str(cfg.get("emu") or "bluestacks").strip().lower()
    if cfg["emu"] not in ("bluestacks", "mumu"):
        cfg["emu"] = "bluestacks"
    return cfg


CFG = _load_emu()
EMU = CFG["emu"]
IS_MUMU = EMU == "mumu"
EMU_NAME = "뮤뮤" if IS_MUMU else "BlueStacks"

# ---------------------------------------------------------------- BlueStacks (기존 그대로)
CONF = r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"
INSTANCE = "Pie64_3"
BS_FALLBACK = "127.0.0.1:5586"
BS_CANDS = [5555, 5556, 5565, 5566, 5575, 5576, 5585, 5586, 5595, 5596, 5605, 5606]

# ---------------------------------------------------------------- 뮤뮤 (patch250)
try:
    MUMU_INDEX = int(CFG.get("mumu_index") or 0)
except (TypeError, ValueError):
    MUMU_INDEX = 0
try:
    MUMU_PORT = int(CFG.get("mumu_port") or (16384 + 32 * MUMU_INDEX))
except (TypeError, ValueError):
    MUMU_PORT = 16384 + 32 * MUMU_INDEX
MUMU_FALLBACK = "127.0.0.1:%d" % MUMU_PORT
MUMU_CANDS = list(dict.fromkeys([MUMU_PORT, 16384 + 32 * MUMU_INDEX]
                                + [16384 + 32 * i for i in range(6)] + [5555, 7555]))
MUMU_MGR_PATHS = [
    r"C:\Program Files\Netease\MuMuPlayer\nx_main\MuMuManager.exe",
    r"C:\Program Files\Netease\MuMuPlayer\nx_main\mumu-cli.exe",
    r"C:\Program Files\Netease\MuMuPlayer\shell\MuMuManager.exe",
    r"C:\Program Files\Netease\MuMuPlayer-12.0\nx_main\MuMuManager.exe",
    r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe",
    r"C:\Program Files\Netease\MuMu Player 12\nx_main\MuMuManager.exe",
    r"C:\Program Files\Netease\MuMu Player 12\shell\MuMuManager.exe",
]

FALLBACK = MUMU_FALLBACK if IS_MUMU else BS_FALLBACK
CANDS = MUMU_CANDS if IS_MUMU else BS_CANDS


def _run(args, timeout=6):
    try:
        r = subprocess.run([ADB_EXE] + args, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
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


# ---------------------------------------------------------------- 뮤뮤 관리 도구 (patch250)
def mumu_manager():
    """MuMuManager.exe 경로 (emu.json 의 mumu_manager 가 있으면 그것 우선). 없으면 None"""
    for p in [CFG.get("mumu_manager") or ""] + MUMU_MGR_PATHS:
        if p and os.path.exists(p):
            return p
    return None


def mumu_cmd(*args, timeout=30):
    """MuMuManager <args...> 실행 -> 출력 글자 (실패하면 None). 콘솔 창 안 띄움"""
    mgr = mumu_manager()
    if not mgr:
        return None
    try:
        r = subprocess.run([mgr] + [str(a) for a in args], capture_output=True, timeout=timeout,
                           creationflags=NOWIN)
    except Exception:
        return None
    out = r.stdout or b""
    for enc in ("utf-8", "cp949"):
        try:
            return out.decode(enc)
        except UnicodeDecodeError:
            continue
    return out.decode("utf-8", "ignore")


def mumu_info():
    """MuMuManager info -v <번호> 결과(JSON dict). 관리 도구가 없거나 해석 실패면 None"""
    out = mumu_cmd("info", "-v", MUMU_INDEX, timeout=15)
    if not out:
        return None
    i, j = out.find("{"), out.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        d = json.loads(out[i:j + 1])
    except ValueError:
        return None
    if isinstance(d, dict) and str(MUMU_INDEX) in d and isinstance(d[str(MUMU_INDEX)], dict):
        d = d[str(MUMU_INDEX)]                  # 여러 인스턴스 묶음으로 올 때
    return d if isinstance(d, dict) else None


def port_from_mumu():
    d = mumu_info()
    if not d:
        return None
    try:
        p = int(d.get("adb_port") or 0)
    except (TypeError, ValueError):
        return None
    return p or None


# ---------------------------------------------------------------- 공통
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
    if IS_MUMU:                                   # patch250
        if not scan:                              # 뮤뮤는 설정 파일 대신 지금 주소 유지 (scan 결과가 되돌려지지 않게)
            return globals().get("DEV") or MUMU_FALLBACK
        p = port_from_mumu()
        if p is None:
            p = port_by_scan()
        return None if p is None else "127.0.0.1:%d" % p
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
        say("ADB 주소 바뀜: %s -> %s (%s 설정에서 확인)" % (old, dev, EMU_NAME))
    _run(["connect", DEV], 6)
    return DEV


if __name__ == "__main__":
    print("에뮬레이터:", EMU_NAME, "(emu.json: %s)" % ("있음" if os.path.exists(EMU_CFG) else "없음 -> 기본 BlueStacks"))
    if IS_MUMU:
        print("뮤뮤 인스턴스 번호:", MUMU_INDEX, "/ 설정 포트:", MUMU_PORT)
        print("MuMuManager:", mumu_manager() or "못 찾음 (emu.json 에 mumu_manager 경로 지정 가능)")
        print("MuMuManager 포트:", port_from_mumu(), "/ 지금 주소:", DEV)
    else:
        print("설정 파일:", port_from_conf(), "/ 지금 주소:", DEV)
    if "scan" in sys.argv[1:]:
        print("후보 포트 검색:", port_by_scan())
