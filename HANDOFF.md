# HANDOFF.md — 작업 인수인계 문서

Claude Code와 Antigravity CLI가 번갈아 작업할 때 **지금 상태와 다음 할 일**만 공유하는 문서입니다.
상세 패치 이력은 `docs/CHANGELOG.md`에 있습니다. (patch279에서 분리 — 이 파일은 짧게 유지)

**작성 규칙**
- "최근 작업"은 최근 5개 패치까지만, 패치당 3~6줄(무엇을 / 근거 / 미검증·미빌드 / 백업). 넘치면 오래된 것부터 `docs/CHANGELOG.md` 맨 위로 옮깁니다.
- 새 패치 번호 = 이 파일과 `docs/CHANGELOG.md`에 나온 **가장 큰 번호 + 1**. (patch266~268이 Claude/Antigravity 양쪽에서 중복 사용된 적 있음)
- **마지막 패치 번호: patch280**

---

## 현재 상태 (patch280 기준, 2026-10-29)

- **환경**
  - 프로젝트 경로 `C:\macro`, 통합 패널·표키2 매크로 `C:\pyokey`, 웹 대시보드 `py web_panel.py` → `http://localhost:5000`.
  - 에뮬레이터: BlueStacks `Pie64_3` (창 제목 `오환2`). `emu.json` = `bluestacks` (patch259에서 뮤뮤에서 롤백).
  - ADB: `adbport.py`가 찾아서 씀 (최근 실측 `127.0.0.1:5585`, 못 찾을 때 대체값 `5586`).
- **메인 루프(`main.py`)**: 환생 사이클(저층 → 5000 중간 업글 → 6500 고레벨 2단계 → 7000 유물 기본 → 7200+ 스킬 수동 제어), 성 함락 이어하기/정체 환생, 주말 +50% 다이아 환생, 영혼의 휴식 및 휴식 중 병행 작업, 일일 숙제·던전·고원·무한랭킹전·영입, 유물 공방 자동, 복구·점검 대기.
  - 웨이브 호출 AUTO: 게임 내 상시 켜짐 전제. patch273부터 메인은 확인·토글하지 않음 (`wavecall.tick/request_check` = no-op, CLI 진단만 남음).
  - 인간 종족 판에서만 30퀘 (`q30_human_only`).
  - 텔레그램 무음 알림: 환생(층수·종류·소요 시간·획득 훈장), 유물 공방 ★10. 토큰은 `telegram.json`(git 제외).
- **유물 공방(헥사 머지)**: C 탐색기 `hexa_search_v8.exe`(search11.c, 합치기 처리 순서 반영) 최우선 → v7 → … → Python. 실전 설정(HANDOFF 기록 기준) `c_hub 30`, `c_tenb 10`, `c_clust 0` = ★10 올인(600판 ★10 20.3%).
- **웹 대시보드**: 오환2/표키2 탭, 상태·환생 기록·로그·단발 실행·옵션 토글. 표키2 패스 일일 보상(`C:\pyokey\pass_quest.py`) 매일 6시 이후 자동.

### ⚠️ git 과 PC 실제 상태가 다를 수 있음 (patch279 확인, PC에서 `git status`로 점검 필요)
클라우드 사본(커밋 `cf04615`) 기준으로 아래가 HANDOFF 기록과 다릅니다. Claude 쪽 패치 일부가 PC에만 있고 커밋되지 않은 것으로 보입니다.
- `hexa_cfg.json`(git): `c_tenb 180`, `c_clust 1.0`, `c_hub` 없음 = **patch259 값**. 기록상 실전 값은 `c_tenb 10 / c_clust 0`(patch260) + `c_hub 30`(patch264).
- `hexa_train/search9.c`(git): 기본값 `TENB 180 / CLUST 1.0` (patch260에서 0으로 되돌렸다고 기록됨).
- git에 없는 파일: `hexa_train/search10.c`, `bench_clust.*`, `bench_hub*.py/.bat`, `bench_hub*_result.txt`.
- `hexa_nt.py`·`search11.c`·`core5.inc`(patch260~269)는 git에 있음.
→ PC에서 `git status` / `git diff hexa_cfg.json` 확인 후, 실전 값이 맞으면 해당 파일들을 커밋해 주세요. **설정값 자체는 이번 패치에서 건드리지 않았습니다.**

---

## 최근 작업 (최근 5개, 상세는 `docs/CHANGELOG.md`)

