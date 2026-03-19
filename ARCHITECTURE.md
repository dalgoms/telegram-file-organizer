# Telegram File Organizer Bot — 아키텍처 & 설계 문서

> 대화 기반 설계 과정 기록 | 2026-03-19

---

## 1. 프로젝트 개요

텔레그램에서 폴더 경로를 보내면 AI가 파일을 분석하여 자동으로 정리해주는 봇.
"나 대신 커서가 해주던 파일 정리를, 커서 없이도 쓸 수 있게" 가 출발점.

### 핵심 가치
- **기록의 허들을 0으로** — 텔레그램 한 줄이면 정리 시작
- **AI가 대신 판단** — 어떤 폴더에 넣을지 사람이 안 정해도 됨
- **실수해도 복구** — 모든 이동 기록을 남기고 Undo 가능

---

## 2. 설계 동기 — 대화에서 나온 핵심 질문들

### Q1. "커서가 해주던 파일 정리를 봇으로 만들 수 있어?"
→ 가능. 텔레그램 봇 + Python pathlib/shutil + OpenAI API 조합.

### Q2. "장기간 근로한 직원들이 진짜 편하다고 느끼려면?"
→ 단순 정리만으로는 부족. 수년간 쌓인 파일의 고통을 해결해야 함:
- 같은 파일이 여러 폴더에 중복
- "보고서_최종_수정_진짜최종" 버전 지옥
- 용량 먹는 파일이 어디인지 모름
- 5년 치 파일이 한 폴더에 섞여 있음

→ `/dup`, `/ver`, `/size`, `/old`, `/report` 분석 기능 추가

### Q3. "집 컴퓨터랑 회사 컴퓨터 구분해서 명령할 수 있어?"
→ 기기별 봇 인스턴스 + `DEVICE_NAME` 환경변수로 해결.
  모든 응답에 `[집PC]`, `[회사PC]` 태그 표시.

---

## 3. 시스템 아키텍처

```
텔레그램 (사용자)
│
│  /scan D:\Downloads
│
▼
bot.py ─── 명령어 라우팅
│
├── scanner.py ─── 파일 시스템 스캔
│   └── FileInfo, ScanResult 데이터 클래스
│
├── classifier.py ─── GPT-4o-mini로 AI 분류
│   └── 파일 목록 → JSON 카테고리 매핑
│
├── organizer.py ─── 실제 파일 이동 + Undo
│   └── history.json에 모든 이동 기록
│
├── analyzer.py ─── 장기 근속자용 분석 도구
│   ├── find_duplicates() ─── MD5 해시 기반 중복 탐지
│   ├── find_version_chains() ─── 최종/수정/v1 패턴 인식
│   ├── analyze_size() ─── 용량 TOP + 확장자별 통계
│   ├── suggest_archive() ─── 연도별 아카이브 제안
│   └── search_files() ─── 키워드 검색
│
├── rules.py ─── 커스텀 분류 규칙
│   └── rules.json에 패턴 → 폴더 매핑 저장
│
├── cloud/gdrive.py ─── Google Drive API 연동
│
└── config.py ─── 환경변수 + 설정 관리
    └── DEVICE_NAME으로 기기 식별
```

---

## 4. 데이터 흐름

### 정리 흐름 (메인)

```
사용자 입력          처리 단계              결과
──────────     ──────────────     ──────────
/scan 경로  →  scanner.scan_local()  →  ScanResult (파일 목록)
            →  classifier.classify()  →  {folders: {카테고리: [파일]}}
            →  rules.apply_rules()    →  커스텀 규칙 우선 적용
            →  미리보기 전송           →  텔레그램 메시지 + 버튼

정리 실행   →  organizer.execute()    →  폴더 생성 + 파일 이동
            →  history.json 저장      →  Undo 가능 상태

/undo       →  organizer.undo_last()  →  원위치 복원 + 빈 폴더 삭제
```

### 분석 흐름 (장기 근속자용)

```
/dup   →  크기 비교 → MD5 해시 비교 → 중복 그룹 리포트
/ver   →  정규식으로 버전 키워드 제거 → 기본명 동일 파일 그룹핑
/size  →  크기 정렬 TOP N + 확장자별 집계
/old   →  수정 날짜 기준 연도별 분류 → 아카이브 제안
/find  →  마지막 스캔 결과에서 파일명 매칭
/report → 위 전부를 순차 실행 → 종합 진단
```

---

## 5. 핵심 설계 결정

### 5.1 미리보기 필수 패턴

```
스캔 → AI 분류 → [미리보기] → 사용자 확인 → 실행
                     ↑
               이 단계가 핵심
```

