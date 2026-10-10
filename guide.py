import subprocess, os, sys, cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", "127.0.0.1:5585"]

STEPS = [
    ("hud",          "전투 화면. 팝업이 하나도 없는 상태 (우하단 금색 순환 화살표 '프리셋' 아이콘이 보이게)"),
    ("hero",         "영웅 탭을 연 상태 (팝업 없음)"),
    ("hire_cool",    "영웅 탭의 '영입'을 눌러 고용 화면을 연 상태 (쿨타임 타이머가 보이는 상태)"),
    ("hire_confirm", "고용 화면에서 '새로고침'을 눌러 💎100 확인창이 뜬 상태.\n   주의: 캡처 후 반드시 '취소'를 누르세요. '확인'은 절대 누르지 마세요 (보석 100개 소모)"),
    ("preset",       "고용 화면은 X로 닫고, 우하단 금색 순환 화살표 '프리셋' 아이콘을 눌러 '통합 프리셋' 팝업을 연 상태 (저장하지 마세요)"),
    ("bulk_ok",      "프리셋 팝업은 '취소'로 닫고, 영웅 탭의 '+' 버튼으로 '일괄 레벨업' 팝업을 연 상태 (영웅이 모두 선택된 정상 상태)"),
    ("bulk_gray",    "(선택) 일괄 레벨업에서 +1000을 눌러 버튼이 회색(클릭 불가)이 된 상태"),
]
EXTRA = {
    "hero_dot": "(쿨타임이 끝났을 때) 영웅 탭에서 '영입' 버튼 위에 빨간 점이 보이는 상태",
    "hire_free": "(쿨타임이 끝났을 때) '영입'을 눌러 연 고용 화면. 새로고침은 누르지 마세요",
}


def capture():
    png = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout
    if not png:
        return None
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def main():
    names = sys.argv[1:]
    table = dict(STEPS); table.update(EXTRA)
    steps = [(n, table[n]) for n in names if n in table] if names else STEPS
    os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
    print("화면 캡처 안내 (건너뛰기: s + Enter / 종료: q + Enter)\n")
    for i, (name, desc) in enumerate(steps, 1):
        print(f"[{i}/{len(steps)}] {name}\n   {desc}")
        ans = input("   준비되면 Enter > ").strip().lower()
        if ans == "q":
            break
        if ans == "s":
            print("   건너뜀\n")
            continue
        img = capture()
        if img is None:
            print("   캡처 실패: adb connect 127.0.0.1:5585 를 다시 실행해 보세요\n")
            continue
        path = os.path.join(BASE, "shots", f"{name}.png")
        cv2.imwrite(path, img)
        print(f"   저장 완료: {path} {img.shape}\n")
    print("끝. C:\\macro\\shots 폴더의 이미지를 보내주세요.")


if __name__ == "__main__":
    main()