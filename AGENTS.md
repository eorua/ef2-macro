# AGENTS.md — 오늘도 환생2 자동화 매크로 프로젝트 가이드

이 문서는 **Claude Code**와 **Antigravity CLI (Gemini)** 가 번갈아 작업할 때 동일한 규칙과 프로젝트 맥락을 공유하기 위한 공용 지침서입니다.

---

## ⚠️ 필수 핵심 규칙 (절대 준수)

1. **PC 사용 방해 금지**: 매크로는 PC의 다른 창, 마우스, 키보드 포커스에 최대한 영향을 주지 않아야 합니다.
   - 모든 화면 캡처와 입력은 ADB(`C:\platform-tools\adb.exe`) 또는 창 없는 `scrcpy-server` 직접 소켓 통신(`fastcam.py`)으로만 처리합니다.
   - 자식 프로세스 호출 시 콘솔 창이 깜빡이며 포커스를 빼앗지 않도록 주의합니다 (`CREATE_NO_WINDOW = 0x08000000` 활용).
2. **타 BlueStacks 인스턴스 종료 절대 금지**: 오환2용 BlueStacks 인스턴스(`Pie64_3`, 창 제목에 `오환2` 포함) 외 **다른 BlueStacks 인스턴스는 절대 종료하거나 재시작하지 마세요.** (`taskkill /IM HD-Player.exe` 전체 종료 금지, 반드시 창 제목/인스턴스 확인 후 해당 PID만 제어)
3. **ADB 포트**: 오환2 BlueStacks(`Pie64_3`)의 ADB 포트는 `adbport.py`가 찾아서 씀 (2026-10-25 현재 **`5585`**, 대체값 `5586`). 포트를 코드에 직접 박지 말고 `adbport.py`를 거칩니다.
   - **에뮬레이터 선택 (patch250)**: `C:\macro\emu.json`의 `"emu"`가 `"bluestacks"`(기본, 파일 없을 때도 동일) 또는 `"mumu"`. 뮤뮤는 `mumu_port`(기본 `16384`, 인스턴스마다 +32)·`mumu_index`(기본 `0`) 사용, 재시작/종료는 `MuMuManager.exe control -v <번호>`로 해당 인스턴스만 제어. 롤백은 `"emu": "bluestacks"` 한 단어만 바꾸고 `main.py` 재시작. 단발 시험은 환경변수 `MACRO_EMU=mumu`.
4. **통합 패널 위치**: 여러 프로젝트를 아우르는 통합 패널은 별도 폴더 `C:\pyokey`에 있습니다 (`C:\macro\panel.py`는 오환2 단독 조작 패널).
5. **작업 종료 시 인수인계 및 커밋**: 작업을 마치면 반드시 `HANDOFF.md`를 최신 상태로 갱신("현재 상태 / 최근 작업 / 다음 할 일")하고 `git commit` 합니다.
6. **검토용 diff 남기기 (Claude 검토 사용량 절약)**: 작업을 **시작할 때** 기준 커밋을 적어 두고, 커밋까지 **끝낸 뒤** 그 기준부터의 변경을 `C:\macro\review.diff` 한 파일로 남깁니다 (덮어쓰기, `.gitignore` 대상).
   ```powershell
   # 시작할 때
   git -C C:\macro rev-parse HEAD > C:\macro\review.base
   # 끝낸 뒤 (커밋 후)
   $b = (Get-Content C:\macro\review.base).Trim()
   git -C C:\macro log --oneline "$b..HEAD" > C:\macro\review.diff
   git -C C:\macro diff --stat $b HEAD >> C:\macro\review.diff
   git -C C:\macro diff $b HEAD -- . ":(exclude)*.exe" ":(exclude)*.bin" ":(exclude)*.npz" >> C:\macro\review.diff
   ```
   - `HANDOFF.md`의 해당 작업 항목에 **근거**(벤치 판수·결과 수치, 회귀 테스트 장수 등)와 **미검증/미빌드 항목**(예: `.c`는 고쳤지만 `.exe` 미빌드)을 반드시 적습니다. 근거 없는 실전 설정 변경(`hexa_cfg.json`, `settings.json` 등)은 하지 않고 "제안"으로만 남깁니다.

---

## 1. 프로젝트 목적

모바일 게임 **'오늘도 환생2 (Endless Frontier 2, 패키지명 `com.ekkorr.ef2`)'** 의 반복 플레이(환생 사이클, 영웅/유물/펫 프리셋 전환, 병영 편성 및 배치, 고층 스킬 수동 제어, 일일 숙제, 이벤트 미니게임 등)를 BlueStacks 에뮬레이터(`Pie64_3`, 해상도 `720x1280` 기준) 위에서 백그라운드로 자동화하는 Python 프로젝트입니다.