**이유**: 파일 이동은 되돌릴 수 있지만, 사용자가 의도하지 않은 이동은 신뢰를 깨뜨린다.
모든 자동화 도구의 첫 번째 원칙: "예측 가능해야 한다."

### 5.2 중복 탐지 — 2단계 필터링

```
전체 파일 → [1단계: 크기 비교] → 크기 같은 파일만 → [2단계: MD5 해시] → 진짜 중복
```

**이유**: 해시 계산은 디스크 I/O가 큼. 크기가 다르면 중복이 아니므로 먼저 걸러냄.
대용량 파일은 앞뒤 8KB만 해시하여 속도 최적화.

### 5.3 버전 체인 — 한국어 + 영어 패턴

인식하는 버전 패턴:
| 패턴 | 예시 |
|------|------|
| 한글 버전 | 최종, 수정, 진짜최종, 최최종, 초안 |
| 영문 버전 | final, revised, rev, draft, copy |
| 숫자 버전 | v1, v2, v3 |
| 날짜 버전 | 20260318 (8자리 숫자) |
| 괄호 버전 | (1), (2), (3) |

**방식**: 정규식으로 버전 표시를 제거 → 나머지가 같으면 같은 파일의 버전으로 판단

### 5.4 기기 식별 — 환경변수 방식

```
# 집 PC
DEVICE_NAME=집PC
TELEGRAM_BOT_TOKEN=집봇_토큰

# 회사 PC  
DEVICE_NAME=회사PC
TELEGRAM_BOT_TOKEN=회사봇_토큰
```

**이유**: 가장 단순한 방식. 서버/DB/네트워크 없이 각 PC가 독립 실행.
한 봇 토큰은 한 인스턴스만 가능하므로 (Telegram Polling 제약) 봇을 2개 만든다.

### 5.5 안전장치 체계

| 장치 | 구현 |
|------|------|
| 미리보기 필수 | 정리 전 항상 분류안 표시 + 확인 버튼 |
| Undo | history.json에 from/to 경로 기록, 역순 복원 |
| 시스템 파일 보호 | SKIP_DIRS, SKIP_FILES로 .git, node_modules 등 자동 제외 |
| 파일명 충돌 | 동일명 존재 시 `파일_1.ext`, `파일_2.ext`으로 자동 번호 부여 |
| 이력 제한 | 최근 50건만 보관 (무한 증가 방지) |
| 스캔 제한 | MAX_FILES_PER_SCAN = 500 (메모리/API 비용 보호) |

---

## 6. 모듈 상세

### bot.py — 텔레그램 핸들러 (약 440줄)
- 16개 명령어 핸들러 등록
- `PENDING_SCANS`: 스캔 결과 임시 저장 (확인 대기)
- `LAST_SCANS`: 마지막 스캔 캐시 (분석 명령어 재사용)
- `TAG`: 모든 응답에 `[기기명]` 접두사 부착
- 일반 메시지도 경로 패턴 감지 시 자동 스캔

### scanner.py — 파일 스캔 (약 120줄)
- `FileInfo` 데이터 클래스: name, path, extension, size, modified
- `ScanResult`: 파일 목록 + 에러 + 건너뛴 항목 수
- 재귀/비재귀 스캔 지원 (`-r` 옵션)
- 확장자별 현황 요약

### classifier.py — AI 분류 (약 100줄)
- GPT-4o-mini 사용 (빠르고 저렴, 분류에 충분)
- temperature 0.2 (일관성 우선)
- 프롬프트: 2단계 한글 폴더 구조로 분류하도록 지시
- JSON 파싱 실패 대비: 코드 블록 제거 후처리

### organizer.py — 파일 이동 + Undo (약 180줄)
- `execute_organization()`: 폴더 생성 → 파일 이동 → 이력 저장
- `undo_last()`: 마지막 이력 역순 복원 → 빈 폴더 자동 삭제
- `history.json`에 세션 단위로 기록

### analyzer.py — 분석 도구 (약 280줄)
- `find_duplicates()`: 크기→해시 2단계 중복 탐지
- `find_version_chains()`: 11개 정규식 패턴으로 버전 키워드 제거 후 그룹핑
- `analyze_size()`: TOP N + 확장자별 용량/개수 통계
- `suggest_archive()`: 올해가 아닌 파일을 연도별 분류
- `search_files()`: 키워드 포함 파일 검색

### rules.py — 커스텀 규칙 (약 90줄)
- glob 패턴 기반 매칭 (`*.pptx` → `문서/프레젠테이션`)
- AI 분류 결과에 커스텀 규칙을 우선 적용
- rules.json에 영구 저장

### cloud/gdrive.py — Google Drive (약 150줄)
- OAuth 2.0 인증 (credentials.json → token.json)
- 폴더 스캔, 파일 이동, 폴더 생성
- 로컬과 동일한 ScanResult 형식으로 통일

