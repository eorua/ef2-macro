"""maint.py - '서버 점검 중입니다' 팝업 인식 (글자 읽기 + 끝나는 시각 해석)

  py maint.py look       지금 화면에 점검 팝업이 있는지 판별 (누르지 않음)
  py maint.py ocrtest    윈도우 글자 인식(OCR)이 되는지 시험 (지금 화면의 글자를 출력)
읽는 순서: 화면 구조 확인(가운데 초록 '확인' 버튼 하나) -> 윈도우 OCR 로 글자 읽기('점검' / 'KST' 포함 여부)
          -> OCR 이 안 되면 템플릿 이미지로 대체 판별. 끝나는 시각(예: 09:40 ~ 10:40)은 OCR 로만 읽음 (못 읽으면 None)
"""
import os, re, sys, time, subprocess, tempfile
import cv2, numpy as np

BASE = r"C:\macro"
TPLDIR = os.path.join(BASE, "tpl")
SHOTS = os.path.join(BASE, "shots")
ROI_DLG = (120, 420, 600, 950)           # 팝업 대화창이 있을 영역 (x1, y1, x2, y2)
OCR_COOLDOWN = 20                        # 후보 화면이 계속 떠 있어도 이 초마다 한 번만 OCR
_last = {"t": 0.0, "hit": False}

PS_SCRIPT = r'''
param($path)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) {
    $t = $asTask.MakeGenericMethod($type)
    $task = $t.Invoke($null, @($op))
    $null = $task.Wait(-1)
    $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) { Write-Output 'NOENGINE'; exit }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
Write-Output 'OK'
foreach ($l in $res.Lines) { Write-Output $l.Text }
'''


def log(*a):
    print(time.strftime("[%H:%M:%S] maint:"), *a, flush=True)


def ocr_lines(img):
    """윈도우 내장 OCR 로 글자 읽기 -> 줄 목록. 사용할 수 없으면 None"""
    try:
        d = tempfile.gettempdir()
        png = os.path.join(d, "ef2_ocr.png")
        ps1 = os.path.join(d, "ef2_ocr.ps1")
        cv2.imwrite(png, img)
        with open(ps1, "w", encoding="utf-8-sig") as f:
            f.write(PS_SCRIPT)
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, png],
                           capture_output=True, timeout=60)
        out = r.stdout.decode("utf-8", errors="replace").splitlines()
        out = [x.strip() for x in out if x.strip()]
        if not out or out[0] != "OK":
            return None
        return out[1:]
    except Exception as e:
        log("OCR 오류:", repr(e))
        return None