---

## 2. 폴더 및 주요 파일 역할

### 디렉터리 구조
- `C:\macro\` : 프로젝트 루트 (모든 주요 실행 스크립트 위치)
- `tpl/` : OpenCV 템플릿 매칭용 기준 이미지 모음 (`tpl/bonus/`, `tpl/rtimer/` 등 하위 폴더 포함)
- `shots/` : 디버그용 캡처, 실행 로그(`hexa_log.txt`, `arch2_log.txt`, `raid_log.txt`), 학습/추적 데이터 저장 폴더 (Git 추적 제외)
- `hexa_train/` : 유물 공방(헥사 머지) n-tuple 네트워크 학습용 C/Python 코드 및 도구
- `tests/` : 단위 테스트 및 이미지 판별 검증 스크립트
- `_archive/` : `cleanup.py`로 정리된 구버전 백업(`*.bak*`) 및 패치 파일 보관소

### 주요 파일 역할

#### 핵심 제어 및 인프라
- `main.py` : 메인 자동화 루프. 웨이브 추적, 단계별 업그레이드(중간 업글·고레벨 단계·병영 교체·프리셋 전환), 성 함락/정체 환생, 팝업 닫기, 일일 작업 및 이벤트 호출, 앱/에뮬레이터 복구를 총괄.
- `panel.py` : 오환2 전용 Tkinter GUI 조작 패널. 시작(`F5`)/중지(`F6`)/일시정지(`F7`), 미니게임 단발 실행, 옵션(`settings.json`) 토글, 실시간 로그 표시 및 코드 변경 시 자동 재시작 지원. (전체 통합 패널은 `C:\pyokey`에 별도 존재)
- `adbport.py` : BlueStacks(`Pie64_3`) ADB 주소(`127.0.0.1:5586` 고정 기본값 및 설정 확인) 관리 및 전 모듈 동기화. (patch250: `emu.json`으로 뮤뮤 선택 시 `127.0.0.1:16384` + MuMuManager `info` 포트 확인)
- `emucheck.py` : (patch250) 에뮬레이터 연결·해상도/DPI·screencap·fastcam·터치 점검 도구 (`py emucheck.py [fast]`, `py emucheck.py touch X Y go`).
- `bsrestart.py` : 창 제목에 `'오환2'`가 포함된 `HD-Player.exe` PID만 찾아 안전하게 단독 재시작 (`Pie64_3` 외 다른 인스턴스 보호).
- `fastcam.py` : `scrcpy-server`와 직접 소켓 통신하여 창/마우스 없이 최대 60fps 실시간 화면 수신 및 즉시 터치 전송.
- `speed.py` : `time.sleep` 배율 조절 모듈 (`FACTOR = 0.6`).

#### 환생 사이클 · 전투 · 편성
- `wave.py` : 상단 웨이브 숫자(`Wave NNNN`) 템플릿 인식 및 화면 캡처.
- `rebirth.py` : 성 함락 및 환생 결과 팝업 인식·클릭 처리.
- `bonus.py` : 주말 '환생 훈장 +50%' 이벤트 배지(`N/5`) 및 성 함락 창 보너스 판독, 다이아 500 빨간 환생(하루 5회) 조건 검증.
- `preset.py` : 통합 프리셋(영웅/유물 탭) 전환, 영웅 탭 일괄 레벨업(`+`), 절전 화면 복귀 처리.
- `pet.py` : 구간별 대표 펫 자동 교체(팅키/랩티/백호/맘보/사르크) 및 29번 퀘스트 레벨 확인·보물상자 수령.
- `q30.py` : (선택 옵션) 퀘스트 30번 오픈 골드 수집 및 오픈 전략 자동화.
- `activate.py` : 환생 직후 영웅/유물 프리셋 활성 여부 확인 및 재활성화.
- `barracks.py` : 고레벨 단계에서 병영 유닛 해제 및 종족별 유닛(골렘/죽음의 손 → 드루이드/불의정령/전장의북) 자동 배치.
- `arrange.py` : 성 클릭 '영웅 배치' 창에서 유닛 아이콘 드래그 배치 정리 (불의정령 좌우, 전장의북 중앙, 나머지 12시).
- `newspirit.py` : 고레벨 2단계에서 새로 배치한 불의정령 2마리 훈장 강화 1000 + 골드 레벨 1000 달성.
- `drum.py` : 고레벨 2단계 후 전장의북 2마리 훈장 강화 2000 달성.
- `skillctl.py` : 고층(7200 웨이브 이상)에서 액티브 스킬 3개를 겹치지 않게 수동 쿨타임 제어.
- `wavecall.py` : 고층 진입 시 웨이브 호출 AUTO 끄기 / 환생 후 저층에서 다시 켜기.
- `recruit.py` : 영웅 탭 무료 영입(고용/새로고침) 자동화, 보석 가격 회피(훈장만 구매), 쿨타임 타이머(`MM:SS`) 판독.

#### 일일 숙제 · 미니게임 · 유틸리티
- `daily.py` : 일일 작업 총괄 (상점 무료/광고 보상, 일일 랭킹전, 무한랭킹전, 일일 퀘스트 보상, 던전 소탕, 정령의 고원, 길드 작업 연계).
- `dungeon.py` : 4종 보스 재화량 비교 후 최소 재화 보스 티켓 소탕 + 광고 티켓(하루 5회) 수령 (다이아 구매 버튼 클릭 방지 안전장치 포함).
- `inf2.py` / `lvdigits.py` : 개편된 무한랭킹전 화면 인식, 상대 레벨 판독 및 전투 진행.
- `spirit.py` : 정령의 고원 일일 티켓 구매 및 즐겨찾기 펫 Max 소탕.
- `guild.py` : 길드 출석, 길드 우체국 선물(5회), 길드레이드 상점 티켓/광고 뽑기.
- `raid.py` : 길드레이드 보스 전투/연습 수동 실행 도구 (스킬 타이밍 및 발리스타 약점 조준).
- `soul.py` : 신전 '영혼의 휴식'(최대 4시간 방치 보상) 시작·진행 확인·다이아 2배 종료 처리 (휴식 중에도 던전/고원/무한랭킹전/영입/유물공방 병행 지원).
- `arch.py` / `arch2.py` : 길드 놀이터 양궁 미니게임 자동 조준·발사 (`fastcam` 기반 과녁 속도 추정 및 리드샷).
- `fossil.py` : 이벤트 '화석 발굴' 미니게임 확률 추론 기반 최소 망치 자동 플레이.
- `hexa.py` / `hexa_engine.py` / `hexa_vision.py` / `hexa_nt.py` : 이벤트 '유물 공방(헥사 머지)' 자동 플레이 봇 (23칸 육각 보드 색 인식, n-tuple 가중치 `hexa_nt_w.*` 및 C 탐색기 `hexa_search*.exe` 연동).
- `friend.py` : 친구 우정 포인트 하루 1회 '모두 보내기' 및 빨간 점 감지 시 '모두 받기'.
- `maint.py` / `notice.py` / `ocrx.py` / `hud.py` / `closer.py` : 서버 점검 팝업 대기, 공지 팝업 오늘 하루 보지 않기 닫기, Windows 내장 OCR 기반 출석 보상 인식, 우측 HUD 메뉴 펼침 복구, 열린 창 빨간 X 닫기.
- `cap.py` / `cleanup.py` / `glyph.py` / `split_video.py` : 빠른 화면 캡처 저장, 백업/로그 아카이브 정리, 숫자 글꼴 샘플 수집, 대용량 녹화 영상 분할 도구.
- `state.json` / `settings.json` : 매크로 런타임 상태 저장(환생 기록, 쿨타임 시각 등) 및 패널 옵션 설정 파일 (Git 추적 제외).

---

## 3. 실행 방법

모든 명령은 `C:\macro` 작업 디렉터리에서 실행합니다.

### 조작 패널 실행 (권장)
```powershell
py panel.py        # 콘솔 포함 실행
pyw panel.py       # 콘솔 창 없이 실행
```
- 패널 단축키: `F5` (시작), `F6` (중지), `F7` (일시정지/재개)
- 통합 패널을 사용할 경우 `C:\pyokey`의 패널을 통해 제어할 수 있습니다.

### 메인 루프 직접 실행
```powershell
py main.py         # 시험 모드 (화면 판별만 하고 실제 탭/클릭 안 함)
py main.py go      # 실제 자동화 실행
```
- 일시정지: `C:\macro\PAUSE` 빈 파일을 생성하면 메인 루프가 안전 지점에서 멈추고 `PAUSED` 파일을 생성합니다. `PAUSE` 파일을 삭제하면 재개됩니다.

### 매크로 재시작 방법 (`restart_main.req`)
코드 수정 후 실행 중인 오환2 `main.py`만 안전하게 재시작할 때는 `panel.py`(`# patch183`) 및 통합 패널(`C:\pyokey\hub.py`)의 `watch()`가 2초마다 감지하는 **`C:\macro\restart_main.req` 빈 파일 생성 방식**을 사용합니다.
```powershell
New-Item -Path C:\macro\restart_main.req -ItemType File -Force
```
- **동작 원리**: 실행 중인 패널(`panel.py` 또는 `C:\pyokey\hub.py`)이 `restart_main.req`를 감지하면 즉시 해당 파일을 삭제하고, `C:\macro\main.pid`에 기록된 오환2 `main.py` PID만 종료(`taskkill /PID <pid> /T /F`)한 뒤 2.5초 후 `python.exe main.py go` (`CREATE_NO_WINDOW`)를 새로 실행하여 `main.pid`를 갱신합니다.
- **재시작 전 필수 주의사항**:
  1. **진행 중인 작업 확인**: 재시작 전에 반드시 `macro.log` 마지막 줄과 `state.json`을 확인하여 **영혼의 휴식(`soul.py`), 유물 공방(`hexa.py`), 일일 숙제(`daily.py`), 고레벨 병영/배치(`barracks.py`, `arrange.py`) 등 중요한 작업이 진행 중인지 점검**합니다. 진행 중이라면 임의로 재시작하지 말고 사용자에게 먼저 알리거나 작업 완료 후 일반 전투 상태에서 재시작합니다.
  2. **타 프로세스 종료 절대 금지**: `taskkill /IM python.exe` 같이 전체 Python 프로세스를 종료하면 함께 돌아가는 **표키2 매크로(`C:\pyokey\main.py`)** 나 **통합 패널(`C:\pyokey\hub.py`)** 까지 꺼지므로 절대 사용하지 않습니다. 반드시 `restart_main.req` 파일을 통해 오환2 `main`만 재시작합니다.
  3. **재시작 후 확인**: 약 3~4초 뒤 `restart_main.req` 파일이 삭제되었는지, `main.pid`가 새 PID로 바뀌었는지, `macro.log`에 `매크로 시작 (실제 클릭 모드)` 로그가 찍혔는지 확인합니다.

