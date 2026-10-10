# patch50.py - 실패 시 열려 있는 창의 빨간 X 를 찾아 닫고 다시 시도 (C:\macro 에서 py patch50.py)
#   * closer.py 추가: py closer.py 로 지금 화면의 X 위치를 확인할 수 있습니다 (go 를 붙이면 닫음)
#   * 병영 편성 방식의 각 단계가 실패하면 -> 창 닫기 -> 같은 단계를 한 번 더 시도 -> 그래도 실패하면 영웅 기본 프리셋으로 복구
#   * 고레벨 단계가 "알 수 없는 팝업/화면"으로 실패했을 때도 창을 닫아 봅니다
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
CL = os.path.join(HERE, "closer.py")
DATA = """
eNqFVm1r21YU/u5fcVBhSK2qKl5fgqkLWz5sha2FFrYME4QSy7GofSUs5cWwD0lripsE1q55cYadJZAsL8uYaZKSQrof5Hv9H3bO
lSzbCVv8QZau7jnnOc9zzrlSFGWq5AVOxfCrcBu6m6v88FRsvAW+vg1iq86XVkG0P4tWA/ing067BuMqX/6zc97WgH+odZcuRKuG
O/4RazVRa0L0DlSxvNtdOQB+ctY5Oxa/HWqpFLrh+3W+vAvjIJo18alBzvnyMW9d8F9qwI8OxPo7NQ4jXh532ovdxhrcgm6rDeOa
aC1Ap70pmhf87wW+09RBvHrTObmIDWl9pymhLJ3xZQpkpAAwrX6CyU/sL3TO6/10CTpZYogE3P4KiI9Nvr0HKq/X+N4pGoFYWxKt
Fe2y42mv57jnhO8hsPoK//044k/mx9+9JYbQQ0pRlJRb9r1KCEE10CF0y05vYWo2rQObKaNjOwDm99b9ihM4YSo1bn3/+IkOPyV/
X41DFu6bpg4j9/Ay+qUZw7nRE2QcqVtIBG0sio2/UKTGLt87F0efdcIIYrvJjw7FLkJ9/atonfKVBZQtlXcKUHBZ3qo4eWtedcvT
OpRdZgXZuxirbM/j3YNRLZOigJjWFQHFWp0qSqo4CCOqH/5+l6pL7L4Ty8egzutQxdI6OuQ7LeKInBaDWcwPWTGmZsMxr+RVIhS0
Mvb0u6fPrK+/eZb+9vkPWrRdBySUTNAwZxiGDuaE3n8YGXxIT0gbzA33q6pahIdZGNXgZ8DbR1kYeZDWNPgC1AAewchdU97P0n3a
1DTDDsKq76jMN2ZcFo5GAJgOJXsSUYSI0WE97B5jzlTo5Mc8lJM5LAx+dMPi89AOAxXjo26RuTcTokkuAlbwKuCCy6Bis2lHHcHC
iKmmH7Glwxzmg0nbaBWEOXciee0WgHkhqFIuSmyOLlIysFkekvViMXkx4J1+iDp02Ywz6NOeDFTMVp3TcGTQTbGIHCElJiBaGx6C
ady7Bzcx3E10fY3DYk+paqaKzU6ZzGfm8W6un8hcAfcUSp4dkkSJjhjpfqRIMZETcaRNkqbs2EzVtCtkmIZ5X3JRoKtpoKbXIERB
DNv3HZZXZd4SHNy5A2lNl/lHuKOVOGLFCWcqjEzjFpLDwpqcCUOPBVS/cdR4Y86XUvsk9XC3aYTcz5kTVI6y9aV2svspAz9HRGSj
OTAxFM0ulVQSlWXvDvTnySk1t5y98WygYdVda/CXDbF6eHlsyXllRP80gZuijodBu9HdbBjU2xA7PDzFpxo/Pu18eEXzXL7CwflH
rdfH1AlmUtVWv6olxgEVMGvcGo07Y8r2kSFHHVKSdrgBPME+GhZvsuLYL5IVPwyo+65Qf7kocN81bowAJ7D6wqlmS3Z5Mm+Dn4Hb
RL2W2NyQ+W81cKCqyEn39RlNO7G1h+tb8kxtSlY1/nGhW2v3vUd5hravYqAczSqF5nFPHqUPl8EtHEnJIx0aRlByHB+renSo8BgW
AiZnWcwuO5YF2SwollW2seMtJcr1f1j+L94GqCfaiH5wSoHTm1Z+hdpBiU/BXgIZRSePkWv0oEx7ComPB59hV6ZncyOZicwAHdJH
XG9IBJn36znuL4p6xQY/O5rdjYY8at83M8P1OHyIrzX6nwmAXyt4+NFfd/2NRL6P3y6LLRJt2tNQgH8B8OBwlw==
"""

