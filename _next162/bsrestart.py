import subprocess, sys, time

from dev import ADB_EXE      # patch162
from dev import SERIAL as DEV
PLAYER = r"C:\Program Files\BlueStacks_nxt\HD-Player.exe"
INSTANCE = "Pie64_3"              # 오환2 인스턴스 이름 (bluestacks.conf 에서 확인)
TITLE = "오환2"                   # BlueStacks 창 제목에 들어 있는 글자
GO = "go" in sys.argv[1:]


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return r.stdout


def find_pids():
    """창 제목에 TITLE 이 들어간 HD-Player 프로세스 번호들 (다른 인스턴스는 건드리지 않음)"""
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
    while time.time() - t0 < timeout:
        adb(["connect", DEV])
        out = adb(["-s", DEV, "shell", "getprop", "sys.boot_completed"])
        if out.strip() == "1":
            print(f"안드로이드 부팅 완료 ({int(time.time() - t0)}초)")
            return True
        time.sleep(5)
    print("부팅 대기 시간 초과")
    return False


def restart_bluestacks():
    """'오환2' BlueStacks 만 종료 후 다시 실행하고 ADB 가 살아날 때까지 기다림. 성공하면 True"""
    pids = find_pids()
    print("대상 HD-Player 프로세스:", pids)
    if len(pids) > 1:
        print("대상이 2개 이상이라 중단합니다 (다른 BlueStacks 를 끄지 않기 위해)")
        return False
    if not GO:
        print("[시험] 실제로는 이 프로세스를 종료하고 BlueStacks 를 다시 실행합니다")
        return True
    if len(pids) == 1:
        print("BlueStacks(오환2) 종료")
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