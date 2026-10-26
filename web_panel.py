# -*- coding: utf-8 -*-
"""web_panel.py - 오환2 & 표키2 통합 웹 대시보드 및 원격 제어 서버 (고도화 버전)
사용법:
  py web_panel.py             (기본 포트: 5000)
  py web_panel.py --port 8080 (포트 지정)
브라우저 접속:
  http://localhost:5000
"""
import os, sys, json, time, glob, socket, subprocess, ctypes, threading
from flask import Flask, render_template, jsonify, request

BASE_OHWAN = r"C:\macro"
BASE_PYOKEY = r"C:\pyokey"
CREATE_NO_WINDOW = 0x08000000

app = Flask(__name__, template_folder=os.path.join(BASE_OHWAN, "templates"))


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def is_pid_alive(pid):
    """Windows API로 콘솔 창 깜빡임 없이 프로세스 생존 여부 확인"""
    try:
        pid = int(pid)
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    except Exception:
        return False


def check_tcp_port(port):
    """지정 포트 TCP 연결 가능 여부 빠른 확인"""
    s = socket.socket()
    s.settimeout(0.2)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


def get_pid_from_file(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                p = f.read().strip()
                if p.isdigit():
                    return int(p)
    except Exception:
        pass
    return None


def read_json_file(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def write_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    # ---------------- 1. 에뮬레이터 연결 상태 ----------------
    ohwan_emu_online = check_tcp_port(5585)
    pyokey_emu_online = check_tcp_port(5595)

    # ---------------- 2. 오환2 상태 및 정밀 진단 ----------------
    ohwan_pid = get_pid_from_file(os.path.join(BASE_OHWAN, "main.pid"))
    ohwan_running = is_pid_alive(ohwan_pid) if ohwan_pid else False
    ohwan_paused = os.path.exists(os.path.join(BASE_OHWAN, "PAUSE")) or os.path.exists(os.path.join(BASE_OHWAN, "PAUSED"))
    state_ohwan = read_json_file(os.path.join(BASE_OHWAN, "state.json"))
    settings_ohwan = read_json_file(os.path.join(BASE_OHWAN, "settings.json"))

    # 진단 상태 결정
    if not ohwan_emu_online:
        ohwan_state = "emu_offline"
        ohwan_diag = "BlueStacks 에뮬레이터(127.0.0.1:5585)가 꺼져 있습니다. BlueStacks(오환2)를 실행해 주세요."
    elif not ohwan_running:
        ohwan_state = "stopped"
        ohwan_diag = "에뮬레이터 정상 연결됨. 오환2 매크로 프로세스가 중지 상태입니다. ▶ [시작] 버튼을 눌러주세요."
    elif ohwan_paused:
        ohwan_state = "paused"
        ohwan_diag = "매크로가 안전 지점에서 일시정지(PAUSED) 상태입니다. ⏸ [재개]를 누르면 이어서 진행됩니다."
    else:
        ohwan_state = "running"
        ohwan_diag = "오환2 매크로가 정상 실행 중입니다 (PID: %d, 최고 %s층)." % (
            ohwan_pid, state_ohwan.get("peak_wave") or "측정중")

    # 종족 한글 변환
    tr = state_ohwan.get("reborn_tribe")
    sc = state_ohwan.get("reborn_tribe_score")
    tr_map = {"HUMAN": "인간 (불의정령)", "ELF": "엘프", "UNDEAD": "언데드", "ORC": "오크", "UNKNOWN": "미인식"}
    tr_text = tr_map.get(tr, tr or "미확인")
    if sc is not None:
        tr_text += " (%.2f)" % float(sc)

    # 보석 영입 남은 영웅 및 무료 영입 쿨타임 통합
    gem_hero_data = read_json_file(os.path.join(BASE_OHWAN, "recruit_left.json"))
    gem_hero = gem_hero_data.get("name") if gem_hero_data else None

    next_rec = state_ohwan.get("next_recruit")
    rec_time_str = "무료 영입 가능"
    if next_rec:
        diff = int(next_rec - time.time())
        if diff > 0:
            rec_time_str = "%d분 %d초 뒤" % (diff // 60, diff % 60)

    if gem_hero:
        recruit_summary = "%s (보석) · %s" % (gem_hero, rec_time_str)
    else:
        recruit_summary = rec_time_str

    # 환생 기록
    rebirths = []
    for r in state_ohwan.get("rebirths") or []:
        r_copy = dict(r)
        if "t" in r_copy:
            r_copy["time_str"] = time.strftime("%m-%d %H:%M:%S", time.localtime(r_copy["t"]))
        rebirths.append(r_copy)

    # 유물 공방 모드 판정
    if settings_ohwan.get("hexa_every", False):
        hexa_mode = "every"
    elif settings_ohwan.get("hexa_auto", True):
        hexa_mode = "full"
    else:
        hexa_mode = "off"

    # 녹화 설정 판독
    rec_cfg = read_json_file(os.path.join(BASE_OHWAN, "rec_cfg.json"))
    rec_files = sorted(glob.glob(os.path.join(BASE_OHWAN, "shots", "rec", "*.mp4")), key=os.path.getmtime)
    latest_rec = os.path.basename(rec_files[-1]) if rec_files else "녹화 파일 없음"

    # 오환2 실시간 로그 (최근 40줄)
    ohwan_logs = []
    log_path = os.path.join(BASE_OHWAN, "macro.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                ohwan_logs = [l.rstrip("\r\n") for l in lines[-40:]]
        except Exception:
            pass

    # ---------------- 3. 표키2 상태 및 정밀 진단 ----------------
    pyokey_pid = get_pid_from_file(os.path.join(BASE_PYOKEY, "main.pid"))
    pyokey_running = is_pid_alive(pyokey_pid) if pyokey_pid else False
    pyokey_paused = os.path.exists(os.path.join(BASE_PYOKEY, "PAUSE"))
    state_pyokey = read_json_file(os.path.join(BASE_PYOKEY, "state.json"))
    settings_pyokey = read_json_file(os.path.join(BASE_PYOKEY, "settings.json"))

    if not pyokey_emu_online:
        pyokey_state = "emu_offline"
        pyokey_diag = "BlueStacks 에뮬레이터(127.0.0.1:5595)가 꺼져 있습니다. BlueStacks(표키)를 실행해 주세요."
    elif not pyokey_running:
        pyokey_state = "stopped"
        pyokey_diag = "에뮬레이터 정상 연결됨. 표키2 매크로가 중지 상태입니다. ▶ [시작] 버튼을 눌러주세요."
    elif pyokey_paused:
        pyokey_state = "paused"
        pyokey_diag = "표키2 매크로가 일시정지 중입니다."
    else:
        pyokey_state = "running"
        pyokey_diag = "표키2 매크로가 정상 실행 중입니다 (PID: %d)." % pyokey_pid

    # 루비 쿨타임
    ruby_next = state_pyokey.get("ruby_next")
    ruby_st = "-"
    if ruby_next:
        diff_r = int(ruby_next - time.time())
        ruby_st = "쿨타임 대기 (%d분 %d초 뒤)" % (diff_r // 60, diff_r % 60) if diff_r > 0 else "루비 수령 가능"

    # 표키2 실시간 로그 (최근 로그 파일 tail)
    pyokey_logs = []
    py_log_files = sorted(glob.glob(os.path.join(BASE_PYOKEY, "logs", "*.log")))
    if py_log_files:
        try:
            with open(py_log_files[-1], "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                pyokey_logs = [l.rstrip("\r\n") for l in lines[-40:]]
        except Exception:
            pass

    return jsonify({
        "ohwan": {
            "state": ohwan_state,
            "diag_msg": ohwan_diag,
            "running": ohwan_running,
            "pid": ohwan_pid if ohwan_running else None,
            "paused": ohwan_paused,
            "peak_wave": state_ohwan.get("peak_wave", 0),
            "tribe_text": tr_text,
            "cont_used": state_ohwan.get("cont_used", 0),
            "cont_limit": settings_ohwan.get("fall_continue_n", 3),
            "hexa_mode": hexa_mode,
            "recruit_summary": recruit_summary,
            "gem_hero": gem_hero,
            "rebirths": rebirths,
            "settings": settings_ohwan,
            "recording": {
                "enabled": rec_cfg.get("enabled", False),
                "remain_runs": rec_cfg.get("remain_runs", 0),
                "start_wave": rec_cfg.get("start_wave", 7500),
                "stop_wave": rec_cfg.get("stop_wave", 8050),
                "latest_file": latest_rec
            },
            "logs": ohwan_logs
        },
        "pyokey": {
            "state": pyokey_state,
            "diag_msg": pyokey_diag,
            "running": pyokey_running,
            "pid": pyokey_pid if pyokey_running else None,
            "paused": pyokey_paused,
            "ruby_status": ruby_st,
            "tickets": state_pyokey.get("tickets", {}),
            "recharge": state_pyokey.get("recharge", {}).get("n", 0),
            "settings": settings_pyokey,
            "logs": pyokey_logs
        },
        "emulators": {
            "ohwan": {"port": 5585, "online": ohwan_emu_online, "pkg": "com.ekkorr.ef2"},
            "pyokey": {"port": 5595, "online": pyokey_emu_online, "pkg": "com.mouseduck.boomerang"}
        }
    })


@app.route("/api/action", methods=["POST"])
def do_action():
    data = request.get_json() or {}
    action = data.get("action")

    # ---------------- 오환2 매크로 제어 ----------------
    if action == "ohwan_start":
        pid = get_pid_from_file(os.path.join(BASE_OHWAN, "main.pid"))
        if pid and is_pid_alive(pid):
            return jsonify({"ok": True, "msg": "오환2가 이미 실행 중입니다 (PID: %d)" % pid})
        try:
            p = subprocess.Popen([sys.executable, "main.py", "go"], cwd=BASE_OHWAN, creationflags=CREATE_NO_WINDOW)
            with open(os.path.join(BASE_OHWAN, "main.pid"), "w", encoding="utf-8") as f:
                f.write(str(p.pid))
            return jsonify({"ok": True, "msg": "오환2 매크로를 시작했습니다 (PID: %d)" % p.pid})
        except Exception as e:
            return jsonify({"ok": False, "msg": "시작 실패: %r" % (e,)})

    elif action == "ohwan_restart":
        pid = get_pid_from_file(os.path.join(BASE_OHWAN, "main.pid"))
        def do_restart():
            if pid and is_pid_alive(pid):
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
                time.sleep(1.5)
            p = subprocess.Popen([sys.executable, "main.py", "go"], cwd=BASE_OHWAN, creationflags=CREATE_NO_WINDOW)
            with open(os.path.join(BASE_OHWAN, "main.pid"), "w", encoding="utf-8") as f:
                f.write(str(p.pid))
            req_file = os.path.join(BASE_OHWAN, "restart_main.req")
            if os.path.exists(req_file):
                try: os.remove(req_file)
                except Exception: pass
        threading.Thread(target=do_restart, daemon=True).start()
        return jsonify({"ok": True, "msg": "오환2 매크로 재시작을 진행 중입니다."})

    elif action == "ohwan_stop":
        pid = get_pid_from_file(os.path.join(BASE_OHWAN, "main.pid"))
        if not pid or not is_pid_alive(pid):
            return jsonify({"ok": True, "msg": "오환2가 이미 중지 상태입니다."})
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            time.sleep(0.5)
            try:
                os.remove(os.path.join(BASE_OHWAN, "main.pid"))
            except Exception:
                pass
            return jsonify({"ok": True, "msg": "오환2 매크로(PID %d)를 안전하게 중지했습니다." % pid})
        except Exception as e:
            return jsonify({"ok": False, "msg": "중지 오류: %r" % (e,)})

    elif action == "ohwan_pause":
        p_file = os.path.join(BASE_OHWAN, "PAUSE")
        pd_file = os.path.join(BASE_OHWAN, "PAUSED")
        if os.path.exists(p_file) or os.path.exists(pd_file):
            if os.path.exists(p_file): os.remove(p_file)
            if os.path.exists(pd_file): os.remove(pd_file)
            return jsonify({"ok": True, "msg": "일시정지를 해제하고 매크로를 재개했습니다."})
        else:
            with open(p_file, "w", encoding="utf-8") as f:
                f.write("pause")
            return jsonify({"ok": True, "msg": "일시정지 신호를 보냈습니다 (안전 지점에서 일시정지)"})

    elif action == "ohwan_opt_set":
        key = data.get("key")
        val = data.get("val")
        st_path = os.path.join(BASE_OHWAN, "settings.json")
        cfg = read_json_file(st_path)
        cfg[key] = val
        write_json_file(st_path, cfg)
        return jsonify({"ok": True, "msg": "오환2 옵션 '%s'이(가) %s(으)로 변경되었습니다." % (key, val)})

    elif action == "ohwan_hexa_mode_set":
        mode = data.get("mode", "full")
        st_path = os.path.join(BASE_OHWAN, "settings.json")
        cfg = read_json_file(st_path)
        if mode == "off":
            cfg["hexa_auto"] = False
            cfg["hexa_every"] = False
            msg = "유물 공방 자동 플레이를 [사용 안 함]으로 설정했습니다."
        elif mode == "every":
            cfg["hexa_auto"] = True
            cfg["hexa_every"] = True
            msg = "유물 공방을 [환생마다 (1장 이상)] 자동 플레이하도록 설정했습니다."
        else:
            cfg["hexa_auto"] = True
            cfg["hexa_every"] = False
            msg = "유물 공방을 [티켓 꽉 차면 (5/5)] 자동 플레이하도록 설정했습니다."
        write_json_file(st_path, cfg)
        return jsonify({"ok": True, "msg": msg})

    elif action == "ohwan_bs_restart":
        def run_bs():
            subprocess.run([sys.executable, "bsrestart.py", "go"], cwd=BASE_OHWAN, creationflags=CREATE_NO_WINDOW)
        threading.Thread(target=run_bs, daemon=True).start()
        return jsonify({"ok": True, "msg": "BlueStacks(오환2) 단독 재시작 작업을 백그라운드에서 시작했습니다."})

    elif action == "ohwan_oneshot":
        job = data.get("job")
        job_map = {
            "daily": ("일일 작업", ["daily.py", "go"]),
            "dungeon": ("던전 소탕", ["dungeon.py", "go"]),
            "archery": ("양궁 1판", ["arch2.py", "play", "go"]),
            "fossil": ("화석 발굴", ["fossil.py", "go"]),
            "hexa": ("유물 공방 1판", ["hexa.py", "play", "go", "1"]),
            "recruit": ("무료 영입", ["recruit.py", "go"]),
            "cap": ("화면 캡처", ["cap.py"]),
            "uitour": ("UI 점검 투어", ["uitour.py", "go"]),
            "cleanup": ("임시파일 정리", ["cleanup.py", "go"])
        }
        if job in job_map:
            label, cmd = job_map[job]
            def run_job():
                subprocess.run([sys.executable] + cmd, cwd=BASE_OHWAN, creationflags=CREATE_NO_WINDOW)
            threading.Thread(target=run_job, daemon=True).start()
            return jsonify({"ok": True, "msg": "'%s' 단발 실행을 시작했습니다." % label})
        return jsonify({"ok": False, "msg": "알 수 없는 단발 작업입니다."})

    elif action == "ohwan_rec_set":
        runs = int(data.get("runs", 3))
        cfg_path = os.path.join(BASE_OHWAN, "rec_cfg.json")
        cfg = read_json_file(cfg_path, {"start_wave": 7500, "stop_wave": 8050, "fps": 15, "max_sec": 1800})
        cfg["enabled"] = runs > 0
        cfg["remain_runs"] = runs
        write_json_file(cfg_path, cfg)
        return jsonify({"ok": True, "msg": "고층 자동 녹화를 %d회분 설정했습니다." % runs})

    elif action == "open_recording":
        try:
            rec_files = sorted(glob.glob(os.path.join(BASE_OHWAN, "shots", "rec", "*.mp4")), key=os.path.getmtime)
            if not rec_files:
                return jsonify({"ok": False, "msg": "저장된 녹화 영상 파일이 없습니다."})
            latest = rec_files[-1]
            os.startfile(latest)
            return jsonify({"ok": True, "msg": "최근 녹화 영상 열기: %s" % os.path.basename(latest)})
        except Exception as e:
            return jsonify({"ok": False, "msg": "영상 열기 실패: %r" % (e,)})

    elif action == "telegram_test":
        try:
            from telegram_bot import send_telegram
            ok = send_telegram("🔔 <b>[웹 대시보드]</b> 텔레그램 연동 정상 작동 테스트입니다.", silent=False, block=True)
            return jsonify({"ok": ok, "msg": "텔레그램 테스트 알림을 발송했습니다." if ok else "전송 실패 (telegram.json 확인)"})
        except Exception as e:
            return jsonify({"ok": False, "msg": "텔레그램 전송 오류: %r" % (e,)})

    # ---------------- 표키2 매크로 제어 ----------------
    elif action == "pyokey_start":
        pid = get_pid_from_file(os.path.join(BASE_PYOKEY, "main.pid"))
        if pid and is_pid_alive(pid):
            return jsonify({"ok": True, "msg": "표키2가 이미 실행 중입니다 (PID: %d)" % pid})
        try:
            p = subprocess.Popen([sys.executable, "main.py"], cwd=BASE_PYOKEY, creationflags=CREATE_NO_WINDOW)
            with open(os.path.join(BASE_PYOKEY, "main.pid"), "w", encoding="utf-8") as f:
                f.write(str(p.pid))
            return jsonify({"ok": True, "msg": "표키2 매크로를 시작했습니다 (PID: %d)" % p.pid})
        except Exception as e:
            return jsonify({"ok": False, "msg": "표키2 시작 실패: %r" % (e,)})

    elif action == "pyokey_restart":
        pid = get_pid_from_file(os.path.join(BASE_PYOKEY, "main.pid"))
        def do_py_restart():
            if pid and is_pid_alive(pid):
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
                time.sleep(1.5)
            p = subprocess.Popen([sys.executable, "main.py", "go"], cwd=BASE_PYOKEY, creationflags=CREATE_NO_WINDOW)
            with open(os.path.join(BASE_PYOKEY, "main.pid"), "w", encoding="utf-8") as f:
                f.write(str(p.pid))
            req_file = os.path.join(BASE_PYOKEY, "restart.req")
            if os.path.exists(req_file):
                try: os.remove(req_file)
                except Exception: pass
        threading.Thread(target=do_py_restart, daemon=True).start()
        return jsonify({"ok": True, "msg": "표키2 매크로 재시작을 진행 중입니다."})

    elif action == "pyokey_stop":
        pid = get_pid_from_file(os.path.join(BASE_PYOKEY, "main.pid"))
        if not pid or not is_pid_alive(pid):
            return jsonify({"ok": True, "msg": "표키2가 이미 중지 상태입니다."})
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            time.sleep(0.5)
            try:
                os.remove(os.path.join(BASE_PYOKEY, "main.pid"))
            except Exception:
                pass
            return jsonify({"ok": True, "msg": "표키2 매크로(PID %d)를 안전하게 중지했습니다." % pid})
        except Exception as e:
            return jsonify({"ok": False, "msg": "표키2 중지 오류: %r" % (e,)})

    elif action == "pyokey_pause":
        pause_f = os.path.join(BASE_PYOKEY, "PAUSE")
        if os.path.exists(pause_f):
            os.remove(pause_f)
            return jsonify({"ok": True, "msg": "표키2 일시정지를 해제하고 재개했습니다."})
        else:
            with open(pause_f, "w", encoding="utf-8") as f:
                f.write("pause")
            return jsonify({"ok": True, "msg": "표키2 일시정지 신호를 보냈습니다."})

    elif action == "pyokey_run_now":
        key = data.get("key", "")
        names = {
            "pass": "패스 보상 수령",
            "weekly": "주간 미션",
            "oneday": "일퀘 묶음 (우편/이벤트/일일미션)",
            "ruby": "무료 루비/광고",
            "guild": "길드 출석/상점",
            "starshop": "별빛 교환소",
            "burning": "버닝 모드"
        }
        name = names.get(key, key)
        try:
            with open(os.path.join(BASE_PYOKEY, "RUN_NOW"), "w", encoding="utf-8") as f:
                f.write(key)
            return jsonify({"ok": True, "msg": "표키2 [%s] 작업을 즉시 실행하도록 요청했습니다." % name})
        except Exception as e:
            return jsonify({"ok": False, "msg": "즉시 실행 요청 실패: %r" % (e,)})

    elif action == "pyokey_oneshot":
        job = data.get("job")
        if job == "cap":
            try:
                subprocess.run([sys.executable, "cap.py"], cwd=BASE_PYOKEY, creationflags=CREATE_NO_WINDOW)
                return jsonify({"ok": True, "msg": "표키2 화면 캡처 저장: C:\\pyokey\\shots"})
            except Exception as e:
                return jsonify({"ok": False, "msg": "표키2 캡처 실패: %r" % (e,)})
        return jsonify({"ok": False, "msg": "알 수 없는 작업입니다."})

    elif action == "pyokey_opt_set":
        key = data.get("key")
        val = data.get("val")
        st_path = os.path.join(BASE_PYOKEY, "settings.json")
        cfg = read_json_file(st_path)
        if key == "merge":
            if "merge" not in cfg or not isinstance(cfg["merge"], dict):
                cfg["merge"] = {}
            cfg["merge"]["on"] = bool(val)
        else:
            if key in cfg and isinstance(cfg[key], dict):
                cfg[key]["on"] = bool(val)
        write_json_file(st_path, cfg)
        return jsonify({"ok": True, "msg": "표키2 설정 [%s]이(가) 변경되었습니다." % key})

    elif action == "pyokey_reset_day":
        st_path = os.path.join(BASE_PYOKEY, "state.json")
        try:
            st = read_json_file(st_path)
            keep = ("ev_G_day", "ev_P_day")
            for k in list(st.keys()):
                if (k.endswith("_day") or k.endswith("_ok")) and k not in keep:
                    st.pop(k, None)
            write_json_file(st_path, st)
            return jsonify({"ok": True, "msg": "표키2 오늘 완료 기록을 초기화했습니다 (다음 루프부터 오늘 숙제를 다시 수행합니다)."})
        except Exception as e:
            return jsonify({"ok": False, "msg": "기록 초기화 실패: %r" % (e,)})

    return jsonify({"ok": False, "msg": "알 수 없는 작업 요청입니다."})


if __name__ == "__main__":
    port = 5000
    for i, arg in enumerate(sys.argv):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    print(f"==================================================")
    print(f"  오환2 & 표키2 통합 웹 대시보드 서버 (고도화 버전)")
    print(f"  브라우저 접속 주소: http://localhost:{port}")
    print(f"  종료하려면 Ctrl + C 를 누르세요.")
    print(f"==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
