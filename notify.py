# -*- coding: utf-8 -*-
"""Windows 우측 하단 토스트 알림 유틸리티 (windows-toasts 기반)"""
import sys


def notify(message="작업 완료 또는 승인 대기 중!", title="Claude CLI"):
    """우측 하단 Windows 토스트 팝업 표시 (실패 시 예외로 죽지 않고 콘솔 출력)"""
    try:
        from windows_toasts import Toast, WindowsToaster
        toaster = WindowsToaster(title)
        new_toast = Toast()
        new_toast.text_fields = [message]
        toaster.show_toast(new_toast)
        return True
    except Exception as e:
        print(f"[notify] 알림 표시 실패 ({title}: {message}) -> {e!r}")
        return False


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) >= 2 else "작업 완료 또는 승인 대기 중!"
    ttl = sys.argv[2] if len(sys.argv) >= 3 else "Claude CLI"
    notify(message=msg, title=ttl)
