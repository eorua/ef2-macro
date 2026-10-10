import time

# 매크로 동작 사이의 대기시간에 곱하는 배율 (1.0 = 원래 속도, 작을수록 빠름)
# 너무 빨라서 클릭이 빗나가면 0.8 -> 0.9 처럼 올리고, 더 빠르게 하려면 0.7 처럼 내리세요.
FACTOR = 0.6
MIN_WAIT = 0.2          # 줄여도 이보다 짧게는 쉬지 않음
MAX_SCALED = 3.0        # 이보다 긴 대기(부팅 대기 등)는 원래대로 둠

_real_sleep = time.sleep


def _fast_sleep(sec):
    if 0.3 < sec <= MAX_SCALED:
        sec = max(sec * FACTOR, MIN_WAIT)
    _real_sleep(sec)


time.sleep = _fast_sleep
