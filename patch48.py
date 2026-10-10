# patch48.py - 병영 편성 방식 연결 (C:\macro 에서 py patch48.py)
#   * 패널 [옵션] 탭에 "병영 편성으로 최대레벨 단계 진행" 체크박스 추가 (기본 꺼짐, settings.json 의 barracks_swap)
#   * 켜면 6200 웨이브 고레벨 단계에서: 골렘 편성 -> 유물 영웅강화골드 + 일괄 레벨업 -> 드루이드/전장의북/불의정령 편성 -> 유물 기본
#   * 꺼져 있으면 지금까지와 똑같이 동작합니다. 중간에 실패하면 영웅 기본 프리셋으로 복구합니다.
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
PANEL = os.path.join(HERE, "panel.py")
BK = os.path.join(HERE, "barracks.py")
DATA = """
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
zAyjVPj1GhglbvZQw/4P2Y7wrw==
"""

NEW_FUNCS = '''def _barracks_fallback(why):
    """병영 편성이 중간에 실패하면 영웅 기본 프리셋으로 되돌림 (편성이 어중간하게 남지 않게)"""
    log("병영 편성 실패: %s -> 영웅 기본 프리셋으로 복구" % why)
    try:
        preset.set_presets("기본", "기본")
    except Abort:
        raise
    except Exception as e:
        log("복구 중 오류: %r" % (e,))
    return False


def run_cycle_barracks():
    """병영 편성 방식 고레벨 단계 (패널 옵션 barracks_swap)"""
    import barracks
    if not barracks.phase1():
        return _barracks_fallback("골렘 편성(1단계)")
    if not preset.set_presets(None, "영웅강화골드"):
        return _barracks_fallback("유물 프리셋 변경")
    if not preset.bulk_levelup():
        return _barracks_fallback("일괄 레벨업")
    if not barracks.phase2():
        return _barracks_fallback("최종 편성(2단계)")
    for _ in range(3):
        if preset.set_presets(None, "기본"):
            return True
        time.sleep(2)
    log("최종 유물 프리셋(기본) 설정 실패 -> 다음 기회에 재시도")
    return False


def run_cycle_high():
    if opt_on("barracks_swap"):
        return run_cycle_barracks()
'''

RESTART_NEW = ('    hero, relic = (None, "기본") if (st.get("high_done") and opt_on("barracks_swap")) else \\\n'
               '        (("렙뻥", "기본") if st.get("high_done") else ("기본", "시간"))\n')


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    for p in (MAIN, PANEL):
        if not os.path.exists(p):
            print(os.path.basename(p), "가 없습니다. C:\\macro 에서 실행하세요."); return 1
    s = open(os.path.join(HERE, "preset.py"), encoding="utf-8").read()
    if "hero is None or cur_h == hero" not in s:
        print("먼저 patch46.py 를 적용하세요 (영웅 프리셋을 건드리지 않는 옵션)"); return 1
    for t in ("bk_druid1.png", "bk_spirit1.png"):
        if not os.path.exists(os.path.join(HERE, "tpl", t)):
            print("tpl\\%s 가 없습니다. py barracks.py mk ... 로 만든 뒤 다시 실행하세요." % t); return 1
    ms = open(MAIN, encoding="utf-8").read()
    ps = open(PANEL, encoding="utf-8").read()
    a1 = "def run_cycle_high():\n"
    a2 = '    hero, relic = ("렙뻥", "기본") if st.get("high_done") else ("기본", "시간")\n'
    b1 = '("fall_continue", "성 함락 시 이어하기 우선", "켜면 하트를 써서 이어하기, 하트가 없으면 환생. 끄면 바로 환생."),):'
    done_main = "def run_cycle_barracks(" in ms
    done_panel = '"barracks_swap"' in ps
    if not done_main and (ms.count(a1) != 1 or ms.count(a2) != 1 or "def opt_on(" not in ms):
        print("main.py 앵커 불일치 (run_cycle_high %d, 재시작 프리셋 %d) -> main.py 를 올려 주세요" % (ms.count(a1), ms.count(a2))); return 1
    if not done_panel and ps.count(b1) != 1:
        print("panel.py 앵커 불일치 (이어하기 옵션이 없나요? patch40 먼저) -> panel.py 를 올려 주세요"); return 1
    data = zlib.decompress(base64.b64decode("".join(DATA.split())))
    if not os.path.exists(BK) or open(BK, "rb").read() != data:
        if os.path.exists(BK):
            print("백업:", backup(BK))
        open(BK, "wb").write(data)
        print("barracks.py 갱신")
    else:
        print("barracks.py 는 이미 최신")
    if not done_main:
        ns = ms.replace(a1, NEW_FUNCS, 1).replace(a2, RESTART_NEW, 1)
        print("main.py 백업:", backup(MAIN))
        open(MAIN, "w", encoding="utf-8").write(ns)
        print("main.py 패치 완료")
    else:
        print("main.py 는 이미 최신")
    if not done_panel:
        b2 = b1[:-2] + ('\n                ("barracks_swap", "병영 편성으로 최대레벨 단계 진행", '
                        '"6200 웨이브에서 병영을 재편성해 일괄 레벨업합니다. 켜면 기존 렙뻥 프리셋 방식 대신 사용. 기본은 꺼짐."),):')
        print("panel.py 백업:", backup(PANEL))
        open(PANEL, "w", encoding="utf-8").write(ps.replace(b1, b2, 1))
        print("panel.py 패치 완료 (패널이 자동으로 다시 뜹니다)")
    else:
        print("panel.py 는 이미 최신")
    print("패널 [옵션] 탭에서 체크하면 켜집니다. 메인 매크로는 껐다 켜야 새 코드가 적용됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