- **2026-10-29 (Claude, patch280) 영혼의 휴식이 끝났는데 계속 휴식 중으로 아는 문제** (`soul.py`):
  - 원인: 종료 시각을 '기록한 시작 시각 + 4시간' 내부 시계로만 계산, 종료 시각 전엔 화면을 전혀 안 봄 → 시작 시각이 틀리면(이미 휴식 중인 걸 발견해 지금 시각으로 기록 등) 게임은 끝났는데 매크로는 최대 4시간 더 멈춤.
  - 수정 1: 휴식 화면이 보이면 10분마다 Windows OCR로 시간(`HH:MM:SS`/`N시간 M분`/`MM:SS`) 읽기 → 늘어나면 경과, 줄면 남은 시간으로 판별해 시작 시각 보정. 종료를 앞당기는 보정은 90초 뒤 다시 읽어 같을 때만. 0 또는 4:00에서 멈추면 종료 처리.
  - 수정 2: 종료 시각 전에도 10분마다 휴식 화면 확인(가린 창 X 닫고 재확인), 연속 3번(약 30분) 안 보이면 끝난 것으로 보고 추적 종료(쿨타임 8시간 기록).
  - 근거: 클라우드에서 가짜 입력으로 판별 시험(경과 3시간 오차 보정, 남은 0 종료, 4:00 멈춤 종료, 30분 미표시 종료) 통과. **실제 휴식 화면 OCR은 미검증** — 시간 글자 위치·형식 모름(ROI `0,150,720,640` 넓게 잡음). 못 읽으면 1시간마다 `shots/soul_timer_fail_*.png` 남기고 내부 시계로 계속.
  - 확인: `py soul.py time`(휴식 화면에서). 메인 재시작 필요. 백업 `soul.py.bak280`.
- **2026-10-29 (Claude, patch279) 인수인계 문서 정리 + 작업 절차 스킬** (`HANDOFF.md`, `docs/CHANGELOG.md`, `AGENTS.md`, `.claude/skills/ef2-patch/SKILL.md`, `.gitignore`):
  - HANDOFF 313줄(약 2.7만 토큰) → 이 형태로 축소, 기존 상세 기록은 `docs/CHANGELOG.md`로 원문 이동.
  - `AGENTS.md`: 패치 번호 규칙, HANDOFF/CHANGELOG 운용, 문서 불일치 수정(ADB 대체값 5586, wavecall patch273 반영).
  - `.claude/skills/ef2-patch/` 신설(패치 작업 절차). `.gitignore`의 `.claude/`를 `.claude/*` + `!.claude/skills/`로 바꿔 스킬만 추적 (`settings.local.json`은 계속 제외).
  - 코드·설정 변경 없음. 메인 재시작 불필요.
- **2026-10-26 (Antigravity, patch278)** 표키2 패스 일일 보상 자동화(`C:\pyokey\pass_quest.py`), 웹 패널 버튼 정리, Claude 권한 설정.
- **2026-10-26 (Antigravity, patch277)** 보석 영웅 이름 판독 개선(`GEM_ROW_DY` 107→90, 크롭·패딩, `KNOWN_HEROES` 퍼지 매칭), 웹 패널 재시작 단독 구동.
- **2026-10-26 (Antigravity, patch276)** 웹 패널 2차: 유물 공방 옵션 드롭다운 통합, 표키2 기능 이식.

---

## 다음 할 일

0. **(patch280) 영휴 시간 OCR 확인**: 휴식 중에 `py soul.py time` → 읽은 글자/초/종류 확인. 못 읽으면 휴식 화면 캡처(`py cap.py`)를 Claude에게 주면 ROI·형식 맞춤. `macro.log`에서 `휴식 시간 보정`/`안 보임 (n/3)` 로그 확인.
0. **(patch279) PC에서 git 불일치 확인** — 위 ⚠️ 항목. 그리고 `git pull`로 이번 문서 정리 받기 (로컬에서 `HANDOFF.md`를 고친 게 있으면 충돌 가능 → 로컬 내용을 새 형식의 "최근 작업"에 옮겨 적으면 됨).
1. **(patch263) 양궁 X 리셋 루프 실전 시험**: `py guild.py arch go`. 첫 미스 후 X 탈출 → 재진입 시 오늘 도전 기회가 차감되지 않는지 확인.
2. **(patch265) `hexa_train\bench_hub3.bat` 결과 확인**: 합격 설정은 `hexa_cfg.json`에 자동 적용됨 (백업 `hexa_cfg.json.bak265`).
3. **유물 공방 확률 상수 보정 검토**: `hexa_spawn.jsonl`이 1,000수 이상 쌓이면 실측 비율(칸 수 1/2/3 = 36.5/37.9/25.6%, 상대 등급 lo/lo+1/hi = 54.8/28.8/16.4%)로 `core*.inc`의 `W_N`, `W_T` 보정 검토. 출현 예측기(카운팅)는 불필요(i.i.d. 확인).
4. **(보류) 뮤뮤 재시험**: `emu.json` → `mumu`, `py adbport.py scan` → `py emucheck.py fast` → `touch X Y go`. MuMuManager `control` 재시작은 미검증.
5. **로그 모니터링**: `macro.log`, `shots/hexa_log.txt` — 주말 다이아 환생, 유물 공방 이어하기, 영휴 중 병행 작업 오독 여부.
6. 루트 `*.bak*` 정리는 `py cleanup.py go`.
