# patch40.py (v2) - 성 함락 시 "이어하기" 켜고 끄기 (C:\macro 에서 py patch40.py)
#   ON  : 성이 함락되면 이어하기(하트 소모)를 먼저 누르고, 하트가 없거나 안 되면 환생
#   OFF : 지금처럼 바로 환생 (기본값)
# 패널의 [옵션] 탭 체크박스로 켜고 끕니다 (settings.json 의 fall_continue). 메인 재시작 불필요.
import os, sys, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
PANEL = os.path.join(HERE, "panel.py")

HELPERS = '''def opt_on(name):
    """settings.json (조작 패널의 옵션 탭에서 켜고 끔) 에서 옵션을 읽음. 없으면 꺼짐"""
    try:
        with open(os.path.join(BASE, "settings.json"), encoding="utf-8") as f:
            return bool(json.load(f).get(name, False))
    except Exception:
        return False


_cont_hist = []          # 이어하기를 누른 시각들


def continue_btn(img):
    """성 함락 팝업 오른쪽의 초록 '이어하기' 버튼. 색으로 판별하며 회색(하트 없음)이면 False"""
    H, W = img.shape[:2]
    x1, y1, x2, y2 = int(0.71 * W), int(0.52 * H), int(0.89 * W), int(0.56 * H)
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    frac = float(((h > 35) & (h < 90) & (s > 100) & (v > 100)).mean())
    return frac >= 0.5, (int(0.80 * W), int(0.54 * H)), frac


def fall_popup(img):
'''

BRANCH = '''            if ok and opt_on("fall_continue"):
                now = time.time()
                recent = [t for t in _cont_hist if now - t < 90]
                if recent and now - recent[-1] < 8:
                    time.sleep(2)               # 방금 눌렀음: 화면이 바뀔 때까지 대기 (하트 중복 소모 방지)
                    continue
                cok, (cx, cy), cfrac = continue_btn(img)
                if cok and len(recent) < 3:
                    log("성 함락 감지 → 이어하기 클릭 (버튼 %.2f, 90초 내 %d회째)" % (cfrac, len(recent) + 1))
                    if GO:
                        rebirth.tap(cx, cy)
                        _cont_hist.append(now)
                        time.sleep(3)
                    else:
                        time.sleep(5)
                    continue
                log("이어하기 불가 (버튼 %.2f, 90초 내 %d회) → 환생" % (cfrac, len(recent)))
            if ok:
                log("성 함락 감지 → 환생 클릭")
'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(MAIN):
        print("main.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    src = open(MAIN, encoding="utf-8").read()
    a1 = "def fall_popup(img):\n"
    a2 = '            if ok:\n                log("성 함락 감지 → 환생 클릭")\n'
    newsrc = None
    if "def continue_btn(" in src:
        # 예전 버전(파일 방식)이 이미 적용된 경우: opt_on 만 settings.json 방식으로 교체
        m = re.search(r"def opt_on\(name\):.*?\n\n\n(?=_cont_hist)", src, flags=re.S)
        if m and "settings.json" not in m.group(0):
            newsrc = src[:m.start()] + HELPERS.split("_cont_hist")[0].replace("def fall_popup(img):\n", "") + src[m.end():]
        else:
            print("main.py 는 이미 최신")
    else:
        if src.count(a1) != 1 or src.count(a2) != 1:
            print("앵커 불일치 (fall_popup %d, 환생 클릭 %d) -> main.py 를 올려 주세요" % (src.count(a1), src.count(a2)))
            return 1
        newsrc = src.replace(a1, HELPERS, 1).replace(a2, BRANCH, 1)
    if newsrc is not None:
        print("main.py 백업:", backup(MAIN))
        open(MAIN, "w", encoding="utf-8").write(newsrc)
        print("main.py 패치 완료")
    # 패널 옵션 탭에 체크박스 추가
    if os.path.exists(PANEL):
        p = open(PANEL, encoding="utf-8").read()
        if '"fall_continue"' in p:
            print("panel.py 는 이미 최신")
        else:
            b1 = '("fairy", "정령의 고원: 티켓 구매 + 소탕", "다이아를 사용합니다. 기본은 꺼짐."),):'
            if p.count(b1) != 1:
                print("panel.py 앵커 불일치 -> panel.py 를 올려 주세요")
                return 1
            b2 = ('("fairy", "정령의 고원: 티켓 구매 + 소탕", "다이아를 사용합니다. 기본은 꺼짐."),\n'
                  '                ("fall_continue", "성 함락 시 이어하기 우선", "켜면 하트를 써서 이어하기, 하트가 없으면 환생. 끄면 바로 환생."),):')
            print("panel.py 백업:", backup(PANEL))
            open(PANEL, "w", encoding="utf-8").write(p.replace(b1, b2, 1))
            print("panel.py 패치 완료 (패널이 자동으로 다시 뜹니다)")
    else:
        print("panel.py 가 없어 체크박스는 건너뜀")
    print("기본은 OFF(바로 환생). 패널 [옵션] 탭의 '성 함락 시 이어하기 우선'을 체크하면 켜집니다 (메인 재시작 불필요).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
