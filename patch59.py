# patch59.py - 길드 일일 작업 추가 (C:\macro 에서 py patch59.py)
#   * 길드 출석 + 우체국 선물 5회 (패널 옵션 guild_post, 기본 켜짐)
#   * 길드레이드 상점 뽑기: 맨 윗줄(티켓) 전부 + 광고 3회 (패널 옵션 raid_shop, 기본 켜짐)
#   * 하루(게임일 기준) 한 번씩, 일일 작업 순서에서 퀘스트 보상 다음에 실행. 실패하면 10분 뒤 재시도(최대 4회)
#   * 시험:  py guild.py look   /   py guild.py post go   /   py guild.py raid go
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY = os.path.join(HERE, "daily.py")
PANEL = os.path.join(HERE, "panel.py")
GUILD = os.path.join(HERE, "guild.py")
TPLDIR = os.path.join(HERE, "tpl")
GUILD_DATA = """
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
"""
TPLS = {
    "g_post_title.png": """
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
""",
    "g_shop_title.png": """
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
HXUi/w+JJgQb
""",
}

D_HELPER_ANCHOR = "def due(st):\n"
D_HELPER = (
    'GUILD_TASKS = (("g_post", "guild_post"), ("g_raid", "raid_shop"))   # (오늘 완료 표시 키, 패널 옵션 키)\n'
    '\n\n'
    'def guild_pending(d):\n'
    '    """오늘 아직 안 한 길드 작업 (옵션이 켜져 있고 재시도 대기 시간이 지난 것)"""\n'
    '    if time.time() < d.get("guild_next", 0):\n'
    '        return None\n'
    '    for key, opt in GUILD_TASKS:\n'
    '        if not d.get(key) and setting(opt, True):\n'
    '            return key\n'
    '    return None\n'
    '\n\n')
D_DUE_OLD = "    return time.time() >= inf_due(st)\n"
D_DUE_NEW = "    if guild_pending(d):\n        return True\n" + D_DUE_OLD
D_RUN_OLD = '        if time.time() >= inf_due(st):\n            log("무한랭킹전 시작")\n'
D_RUN_NEW = (
    '        gk = guild_pending(d)\n'
    '        if gk:\n'
    '            log("길드 작업 시작:", gk)\n'
    '            import guild\n'
    '            d["tries_" + gk] = d.get("tries_" + gk, 0) + 1\n'
    '            if guild.run_task(gk) or d["tries_" + gk] >= 4:\n'
    '                d[gk] = True\n'
    '            else:\n'
    '                d["guild_next"] = time.time() + 600\n'
    '            return True\n') + D_RUN_OLD

P_DEF_OLD = 'DEFAULTS = {"fairy": False, "log_font": 10}'
P_DEF_NEW = 'DEFAULTS = {"fairy": False, "log_font": 10, "guild_post": True, "raid_shop": True}'
P_OPT_OLD = '"),):\n            v = tk.BooleanVar(value=bool(self.set.get(key, False)))\n'
P_OPT_NEW = ('"),\n'
             '                ("guild_post", "길드 출석 + 우체국 선물 5회", "하루 한 번, 일일 작업 때 자동으로 합니다. 기본은 켜짐."),\n'
             '                ("raid_shop", "길드레이드 상점 뽑기 (티켓 + 광고)", "티켓은 있는 만큼, 광고는 3회까지 뽑습니다. 광고 제거 패키지가 있어야 합니다. 기본은 켜짐."),):\n'
             '            v = tk.BooleanVar(value=bool(self.set.get(key, False)))\n')


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def unpack(s):
    return zlib.decompress(base64.b64decode("".join(s.split())))


def main():
    for p in (DAILY, PANEL):
        if not os.path.exists(p):
            print(os.path.basename(p), "가 없습니다. C:\\macro 에서 실행하세요."); return 1
    if not os.path.exists(os.path.join(HERE, "closer.py")):
        print("closer.py 가 없습니다. patch50~53 을 먼저 적용하세요."); return 1
    ds = open(DAILY, encoding="utf-8").read()
    ps = open(PANEL, encoding="utf-8").read()
    done_d = "def guild_pending(" in ds
    done_p = '"guild_post"' in ps
    if not done_d:
        c = (ds.count(D_HELPER_ANCHOR), ds.count(D_DUE_OLD), ds.count(D_RUN_OLD))
        if c != (1, 1, 1):
            print("daily.py 앵커 불일치 %s (기대 (1, 1, 1)) -> daily.py 를 올려 주세요" % (c,)); return 1
    if not done_p:
        c = (ps.count(P_DEF_OLD), ps.count(P_OPT_OLD))
        if c != (1, 1):
            print("panel.py 앵커 불일치 %s (기대 (1, 1)) -> panel.py 를 올려 주세요" % (c,)); return 1
    os.makedirs(TPLDIR, exist_ok=True)
    for name, data in TPLS.items():
        raw = unpack(data)
        path = os.path.join(TPLDIR, name)
        if not os.path.exists(path) or open(path, "rb").read() != raw:
            open(path, "wb").write(raw)
            print("tpl\\%s 저장" % name)
    gd = unpack(GUILD_DATA)
    if not os.path.exists(GUILD) or open(GUILD, "rb").read() != gd:
        if os.path.exists(GUILD):
            print("백업:", backup(GUILD))
        open(GUILD, "wb").write(gd)
        print("guild.py 갱신")
    else:
        print("guild.py 는 이미 최신")
    if not done_d:
        ns = (ds.replace(D_HELPER_ANCHOR, D_HELPER + D_HELPER_ANCHOR, 1)
                .replace(D_DUE_OLD, D_DUE_NEW, 1)
                .replace(D_RUN_OLD, D_RUN_NEW, 1))
        print("daily.py 백업:", backup(DAILY))
        open(DAILY, "w", encoding="utf-8").write(ns)
        print("daily.py 패치 완료")
    else:
        print("daily.py 는 이미 최신")
    if not done_p:
        ns = ps.replace(P_DEF_OLD, P_DEF_NEW, 1).replace(P_OPT_OLD, P_OPT_NEW, 1)
        print("panel.py 백업:", backup(PANEL))
        open(PANEL, "w", encoding="utf-8").write(ns)
        print("panel.py 패치 완료 (패널이 자동으로 다시 뜹니다)")
    else:
        print("panel.py 는 이미 최신")
    print("먼저 길드 창을 연 상태에서 py guild.py look 으로 화면 판별을 확인하고, py guild.py post go / raid go 로 한 번씩 시험해 보세요.")
    print("메인 매크로는 껐다 켜야 새 일일 작업이 반영됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