def candidate(img):
    """구조 확인: 가운데에 초록 버튼 하나만 있는 대화창(점검/공지 같은 안내 팝업)이 떠 있는지"""
    x1, y1, x2, y2 = ROI_DLG
    sub = img[y1:y2, x1:x2]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    green = ((h >= 35) & (h <= 85) & (s >= 120) & (v >= 70)).astype(np.uint8)
    red = (((h <= 8) | (h >= 172)) & (s >= 150) & (v >= 90)).astype(np.uint8)

    def blobs(m):
        n, _, st, cen = cv2.connectedComponentsWithStats(m, 8)
        out = []
        for i in range(1, n):
            x, y, w, hh, a = st[i]
            if 90 <= w <= 280 and 36 <= hh <= 100 and a >= 0.8 * w * hh:
                out.append((x + x1, y + y1, w, hh))
        return out
    g = [b for b in blobs(green) if 270 <= b[0] + b[2] // 2 <= 450]
    if len(g) != 1:
        return False
    gx, gy, gw, gh = g[0]
    _last["btn"] = (gx + gw // 2, gy + gh // 2)          # patch207: 확인 버튼 위치
    for rx, ry, rw, rh in blobs(red):
        if abs((ry + rh // 2) - (gy + gh // 2)) < 60:
            return False                      # 같은 줄에 빨간 버튼(취소 등)이 있으면 안내 팝업이 아님
    return True


def template_score(img):
    t = cv2.imread(os.path.join(TPLDIR, "maint_title.png"))
    if t is None:
        return 0.0
    x1, y1, x2, y2 = ROI_DLG
    sub = img[y1:y2, x1:x2]
    best = 0.0
    for sc in (0.92, 1.0, 1.08):
        tt = cv2.resize(t, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_CUBIC)
        if sub.shape[0] < tt.shape[0] or sub.shape[1] < tt.shape[1]:
            continue
        res = cv2.matchTemplate(sub, tt, cv2.TM_CCOEFF_NORMED)
        best = max(best, float(res.max()))
    return best


def parse_end(text, now=None):
    """'2026-10-12 09:40 ~ 10:40 (KST)' 같은 글에서 끝나는 시각(epoch 초)을 구함. 못 구하면 None"""
    now = now or time.time()
    t = text.replace("：", ":").replace("∼", "~").replace("～", "~").replace("〜", "~")
    # patch215: OCR 이 시각 숫자를 글자로 읽는 경우 (0->O/o/D, 1->l/I/|, 5->S, 8->B) - 숫자나 ':' 옆에 붙은 것만 바꿈
    for a, b in (("O", "0"), ("o", "0"), ("D", "0"), ("l", "1"), ("I", "1"), ("|", "1"), ("S", "5"), ("B", "8")):
        t = re.sub(r"(?<=[\d:])%s|%s(?=[\d:])" % (re.escape(a), re.escape(a)), b, t)
    # patch207: 'HH:MM ~ (날짜) HH:MM' 처럼 물결로 이어진 시간 범위만 인정
    #   (10-21 20:27 '게임 데이터 업데이트' 팝업 뒤 화면의 '3:48:49' 같은 숫자를 점검 시각으로 읽어 BlueStacks 를 3시간 30분 꺼 둔 사고)
    # patch214: OCR 이 물결(~)을 빼먹거나 다른 글자로 읽는 경우(10-23 '16:30 ~ 18:30' 을 못 읽음)까지 -> 두 시각 사이에 숫자가 아닌 글자 0~6개
    #   ':' 를 '.' / ';' 로 읽는 경우도 인정. (점검 글자가 있어야만 이 함수를 쓰므로 '3:48:49' 같은 오독 위험은 없음)
    # patch216: 시작 시각의 ':' 를 빼먹는 경우도 (10-23 OCR: '1630 ~ 19:30')
    m = re.search(r"(?<!\d)(\d{1,2})\s*[:.;]?\s*(\d{2})(?!\d)[^\d]{0,6}?(?:20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}\s*)?(\d{1,2})\s*[:.;]\s*(\d{2})(?!\d)", t)
    if not m:
        return None
    times = [(m.group(1), m.group(2)), (m.group(3), m.group(4))]
    dates = re.findall(r"(20\d{2})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})", t)
    sh, sm = int(times[0][0]), int(times[0][1])
    eh, em = int(times[-1][0]), int(times[-1][1])
    if not (0 <= eh <= 24 and 0 <= em <= 59 and 0 <= sh <= 24 and 0 <= sm <= 59):
        return None
    lt = time.localtime(now)
    try:
        if dates:
            y, mo, d = (int(x) for x in dates[-1])
        else:
            y, mo, d = lt.tm_year, lt.tm_mon, lt.tm_mday
        end = time.mktime((y, mo, d, eh % 24, em, 0, 0, 0, -1)) + (86400 if eh == 24 else 0)
        if len(dates) < 2 and (eh, em) < (sh, sm):
            end += 86400                      # 자정을 넘기는 점검
    except Exception:
        return None
    if not (now - 6 * 3600 <= end <= now + 72 * 3600):
        return None
    return end


def _is_maint_text(text):
    """점검 팝업 글자인지. 메일함/보상 같은 화면 속 '점검 보상' 글자는 제외"""
    t = text.replace(" ", "")
    for bad in ("모두받기", "메일함", "점검보상", "보상"):
        if bad in t:
            return False
    return ("서버점검" in t) or ("점검중" in t) or ("점검안내" in t) or ("점검" in t and "KST" in t.upper())


def save_shot(img, tag):
    try:
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, "maint_%s_%d.png" % (tag, int(time.time()))), img)
    except Exception:
        pass


def detect(img):
    """점검 팝업이면 {'end': 끝나는 시각 epoch 또는 None, 'text': 읽은 글자}, 아니면 None"""
    if img is None or not candidate(img):
        return None
    now = time.time()
    if now - _last["t"] < OCR_COOLDOWN and not _last["hit"]:
        return None
    _last["t"] = now
    x1, y1, x2, y2 = ROI_DLG
    crop = cv2.resize(img[y1:y2, x1:x2], None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    lines = ocr_lines(crop)
    if lines is not None:
        text = " ".join(lines)
        hit = _is_maint_text(text)
        info = {"end": parse_end(text, now) if hit else None, "text": text} if hit else None
        if hit:
            log("점검 팝업 인식 (OCR): %s" % text[:160])
            try:                                          # patch215: 읽은 글자 원문을 파일로 (끝나는 시각을 못 읽을 때 원인 확인용)
                with open(os.path.join(SHOTS, "maint_text.txt"), "a", encoding="utf-8") as f:
                    f.write(time.strftime("%m-%d %H:%M:%S ") + repr(text) + "\n")
            except Exception:
                pass
            log("끝나는 시각: %s" % (time.strftime("%m-%d %H:%M", time.localtime(info["end"])) if info["end"] else "못 읽음"))
        elif "업데이트" in text.replace(" ", ""):        # patch207: '게임 데이터가 업데이트 되었습니다' -> 확인만 누르면 됨 (점검 아님)
            log("게임 데이터 업데이트 팝업 (점검 아님): %s" % text[:60])
            save_shot(img, "update")
            _last["hit"] = False
            return {"update": True, "btn": _last.get("btn"), "text": text}
    else:
        sc = template_score(img)
        hit = sc >= 0.75
        info = {"end": None, "text": "(OCR 불가, 이미지 판별 %.2f)" % sc} if hit else None
        if hit:
            log("점검 팝업 인식 (이미지 %.2f, OCR 불가 -> 끝나는 시각은 모름)" % sc)
        elif sc >= 0.5:
            save_shot(img, "near")
    _last["hit"] = bool(info)
    if info:
        save_shot(img, "hit")
    return info


if __name__ == "__main__":
    sys.path.insert(0, BASE)
    import preset
    img = preset.capture()
    if img is None:
        print("캡처 실패"); sys.exit(1)
    if "ocrtest" in sys.argv[1:]:
        lines = ocr_lines(img)
        if lines is None:
            print("OCR 사용 불가 (윈도우 한국어/영어 OCR 언어가 없을 수 있음)")
        else:
            print("OCR 결과 %d줄:" % len(lines))
            for l in lines:
                print("  ", l)
        sys.exit(0)
    print("구조 후보(가운데 초록 버튼 하나):", candidate(img))
    print("이미지 판별 점수: %.2f" % template_score(img))
    _last["t"] = 0
    print("점검 판별:", detect(img))