### 개별 모듈 진단 및 단발 실행 (`look` / `go` 컨벤션)
대부분의 모듈은 안전을 위해 **`go` 인자가 없으면 읽기/판별만 수행(Dry-run)** 하고, **`go`를 붙여야 실제로 화면을 터치**합니다.
```powershell
py adbport.py              # 현재 ADB 포트 확인
py emucheck.py fast        # 에뮬레이터 연결/해상도/캡처/fastcam 점검 (patch250)
py wave.py                 # 현재 웨이브 숫자 인식 테스트
py recruit.py              # 영입 점/쿨타임 상태 확인 (py recruit.py go 로 실제 실행)
py daily.py                # 일일 작업 대상 판별 (py daily.py go 로 실제 실행)
py dungeon.py              # 던전 재화 및 티켓 읽기 (py dungeon.py go 로 소탕)
py soul.py look            # 영혼의 휴식 화면 상태 판별
py bonus.py                # 주말 +50% 배지(N/5) 판독 테스트
py hexa.py look            # 유물 공방 현재 보드 인식 및 추천 수 표시 (shots\hexa_look.png)
py hexa.py play go 1       # 유물 공방 1판 실제 플레이
py arch2.py play go        # 양궁 미니게임 1판 플레이
py fossil.py go            # 화석 발굴 자동 플레이
py raid.py go practice     # 길드레이드 연습 1판 실행
py cleanup.py              # 정리 대상 백업/임시 파일 확인 (py cleanup.py go 로 _archive 이동)
```

