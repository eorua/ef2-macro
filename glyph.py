"""glyph.py - 게임 숫자 글꼴 견본 모으기 (patch186, 템플릿 인식 전환 준비용)
읽은 화면 조각 + 지금 OCR 이 읽은 글자를 shots\\glyph\\ 에 저장. 종류마다 MAX 장까지만 (넘으면 아무것도 안 함)"""
import os, re, time
import cv2

DIR = r"C:\macro\shots\glyph"
MAX = 300
_cnt = {}


def save(kind, img, text):
    try:
        if img is None or img.size == 0:
            return
        if kind not in _cnt:
            try:
                _cnt[kind] = sum(1 for f in os.listdir(DIR) if f.startswith(kind + "_"))
            except OSError:
                _cnt[kind] = 0
        if _cnt[kind] >= MAX:
            return
        os.makedirs(DIR, exist_ok=True)
        lab = re.sub(r"[^0-9a-z.]", "_", (text or "").lower())[:12] or "none"
        name = "%s_%s_%03d_%s.png" % (kind, time.strftime("%m%d_%H%M%S"), _cnt[kind], lab)
        cv2.imwrite(os.path.join(DIR, name), img)
        _cnt[kind] += 1
    except Exception:
        pass
