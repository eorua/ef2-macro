---
name: ef2-patch
description: 오늘도 환생2 매크로(C:\macro)에서 코드·템플릿·설정을 고치는 모든 작업(patchNNN)의 표준 절차. 버그 수정, 기능 추가, 좌표/임계값 조정, 유물 공방 탐색기 변경 등을 시작할 때 사용.
---

# ef2-patch — 오환2 매크로 패치 작업 절차

이 저장소의 규칙 원문은 `AGENTS.md`입니다. 이 스킬은 그 규칙을 **작업 순서**로 묶은 것입니다. 단계를 건너뛰지 말고, 못 한 단계는 HANDOFF에 "미검증/미실행"으로 적습니다.

## 0. 어디서 돌고 있는지 먼저 확인
- **PC(`C:\macro`, Windows)**: 실행·회귀·커밋 모두 가능.
- **클라우드 사본(리눅스)**: `tests/img/`, `shots/`, `state.json`, `settings.json`, `*.exe`가 없음(gitignore). ADB·실행 불가.
  → 코드 수정, C 빌드(`zig cc -target x86_64-windows-gnu -O3`), 문법 검사, 저장소 안 데이터 분석만 하고, 실행 검증은 "PC에서 확인 필요"로 넘깁니다.

## 1. 시작
1. `HANDOFF.md` 읽기: "현재 상태", "다음 할 일", **마지막 패치 번호**. 상세 이력이 필요하면 `docs/CHANGELOG.md`를 `Grep`으로 해당 파일/패치만 찾기 (통째로 읽지 않음).
2. 이번 패치 번호 = 마지막 번호 + 1. 같은 작업 묶음은 한 번호.
3. 기준 커밋 기록 (PC):
   ```powershell
   git -C C:\macro rev-parse HEAD > C:\macro\review.base
   ```
4. 실행 중인 매크로에 영향이 있는 작업이면 `macro.log` 마지막 줄과 `state.json`으로 영혼의 휴식·유물 공방·일일 숙제·병영 작업이 진행 중인지 확인.

## 2. 수정
- 고칠 파일마다 백업: `<파일>.bak<번호>` (예: `hexa.py.bak279`). `*.bak*`은 git 제외.
- 바뀐 줄 근처에 `# patchNNN: 무엇을 왜` 한국어 주석. 기존 `# patchNNN` 주석은 지우지 않음.
- 좌표·ROI는 720x1280 세로 기준, 주석에 UI 요소 이름.
- 새 CLI·모듈은 dry-run 기본, `go` 인자가 있을 때만 탭/스와이프.
- 다이아·보석 소모 버튼은 이중 안전장치(색 비율 + OCR/템플릿). 애매하면 누르지 말고 닫기 + `shots/`에 캡처.
- 포커스 뺏는 방식 금지(`pyautogui`, `SetForegroundWindow`, 창 있는 scrcpy). 자식 프로세스는 `CREATE_NO_WINDOW`.
- ADB 포트는 하드코딩 금지 → `adbport.py`.
- 실전 설정 파일(`hexa_cfg.json`, `settings.json`)은 **근거(벤치 수치) 없이 바꾸지 않음**. 근거가 없으면 HANDOFF에 "제안"으로만.

## 3. 검증 (가능한 것까지, 결과 수치를 남김)
- 문법: `py -m py_compile <바꾼 파일들>`
- 화면 판독을 바꿨으면: `tests/img` 회귀 → "N장 중 바뀐 것 M장(무엇이 어떻게)" 형태로 기록. 새 템플릿이면 맞을 때 최저점 / 다른 화면 최고점(마진).
- 단발 dry-run: `py <모듈>.py` 또는 `look` 으로 판독만 확인 후 필요하면 `go`.
- 유물 공방 탐색기/가중치: 같은 난수 스트림 벤치(보통 600판) 결과 표, 오차 범위(★10 약 ±3.3%p) 밖일 때만 "개선"으로 판단.
- `.c`를 고쳤으면 exe 빌드 여부를 반드시 기록 (`*.exe`는 git 제외 → 클라우드에서 빌드한 exe는 PC로 따로 옮겨야 함).

## 4. 반영
- 메인 루프에 영향이 있으면 재시작 필요 여부를 판단. 재시작은 **`restart_main.req` 파일로만**:
  ```powershell
  New-Item -Path C:\macro\restart_main.req -ItemType File -Force
  ```
  `taskkill /IM python.exe` 금지 (표키2·통합 패널까지 꺼짐). 다른 BlueStacks 인스턴스 종료 금지.
- 유물 공방만 바뀐 경우 판마다 `hexa.py`가 새로 실행되므로 재시작 불필요.

## 5. 마무리
1. `HANDOFF.md` 갱신:
   - "마지막 패치 번호" 갱신
   - "최근 작업" 맨 위에 3~6줄: 무엇을(파일) / 근거(수치) / 미검증·미빌드 / 백업·롤백 방법
   - 5개를 넘으면 가장 오래된 항목을 `docs/CHANGELOG.md` 맨 위(설명 단락 아래)로 이동
   - "현재 상태", "다음 할 일"에서 바뀐 부분 수정
2. 커밋: `patchNNN: 한 줄 요약`. `shots/`, `*.log`, `state.json`, `settings.json`, `telegram.json`, `emu.json`, `*.bak*`, `*.exe`가 스테이징되지 않았는지 확인.
3. 리뷰용 diff (PC):
   ```powershell
   $b = (Get-Content C:\macro\review.base).Trim()
   git -C C:\macro log --oneline "$b..HEAD" > C:\macro\review.diff
   git -C C:\macro diff --stat $b HEAD >> C:\macro\review.diff
   git -C C:\macro diff $b HEAD -- . ":(exclude)*.exe" ":(exclude)*.bin" ":(exclude)*.npz" >> C:\macro\review.diff
   ```
4. 사용자에게 보고: 바뀐 것, 근거, PC에서 확인해야 할 것(명령어 포함).
