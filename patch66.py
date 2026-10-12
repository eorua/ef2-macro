# patch66.py - 병사 상세창이 '초월' 탭 등으로 열려 있어 '해제' 버튼이 없을 때 '상세' 탭으로 돌려서 해제 (C:\macro 에서 py patch66.py)
#   * 초월 탭은 아래 버튼이 '최대 초월'이라 해제를 눌러도 아무 일도 안 일어나 배치 회수가 중단되던 문제
#   * barracks.py : 상세창이 열리면 빨간 '해제' 버튼이 보이는지 확인, 없으면 '상세' 탭(120,415)을 눌러 다시 확인
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "barracks.py")


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(P):
        print("파일 없음:", P); sys.exit(1)
    s = open(P, "r", encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if "def ensure_release_btn" in s:
        print("이미 적용됨"); return
    a1 = "BTN_RELEASE = (408, 1220)           # 상세창의 '해제'\n"
    a2 = "def release_rest(start=KEEP + 1, cap=10):\n"
    a3 = "        tap(BTN_RELEASE, \"해제\")\n"
    for a in (a1, a2, a3):
        if s.count(a) != 1:
            print("앵커 불일치:", a.strip(), s.count(a)); sys.exit(1)
    s = s.replace(a1, a1 + "TAB_DETAIL = (120, 415)                # 상세창의 '상세' 탭 (스킬 345 / 초월 571)\n")
    helper = '''def ensure_release_btn(img):
    """상세창 아래에 빨간 '해제' 버튼이 없으면(예: '초월' 탭) '상세' 탭으로 돌려서 다시 확인. 이미지 반환"""
    for k in range(2):
        if red(img, BTN_RELEASE) > 0.5:
            return img
        log("해제 버튼이 안 보임(다른 탭?) -> '상세' 탭으로 이동")
        tap(TAB_DETAIL, "상세 탭")
        im2 = preset.wait_for(lambda im: red(im, BTN_RELEASE) > 0.5, 2.0, first=0.3, step=0.2)
        if im2 is not None and red(im2, BTN_RELEASE) > 0.5:
            return im2
        img = snap(0.2)
        if img is None:
            return None
    return img


'''
    s = s.replace(a2, helper + a2)
    s = s.replace(a3, "        img = ensure_release_btn(img)\n        if img is None or red(img, BTN_RELEASE) <= 0.5:\n            log(\"해제 버튼을 못 찾음 -> 중단\"); return False\n" + a3)
    print("백업:", backup(P))
    open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("패치 완료")


main()
