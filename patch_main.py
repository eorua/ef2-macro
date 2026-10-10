import re, shutil, sys

SRC = r"C:\macro\main.py"
src = open(SRC, encoding="utf-8").read()
shutil.copyfile(SRC, SRC + ".bak")          # 백업
n = 0


def rep(old, new, count=1):
    global src, n
    if old not in src:
        print("못 찾음:", old[:50].replace("\n", " "))
        sys.exit(1)
    src = src.replace(old, new, count)
    n += 1


# 1) 모듈 불러오기
rep("import rebirth, wave, preset, recruit", "import rebirth, wave, preset, recruit, bsrestart, activate")

# 2) 게임 실행: monkey 방식
m = re.search(r"def launch_game\(\):\n(?:[ \t]+.*\n)+", src)
if not m:
    print("launch_game 못 찾음"); sys.exit(1)
src = src[:m.start()] + '''def launch_game():
    log("게임 실행")
    adb_out(["shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1"])


def restart_bluestacks_full():
    """오환2 BlueStacks 자체를 껐다 켜고 게임까지 실행"""
    log("BlueStacks(오환2) 재시작")
    if not bsrestart.restart_bluestacks():
        log("BlueStacks 재시작 실패")
        return False
    time.sleep(10)
    launch_game()
    return True


def after_restart_setup(st):
    """재시작 후: 영웅/유물 프리셋 활성화 -> 현재 단계에 맞는 프리셋 선택"""
    img = cap()
    if img is not None and (fall_popup(img)[0] or result_popup(img)[0]):
        log("환생 팝업이 떠 있어 프리셋 설정은 건너뜀")
        return
    ok = activate.activate_presets()
    log("프리셋 활성화: " + ("성공" if ok else "실패"))
    hero, relic = ("렙뻥", "기본") if st.get("high_done") else ("기본", "시간")
    ok2 = preset.set_presets(hero, relic)
    log(f"프리셋 선택({hero}/{relic}): " + ("성공" if ok2 else "실패"))
    if not st.get("high_done"):
        st["need_low"] = False if ok2 else True
    save_state(st)


''' + src[m.end():]
n += 1

# 3) do_restart: 정기=BlueStacks 전체, 튕김=게임 실행 -> 게임 재시작 -> BlueStacks 재시작
m = re.search(r"def do_restart\(kind\):\n(?:(?:[ \t]+.*)?\n)+?(?=def main\(\))", src)
if not m:
    print("do_restart 못 찾음"); sys.exit(1)
src = src[:m.start()] + '''def do_restart(kind, st=None):
    """kind: '정기' 또는 '튕김'. 성공하면 True"""
    if st is None:
        st = load_state()
    for attempt in range(1, MAX_RECOVER_FAILS + 1):
        log(f"{kind} 재시작 시도 {attempt}/{MAX_RECOVER_FAILS}")
        if kind == "정기" or attempt == MAX_RECOVER_FAILS:
            started = restart_bluestacks_full()
        elif attempt == 1:
            launch_game()
            started = True
        else:
            restart_game()
            started = True
        if started and recover():
            after_restart_setup(st)
            return True
    log("재시작 복구 실패 → 5분 후 다시 확인")
    return False


''' + src[m.end():]
n += 1

# 4) 호출부에 st 전달
rep('do_restart("튕김")', 'do_restart("튕김", st)')
rep('do_restart("정기"):\n                        st["last_restart"]', 'do_restart("정기", st):\n                        st["last_restart"]')

open(SRC, "w", encoding="utf-8").write(src)
print(f"패치 완료 ({n}곳). 백업: main.py.bak")