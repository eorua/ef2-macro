# -*- coding: utf-8 -*-
"""Windows 우측 하단 토스트 알림 유틸리티 (windows-toasts 기반)
patch271: 토스트 무음 + 같은 내용을 텔레그램(무음)으로도 전송"""
import sys


def notify(message="작업 완료 또는 승인 대기 중!", title="Claude CLI"):
    """우측 하단 Windows 토스트 팝업 표시 (실패 시 예외로 죽지 않고 콘솔 출력)"""
    ok = False
    try:
        from windows_toasts import Toast, WindowsToaster, ToastAudio
        toaster = WindowsToaster(title)
        new_toast = Toast()
        new_toast.text_fields = [message]
        new_toast.audio = ToastAudio(silent=True)          # patch271: 알림 소리 끔
        toaster.show_toast(new_toast)
        ok = True
    except Exception as e:
        print(f"[notify] 알림 표시 실패 ({title}: {message}) -> {e!r}")
    try:                                                   # patch271: 텔레그램(무음)도 함께
        from telegram_bot import send_telegram, esc
        # 배치에서 py notify.py 로 부르면 곧바로 끝나므로 보낼 때까지 기다림
        send_telegram("🔔 <b>%s</b>\n%s" % (esc(title), esc(message)), block=True)
    except Exception as e:
        print(f"[notify] 텔레그램 전송 실패 -> {e!r}")
    return ok


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) >= 2 else "작업 완료 또는 승인 대기 중!"
    ttl = sys.argv[2] if len(sys.argv) >= 3 else "Claude CLI"
    notify(message=msg, title=ttl)
