import subprocess, sys, time
import adbport

ADB_EXE = r"C:\platform-tools\adb.exe"
DEV = adbport.DEV
EMU = adbport.EMU                 # patch250: "bluestacks" 또는 "mumu" (emu.json)
PLAYER = r"C:\Program Files\BlueStacks_nxt\HD-Player.exe"
INSTANCE = "Pie64_3"              # 오환2 인스턴스 이름 (bluestacks.conf 에서 확인)
TITLE = "오환2"                   # BlueStacks 창 제목에 들어 있는 글자
GO = "go" in sys.argv[1:]


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return r.stdout


def find_pids():
    """오환2 BlueStacks(Pie64_3) HD-Player 프로세스 번호들 (다른 인스턴스는 절대 건드리지 않음)
    patch250: 뮤뮤면 MuMuManager info 로 해당 인스턴스(mumu_index)의 프로세스 번호만
    patch294f: 창 제목이 비어있거나 백그라운드일 때도 100% 탐색 가능하도록 현재 ADB 포트 LISTENING PID 우선 확인"""
    if adbport.IS_MUMU:
        return _mumu_pids()

    # 1순위: 현재 연결된 ADB 포트를 LISTENING 중인 HD-Player PID 탐색 (창 제목 무관, 타 인스턴스 보호 100%)
    try:
        cur_dev = adbport.DEV or "127.0.0.1:5585"
        port = int(cur_dev.split(":")[-1]) if ":" in cur_dev else 5585
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0] == "TCP":
                local_addr = parts[1]
                state = parts[3]
                pid_str = parts[4]
                if local_addr.endswith(":" + str(port)) and state == "LISTENING" and pid_str.isdigit():
                    pid_val = int(pid_str)
                    p_name = ps(f"(Get-Process -Id {pid_val} -ErrorAction SilentlyContinue).ProcessName").strip().lower()
                    if "hd-player" in p_name:
                        return [pid_val]
    except Exception:
        pass

    # 2순위: 창 제목에 TITLE('오환2')이 포함된 HD-Player 프로세스 fallback
    out = ps("Get-Process HD-Player -ErrorAction SilentlyContinue | "
             f"Where-Object {{ $_.MainWindowTitle -like '*{TITLE}*' }} | ForEach-Object {{ $_.Id }}")
    return [int(x) for x in out.split() if x.strip().isdigit()]


def adb(args, timeout=20):
    try:
        r = subprocess.run([ADB_EXE] + args, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception:
        return ""


def wait_boot(timeout=240):
    t0 = time.time()
    import adbport
    while time.time() - t0 < timeout:
        dev = adbport.sync(print, scan=time.time() - t0 > 60)     # patch202: 다시 켜면 포트가 바뀔 수 있음
        out = adb(["-s", dev, "shell", "getprop", "sys.boot_completed"])
        if out.strip() == "1":
            print(f"안드로이드 부팅 완료 ({int(time.time() - t0)}초)")
            return True
        time.sleep(5)
    print("부팅 대기 시간 초과")
    return False


# ---------------------------------------------------------------- 뮤뮤 (patch250)
def _mumu_started(info):
    if not info:
        return False
    v = info.get("is_process_started")
    if isinstance(v, bool):
        return v
    return bool(info.get("pid") or info.get("headless_pid"))


def _mumu_pids():
    """뮤뮤 해당 인스턴스가 켜져 있으면 [프로세스 번호] (번호를 모르면 [0]), 꺼져 있거나 확인 불가면 []"""
    info = adbport.mumu_info()
    if not _mumu_started(info):
        return []
    for k in ("pid", "headless_pid"):
        try:
            if int(info.get(k) or 0) > 0:
                return [int(info[k])]
        except (TypeError, ValueError):
            pass
    return [0]


def kill_target():
    """patch250: 뮤뮤 해당 인스턴스만 종료 (MuMuManager control shutdown). 성공/불필요하면 True"""
    if not adbport.IS_MUMU:
        return False
    if not adbport.mumu_manager():
        print("MuMuManager 를 못 찾아 뮤뮤를 끄지 않음 (emu.json 의 mumu_manager 확인)")
        return False
    if not _mumu_started(adbport.mumu_info()):
        return True
    print("뮤뮤(오환2, 인스턴스 %d) 종료" % adbport.MUMU_INDEX)
    adbport.mumu_cmd("control", "-v", adbport.MUMU_INDEX, "shutdown", timeout=60)
    time.sleep(8)
    return True


def restart_mumu():
    """뮤뮤 해당 인스턴스만 종료 후 다시 실행하고 ADB 가 살아날 때까지 기다림. 성공하면 True"""
    mgr = adbport.mumu_manager()
    if not mgr:
        print("MuMuManager 를 못 찾음 -> 재시작 불가 (emu.json 에 mumu_manager 경로 지정)")
        return False
    info = adbport.mumu_info()
    print("대상 뮤뮤 인스턴스:", adbport.MUMU_INDEX, "/ 켜짐:", _mumu_started(info),
          "/ ADB 포트:", (info or {}).get("adb_port"))
    if not GO:
        print("[시험] 실제로는 MuMuManager control -v %d shutdown -> launch 를 실행합니다" % adbport.MUMU_INDEX)
        return True
    if _mumu_started(info):
        kill_target()
    else:
        print("뮤뮤(오환2) 가 꺼져 있어 바로 실행합니다")
    print("뮤뮤(오환2) 다시 실행")
    adbport.mumu_cmd("control", "-v", adbport.MUMU_INDEX, "launch", timeout=60)
    time.sleep(20)
    return wait_boot()


def restart_bluestacks(force=False):
    """'오환2' BlueStacks 만 종료 후 다시 실행하고 ADB 가 살아날 때까지 기다림. 성공하면 True
    patch250: emu.json 이 뮤뮤면 뮤뮤 해당 인스턴스만 재시작 (함수 이름은 호출부 호환 위해 유지)
    patch294f: force=True 지원 및 포트 기반 프로세스 ID 탐색으로 100% 단독 종료/재실행 보장"""
    if adbport.IS_MUMU:
        return restart_mumu()
    pids = find_pids()
    print("대상 HD-Player 프로세스:", pids)
    if len(pids) > 1:
        print("대상이 2개 이상이라 중단합니다 (다른 BlueStacks 를 끄지 않기 위해)")
        return False
    if not GO and not force:
        print("[시험] 실제로는 이 프로세스를 종료하고 BlueStacks 를 다시 실행합니다")
        return True
    if len(pids) == 1:
        print("BlueStacks(오환2) 종료 (PID %d)" % pids[0])
        subprocess.run(["taskkill", "/PID", str(pids[0]), "/F"], capture_output=True)
        time.sleep(8)
    else:
        print("BlueStacks(오환2) 가 꺼져 있어 바로 실행합니다")
    print("BlueStacks(오환2) 다시 실행")
    flags = 0x00000008 | 0x00000200      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["cmd", "/c", "start", "", PLAYER, "--instance", INSTANCE], creationflags=0x08000000)
    time.sleep(20)
    return wait_boot()


if __name__ == "__main__":
    print("성공" if restart_bluestacks() else "실패")