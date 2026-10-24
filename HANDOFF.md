# HANDOFF.md — 작업 인수인계 문서

Claude Code와 Antigravity CLI가 번갈아 작업할 때 현재 상태와 진행 내역을 공유하는 문서입니다. 작업을 마칠 때마다 이 파일을 갱신하고 커밋해 주세요.

---

## 현재 상태

- **환경**:
  - 프로젝트 경로: `C:\macro` (통합 패널은 `C:\pyokey`에 위치)
  - 대상 에뮬레이터: BlueStacks 인스턴스 `Pie64_3` (창 제목 `오환2`), ADB 포트 `127.0.0.1:5586` 고정 (`adbport.py`)
- **매크로 코드 상태 (patch246 기준)**:
  - 메인 루프(`main.py`) 및 조작 패널(`panel.py`)을 통해 자동 환생 사이클, 일일 작업(`daily.py`, `dungeon.py`, `spirit.py`, `guild.py`, `friend.py`), 영혼의 휴식(`soul.py`), 무료 영입(`recruit.py`), 고층 스킬/웨이브호출 제어(`skillctl.py`, `wavecall.py`) 가동 중.
  - 최근 업데이트된 주요 기능(현재 커밋 반영 완료):
    - **유물 공방(헥사 머지) 자동화**: `hexa.py`, `hexa_engine.py`, `hexa_vision.py`, `hexa_nt.py` 및 C 탐색기(`hexa_search*.exe`), 가중치(`hexa_nt_w.*`), 학습 코드(`hexa_train/`). 환생 후 및 영혼의 휴식 중 티켓(`5/5`) 자동 확인·플레이 및 중단된 판 이어하기(`patch238~246`) 적용.
    - **주말 환생 훈장 +50% 이벤트 대응**: `bonus.py` 및 `main.py`(`wk_x2` 옵션)에서 토·일(오전 9시 기준) 전투 화면 배지(`N/5`)와 성 함락 창 `+보너스` 확인 후 하루 5회 다이아 500 빨간 환생 기능(`patch235`) 적용.
    - **영혼의 휴식 중 병행 작업 확대**: 휴식 중에도 던전 소탕, 정령의 고원, 무한랭킹전, 무료 영입, 유물 공방 티켓 확인을 수행하도록 개선(`patch233, 236, 240`).
    - **영입 쿨타임 타이머 인식**: `recruit.py` 및 `tpl/rtimer/`를 통해 고용 화면의 남은 시간(`MM:SS`)을 읽어 다음 영입 시각 정밀 예약(`patch222`).

---

## 최근 작업

- **2026-10-24 (Antigravity CLI)**:
  - 원격 병합 과정에서 누락되었던 `daily.py`의 `patch234` (`MY_LEVEL = 72` → `80`) 1줄 반영 및 커밋·푸시.
  - Claude Code와 Antigravity CLI 공용 프로젝트 설명 및 규칙 문서 `AGENTS.md` 작성 (프로젝트 목적, 폴더·주요 파일 역할, 실행 방법, 주요 기능 목록, 필수 안전 규칙 및 코딩 규칙 정리).
  - `CLAUDE.md` (`@AGENTS.md`) 및 `GEMINI.md` (`@./AGENTS.md`) 생성하여 양쪽 AI 도구가 동일한 `AGENTS.md`를 참조하도록 설정.
  - 작업 인수인계 문서 `HANDOFF.md` 최초 작성 및 공용 설명 파일 Git 커밋 (`AI 공용 설명 파일 추가`).
  - `C:\macro\restart_main.req` 요청 파일을 통해 오환2 `main.py` 단독 재시작 완료(PID `333416` 기동 확인, 표키2 매크로·통합 패널 무간섭 유지) 및 `AGENTS.md`에 "매크로 재시작 방법 (`restart_main.req`)"과 주의사항 문서화.

---

## 다음 할 일

1. **실행 중 로그(`macro.log`, `shots/hexa_log.txt`) 모니터링**:
   - 주말 `+50%` 다이아 환생(`bonus.py`), 유물 공방 이어하기 및 조각 출현 기록(`shots/hexa_spawn.jsonl`), 영혼의 휴식 중 병행 작업에서 예외 상황이나 오독이 없는지 확인 및 보정.
2. **파일 및 저장소 관리**:
   - 루트에 쌓이는 백업 파일(`*.bak*`)은 필요 시 `py cleanup.py go`로 `_archive/` 이동.
