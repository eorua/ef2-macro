# -*- coding: utf-8 -*-
"""patch271: 텔레그램 봇 알림 (무음 기본, 백그라운드 전송)
토큰·chat_id 는 C:\\macro\\telegram.json (.gitignore 대상) 에 둠 - 코드에 적지 않음
  {"token": "...", "chat_id": "..."}
"""
import sys, os, json, html, threading, urllib.request, urllib.parse

_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram.json")


def _load():
    try:
        with open(_CFG, encoding="utf-8") as f:
            c = json.load(f)
        return str(c.get("token", "")), str(c.get("chat_id", ""))
    except Exception:
        return "", ""


def esc(s):
    """HTML 모드에서 <, &, > 때문에 전송이 깨지지 않게 변수 텍스트를 이스케이프"""
    return html.escape(str(s), quote=False)


def _send(message, silent):
    token, chat = _load()
    if not token or not chat:
        print("[Telegram] telegram.json 이 없거나 비어 있어 전송을 건너뜁니다.")
        return False
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML",
        "disable_notification": "true" if silent else "false",   # 무음 알림 (소리·진동 없음)
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception as e:
        print("[Telegram] 전송 실패: %r" % (e,))
        return False


def send_telegram(message, silent=True, block=False):
    """기본: 무음 + 백그라운드 스레드 전송(네트워크가 느려도 매크로가 멈추지 않음)
    block=True: 보낼 때까지 기다림 (곧바로 끝나는 짧은 스크립트용)"""
    if block:
        return _send(message, silent)
    threading.Thread(target=_send, args=(message, silent), daemon=True).start()
    return True


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "🤖 [오늘도환생2] 텔레그램 무음 알림 테스트"
    print("[Telegram] 전송 성공" if send_telegram(msg, block=True) else "[Telegram] 전송 실패")
