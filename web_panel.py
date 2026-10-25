# -*- coding: utf-8 -*-
"""web_panel.py - 오환2 & 표키2 통합 웹 대시보드 및 원격 제어 서버
사용법:
  py web_panel.py             (기본 포트: 5000)
  py web_panel.py --port 8080 (포트 지정)
브라우저 접속:
  http://localhost:5000
"""
import os, sys, json, time, glob, socket, subprocess, ctypes
from flask import Flask, render_template, jsonify, request

BASE_OHWAN = r"C:\macro"
BASE_PYOKEY = r"C:\pyokey"
CREATE_NO_WINDOW = 0x08000000

app = Flask(__name__, template_folder=os.path.join(BASE_OHWAN, "templates"))


def is_pid_alive(pid):
    """Windows API로 콘솔 창 없이 PID 생존 여부 확인"""
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    # 1. 오환2 상태 판독
    ohwan_pid = get_pid_from_file(os.path.join(BASE_OHWAN, "main.pid"))
    ohwan_running = is_pid_alive(ohwan_pid) if ohwan_pid else False
    ohwan_paused = os.path.exists(os.path.join(BASE_OHWAN, "PAUSE")) or os.path.exists(os.path.join(BASE_OHWAN, "PAUSED"))

    state_ohwan = {}
    state_file = os.path.join(BASE_OHWAN, "state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_ohwan = json.load(f)
        except Exception:
            pass

    # 종족 한글 변환
    tr = state_ohwan.get("reborn_tribe")
    sc = state_ohwan.get("reborn_tribe_score")
    tr_map = {"HUMAN": "인간 (불의정령)", "ELF": "엘프", "UNDEAD": "언데드", "ORC": "오크", "UNKNOWN": "미인식"}
    tr_text = tr_map.get(tr, tr or "미확인")
    if sc is not None:
        tr_text += " (%.2f)" % float(sc)

    # 영입 상태
    rec_st = "-"
    next_rec = state_ohwan.get("next_recruit")
    if next_rec:
        diff = int(next_rec - time.time())
        if diff > 0:
            rec_st = "쿨타임 대기 (%d분 %d초 뒤)" % (diff // 60, diff % 60)
        else:
            rec_st = "영입 가능 상태"

    # 환생 목록 시간 가공
    rebirths = []
    for r in state_ohwan.get("rebirths") or []:
        r_copy = dict(r)
        if "t" in r_copy:
            r_copy["time_str"] = time.strftime("%m-%d %H:%M:%S", time.localtime(r_copy["t"]))
        rebirths.append(r_copy)

    # 녹화 설정 판독
    rec_cfg = {}
    rec_cfg_file = os.path.join(BASE_OHWAN, "rec_cfg.json")
    if os.path.exists(rec_cfg_file):
        try:
            with open(rec_cfg_file, "r", encoding="utf-8") as f:
                rec_cfg = json.load(f)
        except Exception:
            pass

    # 최신 녹화 파일
    rec_files = sorted(glob.glob(os.path.join(BASE_OHWAN, "shots", "rec", "*.mp4")), key=os.path.getmtime)
    latest_rec = os.path.basename(rec_files[-1]) if rec_files else "녹화 파일 없음"

    # 2. 표키2 상태 판독
    pyokey_pid = get_pid_from_file(os.path.join(BASE_PYOKEY, "main.pid"))
    pyokey_running = is_pid_alive(pyokey_pid) if pyokey_pid else False

    # 3. 에뮬레이터 포트 판독
    ohwan_emu_online = check_tcp_port(5585)
    pyokey_emu_online = check_tcp_port(5595)

    # 4. 실시간 로그 (최근 35줄)
    log_lines = []
    log_path = os.path.join(BASE_OHWAN, "macro.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                log_lines = [l.rstrip("\r\n") for l in lines[-35:]]
        except Exception:
            pass

    return jsonify({
        "ohwan": {
            "running": ohwan_running,
            "pid": ohwan_pid if ohwan_running else None,
            "paused": ohwan_paused,
            "peak_wave": state_ohwan.get("peak_wave", 0),
            "tribe_text": tr_text,
            "cont_used": state_ohwan.get("cont_used", 0),
            "recruit_status": rec_st,
            "rebirths": rebirths
        },
        "pyokey": {
            "running": pyokey_running,
            "pid": pyokey_pid if pyokey_running else None
        },
        "emulators": {
            "ohwan_online": ohwan_emu_online,
            "pyokey_online": pyokey_emu_online
        },
        "recording": {
            "enabled": rec_cfg.get("enabled", False),
            "remain_runs": rec_cfg.get("remain_runs", 0),
            "start_wave": rec_cfg.get("start_wave", 7500),
            "stop_wave": rec_cfg.get("stop_wave", 8050),
            "latest_file": latest_rec
        },
        "logs": log_lines
    })


@app.route("/api/action", methods=["POST"])
def do_action():
    data = request.get_json() or {}
    action = data.get("action")

    if action == "ohwan_start":
        pid = get_pid_from_file(os.path.join(BASE_OHWAN, "main.pid"))
        if pid and is_pid_alive(pid):
            return jsonify({"ok": True, "msg": "오환2가 이미 실행 중입니다 (PID: %d)" % pid})
        try:
            p = subprocess.Popen(
                [sys.executable, "main.py", "go"],
                cwd=BASE_OHWAN,
                creationflags=CREATE_NO_WINDOW
            )
            with open(os.path.join(BASE_OHWAN, "main.pid"), "w", encoding="utf-8") as f:
                f.write(str(p.pid))
            return jsonify({"ok": True, "msg": "오환2 매크로를 시작했습니다 (PID: %d)" % p.pid})
        except Exception as e:
            return jsonify({"ok": False, "msg": "시작 실패: %r" % (e,)})

    elif action == "ohwan_restart":
        # restart_main.req 요청 파일 생성 (패널/hub가 감지해 재시작)
        req_file = os.path.join(BASE_OHWAN, "restart_main.req")
        try:
            with open(req_file, "w", encoding="utf-8") as f:
                f.write("restart")
            return jsonify({"ok": True, "msg": "오환2 재시작을 요청했습니다 (restart_main.req)"})
        except Exception as e:
            return jsonify({"ok": False, "msg": "재시작 요청 실패: %r" % (e,)})

    elif action == "ohwan_stop":
        pid = get_pid_from_file(os.path.join(BASE_OHWAN, "main.pid"))
        if not pid or not is_pid_alive(pid):
            return jsonify({"ok": True, "msg": "오환2가 실행 중이 아닙니다."})
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
        pause_file = os.path.join(BASE_OHWAN, "PAUSE")
        paused_file = os.path.join(BASE_OHWAN, "PAUSED")
        if os.path.exists(pause_file) or os.path.exists(paused_file):
            try:
                if os.path.exists(pause_file): os.remove(pause_file)
                if os.path.exists(paused_file): os.remove(paused_file)
                return jsonify({"ok": True, "msg": "일시정지를 해제하고 매크로를 재개했습니다."})
            except Exception as e:
                return jsonify({"ok": False, "msg": "일시정지 해제 오류: %r" % (e,)})
        else:
            try:
                with open(pause_file, "w", encoding="utf-8") as f:
                    f.write("pause")
                return jsonify({"ok": True, "msg": "일시정지 신호를 보냈습니다 (안전 지점에서 정지)"})
            except Exception as e:
                return jsonify({"ok": False, "msg": "일시정지 설정 오류: %r" % (e,)})

    elif action == "telegram_test":
        try:
            from telegram_bot import send_telegram
            ok = send_telegram("🔔 <b>[웹 패널]</b> 텔레그램 연동 테스트 알림입니다.", silent=False, block=True)
            return jsonify({"ok": ok, "msg": "텔레그램 테스트 알림을 전송했습니다." if ok else "전송 실패 (telegram.json 확인)"})
        except Exception as e:
            return jsonify({"ok": False, "msg": "텔레그램 오류: %r" % (e,)})

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

    elif action == "toggle_rec":
        try:
            cfg_path = os.path.join(BASE_OHWAN, "rec_cfg.json")
            cfg = {"enabled": True, "remain_runs": 3, "start_wave": 7500, "stop_wave": 8050, "fps": 15, "max_sec": 1800}
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            cfg["enabled"] = True
            cfg["remain_runs"] = 3
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            return jsonify({"ok": True, "msg": "앞으로 3회 환생 사이클 동안 7500~8050 구간 자동 녹화를 장전했습니다."})
        except Exception as e:
            return jsonify({"ok": False, "msg": "녹화 설정 변경 실패: %r" % (e,)})

    elif action == "pyokey_toggle":
        pid = get_pid_from_file(os.path.join(BASE_PYOKEY, "main.pid"))
        if pid and is_pid_alive(pid):
            # 표키 재시작 요청
            req = os.path.join(BASE_PYOKEY, "restart.req")
            with open(req, "w", encoding="utf-8") as f:
                f.write("restart")
            return jsonify({"ok": True, "msg": "표키2 매크로 재시작을 요청했습니다."})
        else:
            try:
                p = subprocess.Popen([sys.executable, "main.py"], cwd=BASE_PYOKEY, creationflags=CREATE_NO_WINDOW)
                with open(os.path.join(BASE_PYOKEY, "main.pid"), "w", encoding="utf-8") as f:
                    f.write(str(p.pid))
                return jsonify({"ok": True, "msg": "표키2 매크로를 시작했습니다 (PID: %d)" % p.pid})
            except Exception as e:
                return jsonify({"ok": False, "msg": "표키2 시작 실패: %r" % (e,)})

    return jsonify({"ok": False, "msg": "알 수 없는 작업 요청입니다."})


if __name__ == "__main__":
    port = 5000
    for i, arg in enumerate(sys.argv):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    print(f"==================================================")
    print(f"  오환2 & 표키2 통합 웹 대시보드 서버 시작")
    print(f"  브라우저 접속 주소: http://localhost:{port}")
    print(f"  중지하려면 Ctrl + C 를 누르세요.")
    print(f"==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
