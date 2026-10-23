"""ocrx.py - 윈도우 내장 OCR 로 글자와 위치를 읽어서 '출석 보상' 창을 찾아 받기/닫기 (창 모양이 달라도 글자로 찾음)

  py ocrx.py words      지금 화면의 글자와 위치(중심 좌표) 출력
  py ocrx.py look       출석 보상 창으로 판별되는지, 눌러야 할 위치는 어디인지 출력 (누르지 않음)
  py ocrx.py go         출석 보상 창이면 받기 -> (남아 있으면) X 까지 실제로 누름
main.py 의 find_popup 이 템플릿으로 못 찾을 때 find_attendance(img) 를 대신 호출합니다.
"""
import os, re, sys, time, subprocess, tempfile
import cv2, numpy as np

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
foreach ($l in $res.Lines) {
    foreach ($w in $l.Words) {
        $r = $w.BoundingRect
        Write-Output ('{0}|{1}|{2}|{3}|{4}' -f $w.Text, [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height)
    }
}
'''

OCR_COOLDOWN = 30            # 같은 화면이 계속 후보여도 이 초마다 한 번만 OCR
_state = {"t": 0.0, "btn": 0.0, "active": False}


def log(*a):
    print(time.strftime("[%H:%M:%S] ocr:"), *a, flush=True)


def words(img):
    """화면의 글자들 -> [(글자, 중심x, 중심y, 폭, 높이)]. OCR 을 쓸 수 없으면 None"""
    try:
        d = tempfile.gettempdir()
        png = os.path.join(d, "ef2_ocrx.png")
        ps1 = os.path.join(d, "ef2_ocrx.ps1")
        cv2.imwrite(png, img)
        with open(ps1, "w", encoding="utf-8-sig") as f:
            f.write(PS_SCRIPT)
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, png],
                           capture_output=True, timeout=60)
        out = [x.strip() for x in r.stdout.decode("utf-8", errors="replace").splitlines() if x.strip()]
        if not out or out[0] != "OK":
            return None
        res = []
        for line in out[1:]:
            p = line.rsplit("|", 4)
            if len(p) != 5:
                continue
            try:
                x, y, w, h = (int(v) for v in p[1:])
            except ValueError:
                continue
            res.append((p[0], x + w // 2, y + h // 2, w, h))
        return res
    except Exception as e:
        log("OCR 오류:", repr(e))
        return None


def red_x_buttons(img, x_min=560, y_min=40, y_max=620):     # patch137: 출석 보상 X 가 y=77 에 있어 90 -> 40
    """오른쪽의 빨간 X(닫기) 버튼들 -> [(x, y)] (위쪽부터). 제목줄의 작은 X(약 35px)도 찾음"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = (((h <= 10) | (h >= 170)) & (s > 120) & (v > 100)).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(red, 8)
    out = []
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        if not (26 <= w <= 80 and 26 <= hh <= 80) or abs(int(w) - int(hh)) > 10 or a < 0.33 * w * hh:
            continue
        cx, cy = int(x + w // 2), int(y + hh // 2)
        if cx < x_min or not (y_min <= cy <= y_max):
            continue
        hv = hsv[y:y + hh, x:x + w]
        wf = float(((hv[..., 1] < 90) & (hv[..., 2] > 170)).mean())
        if not (0.05 <= wf <= 0.45):
            continue
        out.append((cx, cy))
    out.sort(key=lambda p: p[1])
    return out


def analyze(ws):
    """OCR 결과 -> 출석 보상 창인지, 받기 버튼 위치"""
    texts = [w[0] for w in ws]
    joined = " ".join(texts)
    is_att = ("출석" in joined and ("접속" in joined or "보상" in joined) and ("받기" in joined or "일 보상" in joined)) \
        or ("출석" in joined and "보상" in joined and "접속" in joined)
    btn = None
    for t, x, y, w, h in ws:
        if "받기" in t:
            if btn is None or y > btn[1]:
                btn = (x, y)                     # 받기 가 여러 개면 가장 아래(큰 버튼)
    return is_att, btn, joined


def find_attendance(img, force=False):
    """출석 보상 창이면 (이름, 눌러야 할 좌표) 아니면 None. 처음엔 받기, 이미 눌렀는데 창이 남아 있으면 X
    force=True: 제목 그림으로 이미 출석 창임을 확인함 -> 빨간 X/대기시간 검사 없이 바로 글자로 '받기' 찾기 (patch137)"""
    xs = red_x_buttons(img)
    if not xs and not force:
        _state["active"] = False
        return None
    now = time.time()
    if not force and not _state["active"] and now - _state["t"] < OCR_COOLDOWN:
        return None
    _state["t"] = now
    ws = words(img)
    if not ws:
        return None
    is_att, btn, joined = analyze(ws)
    if not is_att and not force:
        _state["active"] = False
        return None
    _state["active"] = True
    if btn is not None and now - _state["btn"] > 25:
        _state["btn"] = now
        log("출석 보상 창 (글자로 인식) -> 받기 %s" % (btn,))
        return "출석 보상(글자)", btn
    if not xs:
        return None
    log("출석 보상 창이 남아 있음 -> 닫기 X %s" % (xs[0],))
    return "출석 보상 닫기(글자)", xs[0]


if __name__ == "__main__":
    BASE = r"C:\macro"
    sys.path.insert(0, BASE)
    import preset
    img = preset.capture()
    if img is None:
        print("캡처 실패"); sys.exit(1)
    if "words" in sys.argv[1:]:
        ws = words(img)
        if ws is None:
            print("OCR 사용 불가")
        else:
            for w in ws:
                print("%-12s 중심 (%d, %d)" % (w[0], w[1], w[2]))
        sys.exit(0)
    ws = words(img)
    if ws is None:
        print("OCR 사용 불가"); sys.exit(1)
    is_att, btn, joined = analyze(ws)
    print("출석 보상 창:", is_att, "| 받기 위치:", btn, "| 빨간 X:", red_x_buttons(img))
    if "go" in sys.argv[1:] and is_att:
        if btn:
            preset.GO = True
            preset.tap(btn, "받기")
            time.sleep(1.5)
            img = preset.capture()
            ws = words(img) or []
            is_att, btn, joined = analyze(ws)
        xs = red_x_buttons(img)
        if is_att and xs:
            preset.GO = True
            preset.tap(xs[0], "닫기 X")
