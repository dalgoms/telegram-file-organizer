# Telegram File Organizer Bot

텔레그램에서 폴더 경로를 보내면 AI가 파일을 분석하여 자동으로 정리해주는 봇.

## 핵심 기능

- **AI 스마트 분류** — GPT가 파일명, 확장자, 크기, 날짜를 분석하여 최적의 폴더 구조 제안
- **미리보기 → 확인 → 실행** — 정리안을 먼저 보여주고, 확인 후 실행
- **Undo** — 언제든 마지막 정리를 되돌릴 수 있음
- **커스텀 규칙** — 자주 쓰는 정리 패턴을 규칙으로 저장
- **Google Drive 지원** — 로컬 폴더와 구글 드라이브 모두 정리 가능

### 장기 근속자를 위한 분석 기능

- **중복 파일 탐지** (`/dup`) — 같은 파일이 여러 폴더에 흩어져 있는지 찾아 낭비 용량 표시
- **버전 체인 분석** (`/ver`) — "보고서_최종", "보고서_최종_수정", "보고서_진짜최종" 같은 파일을 그룹핑
- **용량 분석** (`/size`) — 용량 TOP 파일 + 확장자별 용량 통계
- **아카이브 제안** (`/old`) — 올해가 아닌 오래된 파일을 연도별로 정리 제안
- **파일 검색** (`/find`) — "보고서", "KOBA" 등 키워드로 파일 검색
- **종합 리포트** (`/report`) — 위 분석을 한 번에 실행하여 폴더 상태를 진단

## 명령어

| 명령어 | 기능 |
|--------|------|
| `/scan 경로` | 폴더 스캔 + AI 분류 미리보기 |
| `/scan 경로 -r` | 하위 폴더 포함 스캔 |
| `/run` | 미리보기 확인 후 실제 정리 |
| `/undo` | 마지막 정리 되돌리기 |
| `/history` | 정리 이력 보기 |
| `/rule` | 커스텀 규칙 목록 |
| `/rule 패턴 폴더` | 규칙 추가 |
| `/delrule 패턴` | 규칙 삭제 |
| `/gdrive 폴더ID` | 구글 드라이브 폴더 정리 |
| `/dup 경로` | 중복 파일 탐지 |
| `/ver 경로` | 버전 체인 분석 (최종/수정/v1 등) |
| `/size 경로` | 용량 TOP + 확장자별 통계 |
| `/old 경로` | 연도별 아카이브 제안 |
| `/find 키워드` | 파일명 검색 |
| `/report 경로` | 종합 리포트 (위 분석 전부) |

## 사용 예시

```
# 다운로드 폴더 정리
/scan D:\Downloads

# 바탕화면 정리 (하위 폴더 포함)
/scan C:\Users\사용자\Desktop -r

# 경로만 보내도 동작
D:\프로젝트\마케팅자료

# 커스텀 규칙: PPT는 항상 문서/프레젠테이션으로
/rule *.pptx 문서/프레젠테이션

# 구글 드라이브 폴더 정리
/gdrive 1abc2def3ghi4jkl
```

## AI 분류 예시

입력:
```
2026_Q1_마케팅보고서_v3.pptx
IMG_20260318_142355.jpg
회의록_팀블로_0312.docx
budget_2026.xlsx
screenshot_234.png
```

AI 분류 결과:
```
/문서/보고서/
  -> 2026_Q1_마케팅보고서_v3.pptx
/문서/회의록/
  -> 회의록_팀블로_0312.docx
/문서/재무/
  -> budget_2026.xlsx
/이미지/사진/
  -> IMG_20260318_142355.jpg
/이미지/스크린샷/
  -> screenshot_234.png
```

## 설치

### 1. 의존성 설치

```bash
cd telegram-file-organizer
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일을 만들고 값을 채워주세요:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```

### 3. 텔레그램 봇 토큰 발급

1. Telegram에서 @BotFather 검색
2. `/newbot` 입력 → 봇 이름과 username 설정
3. 발급된 토큰을 `.env`에 입력

### 4. 실행

```bash
python bot.py
```

### 5. Google Drive 연동 (선택)

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Drive API 활성화
3. OAuth 2.0 클라이언트 ID 생성 → `credentials.json` 다운로드
4. 프로젝트 루트에 `credentials.json` 배치
5. 첫 `/gdrive` 실행 시 브라우저에서 인증

## 안전장치

- 정리 전 항상 미리보기를 보여줌
- 모든 이동 기록을 `history.json`에 저장
- `/undo`로 마지막 정리를 언제든 되돌릴 수 있음
- 시스템 파일(`.git`, `node_modules`, `.env` 등) 자동 스킵
- 동일 파일명 충돌 시 자동으로 번호 부여

## 프로젝트 구조

```
telegram-file-organizer/
├── bot.py              # 텔레그램 핸들러
├── scanner.py          # 로컬/클라우드 파일 스캔
├── classifier.py       # GPT 기반 AI 분류
├── organizer.py        # 파일 이동 + Undo + 이력
├── analyzer.py         # 중복/버전/용량/아카이브 분석
├── rules.py            # 커스텀 규칙 관리
├── config.py           # 설정
├── cloud/
│   └── gdrive.py       # Google Drive API
├── requirements.txt
├── .env.example
└── README.md
```

## 기술 스택

- Python 3.12+
- python-telegram-bot — 텔레그램 봇 인터페이스
- OpenAI API (gpt-4o-mini) — AI 파일 분류
- Google Drive API — 클라우드 파일 관리
- pathlib / shutil — 로컬 파일 조작