### config.py — 설정 (약 20줄)
- 환경변수 로드
- DEVICE_NAME 자동 감지 (미설정 시 hostname 사용)
- SKIP_DIRS/SKIP_FILES 목록

---

## 7. 기술 스택

| 계층 | 기술 | 선택 이유 |
|------|------|-----------|
| 인터페이스 | Telegram Bot API | 매일 여는 앱, 허들 최저 |
| 봇 프레임워크 | python-telegram-bot 21.10 | 비동기 지원, 버튼/콜백 내장 |
| AI 분류 | OpenAI gpt-4o-mini | 파일 분류는 단순 작업, 빠르고 저렴 |
| 파일 조작 | pathlib + shutil | Python 표준 라이브러리, 안정적 |
| 중복 탐지 | hashlib MD5 | 빠른 해시, 보안이 아닌 비교 목적 |
| 클라우드 | Google Drive API v3 | 한국 직장인 점유율 높음 |
| 설정 | python-dotenv | .env 파일 기반, 기기별 설정 분리 |
| 데이터 저장 | JSON 파일 | DB 불필요, 이력/규칙 정도는 JSON으로 충분 |

---

## 8. 명령어 전체 맵

```
봇 명령어 (16개)
│
├── 정리 ─────────────────────
│   ├── /scan 경로 [-r]     스캔 + AI 분류 미리보기
│   ├── /run                분류안 실행
│   └── /undo               되돌리기
│
├── 분석 (장기 근속자용) ────
│   ├── /dup 경로           중복 파일 탐지
│   ├── /ver 경로           버전 체인 분석
│   ├── /size 경로          용량 TOP + 통계
│   ├── /old 경로           연도별 아카이브 제안
│   ├── /find 키워드        파일 검색
│   └── /report 경로        종합 리포트
│
├── 설정 ─────────────────────
│   ├── /rule [패턴 폴더]   커스텀 규칙
│   └── /delrule 패턴       규칙 삭제
│
├── 클라우드 ─────────────────
│   └── /gdrive 폴더ID     드라이브 정리
│
├── 기록 ─────────────────────
│   └── /history            정리 이력
│
└── 안내 ─────────────────────
    ├── /start              빠른 시작
    └── /help               상세 가이드
```

---

## 9. 멀티 기기 운영 구조

```
텔레그램 (사용자 1명)
├── @home_file_bot 채팅방
│   ↕ (Polling)
│   집 PC — bot.py [DEVICE_NAME=집PC]
│   → 응답: [집PC] 스캔 완료...
│
└── @work_file_bot 채팅방
    ↕ (Polling)
    회사 PC — bot.py [DEVICE_NAME=회사PC]
    → 응답: [회사PC] 스캔 완료...
```

각 PC에 같은 코드, `.env`만 다르게.
서버/DB/네트워크 설정 없이 독립 실행.

---

## 10. 파일 구조

```
telegram-file-organizer/
├── bot.py              # 텔레그램 핸들러 + 명령어 라우팅
├── scanner.py          # 로컬/클라우드 파일 스캔
├── classifier.py       # GPT 기반 AI 분류
├── organizer.py        # 파일 이동 + Undo + 이력
├── analyzer.py         # 중복/버전/용량/아카이브 분석
├── rules.py            # 커스텀 규칙 관리
├── config.py           # 환경변수 + 설정
├── cloud/
│   ├── __init__.py
│   └── gdrive.py       # Google Drive API
├── history.json        # 정리 이력 (자동 생성)
├── rules.json          # 커스텀 규칙 (자동 생성)
├── requirements.txt    # Python 의존성
├── .env                # API 키 + 기기명 (git 제외)
├── .env.example        # 환경변수 템플릿
├── .gitignore
├── README.md           # 사용 가이드
└── ARCHITECTURE.md     # 이 문서
```

---

## 11. 설계 원칙

| 원칙 | 적용 |
|------|------|
| **확인 후 실행** | 파일 이동 전 반드시 미리보기. 자동화의 신뢰는 예측 가능성에서 온다 |
| **실패 안전** | 모든 이동을 기록하고 Undo 가능. 시스템 파일은 자동 스킵 |
| **점진적 복잡도** | 경로만 보내면 동작 → 분석 명령어 → 커스텀 규칙 → 드라이브 |
| **기기 독립** | 서버 없이 각 PC에서 독립 실행. .env만 다르면 됨 |
| **비용 효율** | gpt-4o-mini로 충분. DB 대신 JSON. 인프라 비용 0 |
| **한국어 우선** | 폴더명, 버전 패턴, 메시지 모두 한국어 기반 설계 |
