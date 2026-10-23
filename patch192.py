"""patch192: 중간 영웅 업그레이드(5000) 동안만 대표 펫 백호
  영웅강화골드로 바꿀 때 펫 백호 -> 일괄 레벨업 -> 유물 '시간'으로 돌릴 때 원래 펫(팅키/랩티)으로 복귀
  ('30퀘 골드 모으는 중' +1000 두 번 방식은 프리셋 창을 안 열므로 그대로)
"""
import os, shutil, sys
BASE = r"C:\macro"
f = os.path.join(BASE, "main.py")
s = open(f, encoding="utf-8").read()
P = [
 ('def run_cycle_mid():\n'
  '    """중간 영웅 업그레이드: 최대레벨 프리셋으로 일괄 레벨업 후 기본/시간으로 복귀"""\n'
  '    ok = preset.set_presets(None, "영웅강화골드")\n'
  '    if not ok:\n'
  '        return False\n'
  '    bulk_ok = preset.bulk_levelup()\n'
  '    final_ok = preset.set_presets(None, "시간")\n',
  'def run_cycle_mid(back_pet="팅키"):\n'
  '    """중간 영웅 업그레이드: 최대레벨 프리셋으로 일괄 레벨업 후 기본/시간으로 복귀\n'
  '    patch192: 업글 동안만 대표 펫 백호, 끝나면 원래 펫으로"""\n'
  '    ok = preset.set_presets(None, "영웅강화골드", pet="백호")\n'
  '    if not ok:\n'
  '        return False\n'
  '    bulk_ok = preset.bulk_levelup()\n'
  '    final_ok = preset.set_presets(None, "시간", pet=back_pet or "팅키")\n'),
 ('                        _mid_ok = run_cycle_mid()\n',
  '                        _mid_ok = run_cycle_mid(st.get("pet_q", "팅키"))     # patch192\n'),
]
if "patch192" in s:
    print("이미 적용됨"); sys.exit(0)
for a, b in P:
    if s.count(a) != 1:
        print("적용 실패: 찾는 코드가 없음 ->", a.splitlines()[0]); sys.exit(1)
shutil.copy2(f, f + ".bak192")
for a, b in P:
    s = s.replace(a, b)
compile(s, f, "exec")
open(f, "w", encoding="utf-8").write(s)
print("모두 적용 (백업: main.py.bak192)")