---

## 4. 주요 기능 목록

1. **자동 환생 사이클**
   - 저층(환생 직후): `need_low` 단계에서 영웅/유물 프리셋을 저층용(`기본`/`시간` 등)으로 맞추고 대표 펫(팅키/랩티) 설정 및 초반 일괄 레벨업 수행.
   - 중층(`MID_WAVE = 5000`): 중간 영웅 일괄 업그레이드 1회 수행.
   - 고층(`HIGH_WAVE = 6500`, 상한 탐색 `probe` 지원):
     - 1단계: `최대레벨` 프리셋 + 백호/맘보 펫으로 전환, 병영에서 죽음의 손/골렘 배치 후 최대 레벨업.
     - 2단계: `렙뻥` 프리셋 + 사르크 펫 전환, 병영에서 드루이드 6·불의정령 1·전장의북 1 재배치, 불의정령 1000강/1000렙(`newspirit.py`) 및 전장의북 2000강(`drum.py`), 성 영웅 배치 정리(`arrange.py`).
   - 유물 기본 전환(`RELIC_BASIC_WAVE = 7000`) 및 7200층 이상 웨이브 호출 AUTO 해제(`wavecall.py`)·액티브 스킬 수동 제어(`skillctl.py`).
   - 성 함락 시 이어하기(`fall_continue_n`, 최대 3회) 및 환생 처리. 주말 이벤트(`wk_x2`) 조건 충족 시에만 다이아 500 빨간 환생(하루 5회), 그 외에는 항상 초록 무료 환생 클릭.
   - 일정 시간(`STUCK_SEC = 180`초) 동안 웨이브가 오르지 않으면 좌상단 천사 아이콘으로 직접 정체 환생.
