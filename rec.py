# -*- coding: utf-8 -*-
"""rec.py - 7500~8000 고층 구간 자동 녹화 제어 및 영상 관리 도구

사용법 (C:\\macro 에서)
  py rec.py                현재 녹화 설정 및 최근 영상 목록 확인
  py rec.py on             고층 구간(7500~8000) 녹화 켜기 (기본 5판)
  py rec.py on 3           3판만 녹화
  py rec.py off            녹화 끄기
  py rec.py set 7400 8100  시작/종료 웨이브 변경
  py rec.py list           저장된 영상 목록 상세 확인
  py rec.py open [파일명]  영상 파일 재생 (인자 없으면 가장 최근 영상)
"""
import os, sys, time, json

BASE = os.path.dirname(os.path.abspath(__file__))
REC_DIR = os.path.join(BASE, "shots", "rec")
CFG_PATH = os.path.join(BASE, "rec_cfg.json")

DEFAULT_CFG = {
    "enabled": False,
    "start_wave": 7500,
    "stop_wave": 8050,
    "remain_runs": 5,
    "fps": 15,
    "max_sec": 25 * 60,
}


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print("[rec] 설정 저장 실패: %r" % (e,))
        return False


def get_videos():
    if not os.path.exists(REC_DIR):
        return []
    files = []
    for f in os.listdir(REC_DIR):
        if f.endswith(".mp4"):
            p = os.path.join(REC_DIR, f)
            st = os.stat(p)
            files.append((f, st.st_size, st.st_mtime, p))
    files.sort(key=lambda x: x[2], reverse=True)
    return files


def status():
    cfg = load_cfg()
    print("=" * 60)
    print("  오환2 고층 구간(7500 ~ 8000) 자동 녹화 상태")
    print("=" * 60)
    st_str = "활성 (ON)" if (cfg.get("enabled") and cfg.get("remain_runs", 0) > 0) else "비활성 (OFF)"
    print("  녹화 동작: %s" % st_str)
    print("  녹화 구간: %d층 ~ %d층 (도달 시 자동 저장 후 종료)" % (cfg.get("start_wave", 7500), cfg.get("stop_wave", 8050)))
    print("  남은 횟수: %d회" % cfg.get("remain_runs", 0))
    print("  해상도/FPS: 360x640 / %d fps" % cfg.get("fps", 15))
    print("-" * 60)
    videos = get_videos()
    print("  저장된 영상: 총 %d개 (위치: shots\\rec\\)" % len(videos))
    for i, (name, sz, mt, _) in enumerate(videos[:8]):
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt))
        mb = sz / (1024 * 1024)
        print("    [%d] %s  (%.1f MB, %s)" % (i + 1, name, mb, t_str))
    if len(videos) > 8:
        print("    ... 외 %d개" % (len(videos) - 8))
    print("=" * 60)
    print("  명령어: py rec.py on [횟수] | py rec.py off | py rec.py open")


def set_on(runs=5):
    cfg = load_cfg()
    cfg["enabled"] = True
    cfg["remain_runs"] = int(runs)
    save_cfg(cfg)
    print(f"[rec] 고층 녹화 활성화: {cfg['start_wave']}층 ~ {cfg['stop_wave']}층 (앞으로 {runs}회 녹화)")


def set_off():
    cfg = load_cfg()
    cfg["enabled"] = False
    save_cfg(cfg)
    print("[rec] 고층 녹화 비활성화 완료")


def set_waves(start_w, stop_w):
    cfg = load_cfg()
    cfg["start_wave"] = int(start_w)
    cfg["stop_wave"] = int(stop_w)
    save_cfg(cfg)
    print(f"[rec] 녹화 구간 설정: {start_w}층 ~ {stop_w}층")


def open_video(target=None):
    videos = get_videos()
    if not videos:
        print("[rec] 저장된 영상이 없습니다.")
        return
    path = videos[0][3]
    if target is not None:
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(videos):
                path = videos[idx][3]
        else:
            for _, _, _, p in videos:
                if target in os.path.basename(p):
                    path = p
                    break
    print(f"[rec] 영상 재생: {os.path.basename(path)}")
    try:
        os.startfile(path)
    except Exception as e:
        print(f"[rec] 재생 실패: {e!r}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("status", "info"):
        status()
    elif args[0] == "on":
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
        set_on(n)
    elif args[0] == "off":
        set_off()
    elif args[0] == "set" and len(args) >= 3:
        set_waves(args[1], args[2])
    elif args[0] == "list":
        videos = get_videos()
        print(f"총 {len(videos)}개 영상 파일:")
        for i, (name, sz, mt, p) in enumerate(videos):
            t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt))
            print(f"  [{i+1:2d}] {name} ({sz / (1024*1024):5.1f} MB, {t_str})")
    elif args[0] in ("open", "play"):
        tgt = args[1] if len(args) > 1 else None
        open_video(tgt)
    else:
        print("알 수 없는 명령어:", args)
        print("사용법: py rec.py [on [횟수] | off | set 시작 종료 | list | open]")