NEW_CYCLE = '''def _retry_step(name, fn, *a, **k):
    """한 단계를 실행하고, 실패하면 열려 있는 창을 닫은 뒤 한 번 더 시도"""
    import closer
    if fn(*a, **k):
        return True
    n = closer.close_all()
    log("%s 실패 -> 열린 창 %d개 닫고 한 번 더 시도" % (name, n))
    return bool(fn(*a, **k))


def run_cycle_barracks():
    """병영 편성 방식 고레벨 단계 (패널 옵션 barracks_swap)"""
    import barracks, closer
    closer.close_all()                      # 시작 전에 남아 있는 창이 있으면 정리
    if not _retry_step("골렘 편성(1단계)", barracks.phase1):
        return _barracks_fallback("골렘 편성(1단계)")
    if not _retry_step("유물 프리셋 변경", preset.set_presets, None, "영웅강화골드"):
        return _barracks_fallback("유물 프리셋 변경")
    if not _retry_step("일괄 레벨업", preset.bulk_levelup, max_rounds=1):
        return _barracks_fallback("일괄 레벨업")
    if not _retry_step("최종 편성(2단계)", barracks.phase2):
        return _barracks_fallback("최종 편성(2단계)")
    for _ in range(3):
        if preset.set_presets(None, "기본"):
            return True
        closer.close_all()
        time.sleep(2)
    log("최종 유물 프리셋(기본) 설정 실패 -> 다음 기회에 재시도")
    return False


'''

A_UNK = ('                                log("고레벨 단계 실패: 알 수 없는 팝업/화면으로 추정 → 실패 횟수에 넣지 않음")\n'
         '                                time.sleep(5)\n')
B_UNK = ('                                log("고레벨 단계 실패: 알 수 없는 팝업/화면으로 추정 → 실패 횟수에 넣지 않음")\n'
         '                                try:\n'
         '                                    import closer\n'
         '                                    log("열린 창 %d개 닫음" % closer.close_all())\n'
         '                                except Abort:\n'
         '                                    raise\n'
         '                                except Exception as e:\n'
         '                                    log("창 닫기 오류: %r" % (e,))\n'
         '                                time.sleep(5)\n')


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(MAIN):
        print("main.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    ms = open(MAIN, encoding="utf-8").read()
    if "def run_cycle_barracks(" not in ms:
        print("먼저 patch48.py 를 적용하세요"); return 1
    data = zlib.decompress(base64.b64decode("".join(DATA.split())))
    if os.path.exists(CL) and open(CL, "rb").read() == data:
        print("closer.py 는 이미 최신")
    else:
        if os.path.exists(CL):
            print("백업:", backup(CL))
        open(CL, "wb").write(data)
        print("closer.py 저장")
    if "_retry_step(" in ms:
        print("main.py 는 이미 최신"); return 0
    i = ms.index("def run_cycle_barracks():")
    j = ms.index("def run_cycle_high():")
    if i > j or ms.count(A_UNK) != 1:
        print("main.py 앵커 불일치 -> main.py 를 올려 주세요"); return 1
    ns = ms[:i] + NEW_CYCLE + ms[j:]
    ns = ns.replace(A_UNK, B_UNK, 1)
    print("main.py 백업:", backup(MAIN))
    open(MAIN, "w", encoding="utf-8").write(ns)
    print("main.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
