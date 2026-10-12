# patch65.py - 오른쪽 HUD 메뉴가 접혔거나 창에 가려졌을 때 자동 복구 (C:\\macro 에서 py patch65.py)
#   * hud.py 신규: 펼침(▶ 519,186)/접힘(◀ 691,186) 토글을 모양으로 인식. 접혀 있으면 눌러서 펼치고, 안 보이면 떠 있는 창을 닫고 재확인
#   * daily.py: hud_ensure() 추가. 퀘스트 보상 확인 전(접힘만 펼침)과 퀘스트 아이콘 누르기 전(창 닫기 포함)에 호출
#   * guild.py: 길드 아이콘 누르기 전에 호출
#   * 시험:  py hud.py   (상태만 출력)   /   py hud.py go   (펼치기까지)
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
HUD_DATA = """
eNqVVt1v01YUf89fceRJqy2MmwTaQkX6MD7KJEQmxvZSVZbVOq2lxI5sp014mApkUynRREVbwpawIrV8rQ8BAsqm8s/sMb7+H3bO9U3shNJpeW
jtc+/vfPzu75xrSZJWK8tauQZngTUPgsMee/MJrv9wBYLXO8GDrhxuNNnWQbjVm+z3esHjFrDdOmt32acmsIO60u9sANvfDpv479lm/20nuIcL
nU/sySPAtWD/gD1vsHYdgt0GBO8/9D8cpQDCX4/ZX6+A3b8b3m/NilDAnh5jcEL+s/cRwl/2+70NkKcyF9XMhWkFgAd61hzC4nyDu20Oe7IxhE
1fzHAYRsPiRI2JH3u50e9tCl/Bywawj61g/xDkYLMeHHZxGSvdYu3GqIcVZ+ghRCJ+2wl3m8HrblRRU9RPhb/ocBqo8od/Emf11mjZwfMWYNzg
8YuUJEkpq1R2XB+8mqeCb5XMgWFpLauCXSlhbMMDuzywl13TM/1U6nZ+fv7GVf1a/sYVyEVlg6Br9PdVRF9DhGftJvE1wOe/u3qT8MT2l/A8/V
YSv/cxdSv/bRx8BnPNTE+rMJPBP9n0BSWJr2bUWkatZtValsOGMdPnBGzq3EwES6VSy2YB9IJVLMpWaUUF17GU2RQ5QjeAfgAdQS2LDnCJL6x6
a/iGhGlLa/5lp+i4BF2oZWZruLWama1mF1W+fjl/I39L/2b+Vvb69z8qEVgFZJ4coJsFTdNUSOPu4Usm+ZJd5BjX9CuuDbK8CnM5ZE2BrwGfL+
Xg/BR/9sh+Pi2e0Z6Zil7WOGAmrSia4fm1sinbZa1i2X5cuuG6zvqwdhXKDi7rRbPgCx5QNULs4dMddq8bbrdk9qQTbD/6Cd+w0dj9B8DuHfc7
d8PmLpyB/rsN1sbdPzdwT/DiSAHW7rGHbS3hO3fbrZhAiqZmCt68YnvbJE8KWEJyxk6E2220I14uaV6lJCuR0SqA7fggn5+ium1e/HRapJ4g75
pR9ExuJOVXPfSFVNiOfcd0HbkUOVtH7nGh6mkloyorOKvo0bLx8QyQHOKFWmJhJJEZSmE9ygMMexkyWXrhx5XNnpZYyVommSZCDhJRYBKyWprv
IvaQFGtl1Rd8IIKcI1wRzKhD+1zSPCIm8gOXIkcKZR8fDpiYktgxJ3YIuXi+4Zt0LrE4JpyyaU/I0dChTCcKTnF5Qo6mKBluOrYpB9tNHFEHOO
02cUB32bM6po8GHK3RBOtG8+wYgsdvlYEWrFGFDto5KdMcZ/BzYiXK64teaJao44I8wQnVIiWJo2IEGabtVVxTXio6nsnxOFJdy/Ry52J2EpcH
v32Cw+PRARfPZw1Y/W3//Qcx6smhxt2I++jsXNQs6CHYbAR/HA0G/WSSVNyVyIhaTIFgb5+uzWBrh6imm6Lf60D4ex2tR+HTXezPAeEcSjqMdV
lwXNBRUeAa9oop8xITTCGluD26J7Qlo+wTJ0q8XOA7LI8zF8NObAH6eaTrWGdJR7SUEwd7oicq+QQAP8RRQNmlFpEW8L5dhPFDGv3awMuZWI3I
lpQxN7xs3yjLiRtSBUl8a4j7GtnGoxvD0vWreUXTLMtp7cLo2pJj+5Y9Wgw/Gj5SaNBEB/U/ipqMpjg12qhcTlTHWK5DWYwwHB1/9P1AG9zPMa
7G/+kGjvNTyp/+j/JP2nyK8IQchPCILhIf5y5WVqwl7GcaEbptlExd53ZdLxmWretCNqfEEqSHzTo20+CjUVKTgeIeGKbCR6zE/n7O3uGX5sOD
sDGQFm6WVhyJGg6/0jTDXVlbyMwuxictspjPjx+HyKT/rtN/f0wpSGJAiBYn12JmKYMEBpH/Bfh0N9U=
"""


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def main():
    daily = os.path.join(HERE, "daily.py")
    guild = os.path.join(HERE, "guild.py")
    hudp = os.path.join(HERE, "hud.py")
    for p in (daily, guild):
        if not os.path.exists(p):
            print("파일 없음:", p); sys.exit(1)
    d = read(daily); g = read(guild)
    crlf_d = "\r\n" in d; crlf_g = "\r\n" in g
    d = d.replace("\r\n", "\n"); g = g.replace("\r\n", "\n")

    # 1) hud.py
    data = zlib.decompress(base64.b64decode("".join(HUD_DATA.split())))
    if os.path.exists(hudp):
        if open(hudp, "rb").read() != data:
            print("hud.py 백업:", backup(hudp))
            open(hudp, "wb").write(data)
    else:
        open(hudp, "wb").write(data)
    print("hud.py 설치")

    # 2) daily.py
    a1 = "def do_quest(go, force=False):\n    img = cap()\n"
    a2 = "    close_panels()\n    tap(QUEST_ICON, 1.3)\n"
    helper = (
        "def hud_ensure(close=True):\n"
        "    \"\"\"오른쪽 메뉴가 접혀 있으면 펼치고, 가려져 있으면 창을 닫음 (실패해도 그냥 진행)\"\"\"\n"
        "    try:\n"
        "        import hud\n"
        "        if not hud.ensure(close):\n"
        "            log(\"오른쪽 메뉴 펼침 확인 실패 (그냥 진행)\")\n"
        "    except Exception as e:\n"
        "        log(\"hud_ensure 오류:\", e)\n\n\n"
    )
    if "def hud_ensure(" in d:
        print("daily.py: 이미 적용됨")
    else:
        if d.count(a1) != 1 or d.count(a2) != 1:
            print("daily.py 앵커 불일치", d.count(a1), d.count(a2)); sys.exit(1)
        d = d.replace(a1, helper + "def do_quest(go, force=False):\n    hud_ensure(False)\n    img = cap()\n")
        d = d.replace(a2, "    close_panels()\n    hud_ensure()\n    tap(QUEST_ICON, 1.3)\n")
        print("daily.py 백업:", backup(daily))
        write(daily, d.replace("\n", "\r\n") if crlf_d else d)
        print("daily.py 수정 완료")

    # 3) guild.py
    b1 = "    daily.close_panels()\n    tap(GUILD_ICON, 1.4)\n"
    if "daily.hud_ensure()" in g:
        print("guild.py: 이미 적용됨")
    else:
        if g.count(b1) != 1:
            print("guild.py 앵커 불일치", g.count(b1)); sys.exit(1)
        g = g.replace(b1, "    daily.close_panels()\n    daily.hud_ensure()\n    tap(GUILD_ICON, 1.4)\n")
        print("guild.py 백업:", backup(guild))
        write(guild, g.replace("\n", "\r\n") if crlf_g else g)
        print("guild.py 수정 완료")
    print("패치 완료")


main()
