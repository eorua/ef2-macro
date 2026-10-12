# patch79.py - 6200 사이클 직후 '영웅 배치' 자동 정리 (C:\macro 에서 py patch79.py)
#   * 성을 눌러 '영웅 배치' 창을 열고, 불의정령 3마리는 10시/2시/6시에 한 마리씩, 나머지는 전부 12시에 겹쳐 놓고 저장
#   * 아이콘은 얼굴 그림(tpl\arr_spirit/druid/drum.png)으로 찾음. 실패/불확실하면 '취소'를 눌러 원래 배치 유지
#   * main.py: 병영 편성 사이클의 마지막 프리셋(기본) 성공 직후 1번 실행 (설정 arrange, 기본 켜짐)
#   * 시험:  py arrange.py look (판별만) / py arrange.py open go (창만 열기) / py arrange.py go (전체 실행)
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
TPLD = os.path.join(HERE, "tpl")
ARR = os.path.join(HERE, "arrange.py")
ARR_DATA = """
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
r2gcHzVO6AqalkuJ/wF0gVp0
"""
TPLS = {
    "arr_spirit.png": """
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
""",
    "arr_druid.png": """
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
gg==
""",
    "arr_drum.png": """
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
""",
}

M_OLD1 = "def run_cycle_barracks():\n"
M_NEW1 = '''def _arrange_after():
    """6200 사이클 직후 영웅 배치 정리 (불의정령 10/2/6시, 나머지 12시). 실패해도 사이클 결과에는 영향 없음"""
    try:
        if not daily.setting("arrange", True):
            return
        import arrange
        arrange.GO = True
        arrange.GUARD = _guard
        arrange.log = lambda *a: log("  [배치] " + " ".join(str(x) for x in a))
        log("영웅 배치 정리 시작")
        ok = arrange.run()
        log("영웅 배치 정리: " + ("성공" if ok else "실패 (원래 배치 유지)"))
        if not ok:
            import closer
            closer.close_all()
    except Abort:
        raise
    except Exception as e:
        log("영웅 배치 정리 오류: %r" % (e,))


def run_cycle_barracks():
'''
M_OLD2 = '    for _ in range(3):\n        if preset.set_presets(None, "기본"):\n            return True\n'
M_NEW2 = '    for _ in range(3):\n        if preset.set_presets(None, "기본"):\n            _arrange_after()\n            return True\n'


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def put(path, raw, label):
    if not os.path.exists(path) or open(path, "rb").read() != raw:
        if os.path.exists(path):
            print("백업:", backup(path))
        open(path, "wb").write(raw)
        print(label, "갱신")
    else:
        print(label, "는 이미 최신")


def main():
    if not os.path.exists(MAIN):
        print("main.py 가 없습니다 (C:\\macro 에서 실행)"); return 1
    s = open(MAIN, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    done = "def _arrange_after(" in s
    if not done and (s.count(M_OLD1) != 1 or s.count(M_OLD2) != 1):
        print("main.py 앵커 불일치", s.count(M_OLD1), s.count(M_OLD2), "-> main.py 를 올려 주세요"); return 1
    os.makedirs(TPLD, exist_ok=True)
    put(ARR, zlib.decompress(base64.b64decode("".join(ARR_DATA.split()))), "arrange.py")
    for name, data in TPLS.items():
        put(os.path.join(TPLD, name), base64.b64decode("".join(data.split())), "tpl\\" + name)
    if not done:
        print("main.py 백업:", backup(MAIN))
        s = s.replace(M_OLD1, M_NEW1, 1).replace(M_OLD2, M_NEW2, 1)
        open(MAIN, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
        print("main.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    else:
        print("main.py 는 이미 최신")
    print("영웅 배치 창을 열어 둔 채 py arrange.py look 으로 판별을 확인해 보세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
