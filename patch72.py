# patch72.py - 던전/일일 랭킹전이 실패해도 '오늘 완료'로 기록되던 문제 수정 (C:\macro 에서 py patch72.py, 메인 매크로를 끈 상태에서)
#   * 원인: run_daily 가 do_dungeon/do_ranking 결과와 상관없이 완료로 기록 -> 오늘 아침 점검/팝업 직후 한 번 실패하면 하루 종일 안 함
#   * 수정: 성공했을 때만 완료 기록, 실패하면 10분 뒤 재시도 (최대 3번째 시도까지만, 그 뒤엔 완료 처리)
#   * 오늘 이미 잘못 기록된 던전/일일 랭킹전 완료 표시는 이번에 한 번 지움 (state.json)
import os, sys, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY = os.path.join(HERE, "daily.py")
STATE = os.path.join(HERE, "state.json")

OLD = '''        if not d.get("dungeon"):
            log("던전 소탕 시작")
            do_dungeon(True)
            d["dungeon"] = True
            return True
        if not d.get("ranking"):
            log("일일 랭킹전 시작")
            do_ranking(True)
            d["ranking"] = True
            return True
'''
NEW = '''        if not d.get("dungeon") and time.time() >= d.get("dungeon_next", 0):
            log("던전 소탕 시작")
            d["dungeon_tries"] = d.get("dungeon_tries", 0) + 1
            if do_dungeon(True) or d["dungeon_tries"] >= 3:
                d["dungeon"] = True
            else:
                log("던전 소탕 실패 -> 10분 뒤 재시도 (%d/3)" % d["dungeon_tries"])
                d["dungeon_next"] = time.time() + 600
            return True
        if not d.get("ranking") and time.time() >= d.get("ranking_next", 0):
            log("일일 랭킹전 시작")
            d["ranking_tries"] = d.get("ranking_tries", 0) + 1
            if do_ranking(True) or d["ranking_tries"] >= 3:
                d["ranking"] = True
            else:
                log("일일 랭킹전 참여 못 함 -> 10분 뒤 재시도 (%d/3)" % d["ranking_tries"])
                d["ranking_next"] = time.time() + 600
            return True
'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    s = open(DAILY, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    done = "dungeon_tries" in s
    if not done and s.count(OLD) != 1:
        print("daily.py 앵커 불일치", s.count(OLD), "-> daily.py 를 올려 주세요"); return 1
    if not done:
        print("daily.py 백업:", backup(DAILY))
        s = s.replace(OLD, NEW, 1)
        open(DAILY, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
        print("daily.py 패치 완료")
    else:
        print("daily.py 는 이미 최신")
    if os.path.exists(STATE):
        st = json.load(open(STATE, encoding="utf-8"))
        d = st.get("daily", {})
        if not d.get("fix72"):
            print("state 백업:", backup(STATE))
            for k in ("dungeon", "ranking", "dungeon_tries", "ranking_tries", "dungeon_next", "ranking_next"):
                d.pop(k, None)
            d["fix72"] = True
            st["daily"] = d
            st["daily_next"] = 0
            json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print("오늘 던전/일일 랭킹전 완료 표시를 지웠습니다 -> 메인을 켜면 다시 시도")
        else:
            print("state 는 이미 정리됨")
    else:
        print("state.json 이 없어 건너뜀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