2. **주기적·일일 자동 작업**
   - 약 1시간 주기 무료 영웅 영입 및 쿨타임 정밀 추적(`recruit.py`).
   - 게임 기준일(오전 9시 갱신)에 맞춘 일일 퀘스트/출석 보상, 상점 무료·광고 패키지 보상, 일일 랭킹전, 길드 출석·우체국 선물·레이드 상점(`guild.py`), 친구 선물(`friend.py`), 정령의 고원(`spirit.py`).
   - 40분 주기 던전 소탕(`dungeon.py`) 및 2시간 주기 무한랭킹전(`inf2.py`).
   - 신전 '영혼의 휴식'(`soul.py`) 자동 진입/종료 및 휴식 중 주기적 숙제 수행.
   - 환생 후 유물 공방 티켓(`5/5`) 자동 확인 및 플레이(`hexa.py`).
3. **미니게임 AI 및 보조 도구**
   - 유물 공방(헥사 머지) n-tuple AI + C 탐색 엔진(`hexa.py`), 양궁 리드샷(`arch2.py`), 화석 발굴 확률 추론(`fossil.py`), 길드레이드 발리스타 조준(`raid.py`).
4. **장애 복구 및 안전장치**
   - 앱 강제 종료/비활성 감지 시 자동 재실행, 연속 복구 실패 또는 6시간 주기 시 오환2 BlueStacks(`Pie64_3`) 단독 재시작(`bsrestart.py`), 서버 점검 팝업 인식 및 종료 시각까지 대기(`maint.py`), 열린 창 강제 닫기(`closer.py`).

---

## 5. 코딩 규칙

1. **Dry-run 기본 (`go` 플래그)**
   - 새로운 모듈이나 CLI 명령을 작성할 때는 기본적으로 화면 캡처·판독 결과만 출력하고, `sys.argv`에 `"go"`가 있을 때만 실제 ADB 탭/스와이프를 수행하도록 작성합니다.
2. **해상도 및 좌표계**
   - 모든 픽셀 좌표와 ROI(`(x1, y1, x2, y2)`)는 **`720x1280` (세로 모드)** 해상도를 기준으로 작성하며, 주석에 대상 UI 요소 설명과 패치 번호(예: `# patch235: ...`)를 남깁니다.
3. **재화(다이아/보석) 보호 안전장치**
   - 다이아/보석을 소모하는 버튼(영입 보석 구매, 던전 티켓 다이아 구매, 정령의 고원 고가 티켓, 다이아 환생 등)은 사용자가 명시적으로 허용한 조건·옵션이 아니면 **절대 눌리지 않도록** 색상(초록/빨강/파랑 아이콘 비율), OCR, 템플릿 매칭 등 이중 안전장치를 둡니다.
   - 화면 판별이 조금이라도 애매하면 클릭하지 않고 닫기(X) 또는 중단 후 `shots/`에 디버그 캡처를 남깁니다.
4. **백그라운드 무간섭 원칙**
   - Windows GUI 포커스를 뺏는 방식(`pyautogui`, `SetForegroundWindow`, 일반 창 있는 `scrcpy.exe`, `pythonw`에서 콘솔 플래그 없는 `subprocess` 호출 등)은 절대 사용하지 않습니다.
   - ADB 명령이나 외부 실행 파일을 띄울 때 콘솔 창이 뜨지 않도록 관리합니다.
5. **한글 주석 및 로그 유지**
   - 기존 코드 스타일에 맞춰 로그 메시지, 독스트링, 핵심 주석은 이해하기 쉬운 한국어로 작성하고, 기존의 중요한 주석과 패치 히스토리(`# patchNNN`)를 임의로 삭제하지 않습니다.
6. **파일 정리 및 버전 관리**
   - `shots/`, `*.log`, `state.json`, `settings.json`, `*.bak*` 등 런타임/백업 파일은 커밋하지 않습니다 (`.gitignore` 준수).
   - 작업 완료 후에는 반드시 `HANDOFF.md`를 업데이트하고 변경 사항을 커밋합니다.
