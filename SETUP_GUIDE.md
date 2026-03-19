# Telegram File Organizer Bot — 설치 가이드

> 누구나 자기 PC에서 직접 실행할 수 있는 AI 파일 정리 봇
> 예상 소요시간: 10~15분

---

## 비용 안내

| 항목 | 비용 |
|------|------|
| 텔레그램 봇 | 무료 |
| 코드 (이 레포) | 무료 |
| Python | 무료 |
| OpenAI API | 종량제 (파일 분류 1회당 약 10~50원) |
| Google Drive 연동 | 무료 (선택사항) |

OpenAI 신규 가입 시 $5 무료 크레딧이 제공됩니다.
파일 분류 1회 = 약 $0.01~0.03이므로 무료 크레딧으로 수백 회 사용 가능합니다.

---

## 준비물

- Windows / Mac / Linux PC
- Python 3.10 이상
- 텔레그램 계정
- OpenAI 계정

---

## Step 1. Python 설치 확인

터미널(명령 프롬프트)에서 확인:

```bash
python --version
```

`Python 3.10` 이상이 나오면 OK.

없다면:
- **Windows**: https://www.python.org/downloads/ 에서 다운로드
  - 설치 시 "Add Python to PATH" 반드시 체크
- **Mac**: `brew install python`

---

## Step 2. 코드 다운로드

### 방법 A: Git 사용 (추천)

```bash
git clone https://github.com/dalgoms/telegram-file-organizer.git
cd telegram-file-organizer
```

### 방법 B: 직접 다운로드

1. https://github.com/dalgoms/telegram-file-organizer 접속
2. 초록색 "Code" 버튼 → "Download ZIP"
3. 압축 해제

---

## Step 3. 패키지 설치

```bash
cd telegram-file-organizer
pip install -r requirements.txt
```

> 만약 `pip`가 안 되면 `python -m pip install -r requirements.txt` 시도

---

## Step 4. 텔레그램 봇 만들기

1. 텔레그램 앱에서 **검색창**에 `BotFather` 입력 → 들어가기
2. `/newbot` 입력
3. 봇 이름 입력 (예: `My File Organizer`)
4. 봇 username 입력 (예: `myname_file_bot`)
   - 반드시 `_bot`으로 끝나야 함
   - 다른 사람과 겹치지 않는 이름으로
5. **토큰이 나옵니다** — 복사해두세요

```
Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  ← 이것이 토큰
```

---

## Step 5. OpenAI API 키 발급

1. https://platform.openai.com 접속 → 회원가입/로그인
2. 좌측 메뉴 → **API Keys**
3. **Create new secret key** 클릭
4. 키 복사 (한 번만 보여주므로 반드시 복사)

```
sk-proj-XXXXXXXXXX...  ← 이것이 API 키
```

> 신규 가입 시 $5 무료 크레딧이 자동 지급됩니다.

---

## Step 6. 환경 변수 설정

프로젝트 폴더에서 `.env.example`을 복사하여 `.env` 파일을 만듭니다:

### Windows (명령 프롬프트)
```bash
copy .env.example .env
```

### Mac / Linux
```bash
cp .env.example .env
```

`.env` 파일을 메모장이나 편집기로 열어서 값을 채웁니다:

```
TELEGRAM_BOT_TOKEN=여기에_Step4에서_받은_토큰
OPENAI_API_KEY=여기에_Step5에서_받은_키
DEVICE_NAME=내PC
```

`DEVICE_NAME`은 자유롭게 설정하세요 (예: `집PC`, `회사PC`, `내노트북`).
봇 응답에 `[내PC]` 이런 식으로 표시됩니다.

---

## Step 7. 실행

```bash
python bot.py
```

아래 메시지가 나오면 성공:
```
File Organizer Bot 시작... [내PC]
```

---

## Step 8. 텔레그램에서 테스트

1. 텔레그램 **검색창**에서 Step 4에서 만든 봇 username 검색
2. 봇 채팅방 들어가기
3. `/start` 입력

봇이 응답하면 성공입니다!

### 사용 예시

```
/scan C:\Users\사용자이름\Downloads
```

> "사용자이름" 부분은 본인 PC의 실제 사용자명으로 바꾸세요.
> 확인 방법: 파일 탐색기에서 `C:\Users\` 폴더를 열면 보입니다.

---

## 자주 쓰는 명령어

| 명령어 | 기능 |
|--------|------|
| `/scan 경로` | 폴더 스캔 + AI 분류 미리보기 |
| `/scan 경로 -r` | 하위 폴더 포함 스캔 |
| `/run` | 미리보기 확인 후 실제 정리 |
| `/undo` | 마지막 정리 되돌리기 |
| `/dup 경로` | 중복 파일 탐지 |
| `/ver 경로` | 최종/수정/v1 같은 버전 체인 분석 |
| `/size 경로` | 용량 TOP 파일 + 확장자별 통계 |
| `/old 경로` | 연도별 아카이브 제안 |
| `/find 키워드` | 파일 검색 |
| `/report 경로` | 종합 리포트 (위 분석 전부) |
| `/rule` | 커스텀 규칙 관리 |
| `/history` | 정리 이력 |

---

## 집 + 회사 두 대에서 쓰기

각 PC에서 별도의 봇을 만들어서 운영합니다.

### 집 PC
1. BotFather에서 봇 1개 생성 (예: `@home_file_bot`)
2. `.env` 설정:
```
TELEGRAM_BOT_TOKEN=집봇_토큰
DEVICE_NAME=집PC
```

### 회사 PC
1. BotFather에서 봇 1개 더 생성 (예: `@work_file_bot`)
2. 같은 코드를 회사 PC에 복사
3. `.env` 설정:
```
TELEGRAM_BOT_TOKEN=회사봇_토큰
DEVICE_NAME=회사PC
```

텔레그램에서 각 봇 채팅방을 따로 열면, 어떤 PC의 파일인지 구분됩니다:
```
[집PC] 스캔 완료 — 파일 142개
[회사PC] 중복 파일 발견 — 23그룹
```

---

## Google Drive 연동 (선택)

클라우드 파일도 정리하고 싶다면:

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성
3. "Google Drive API" 검색 → 활성화
4. 사용자 인증 정보 → OAuth 2.0 클라이언트 ID 생성
5. `credentials.json` 다운로드 → 프로젝트 폴더에 배치
6. 봇에서 `/gdrive 폴더ID` 실행 시 브라우저에서 인증

> Google Drive 연동 없이도 로컬 파일 정리는 완벽하게 동작합니다.

---

## 안전장치 (걱정하지 마세요)

| 걱정 | 해결 |
|------|------|
| 파일이 잘못 정리되면? | `/undo` 한 번이면 원래대로 돌아와요 |
| 시스템 파일이 이동되면? | Windows, Program Files 등은 자동 차단돼요 |
| 정리 중에 PC가 꺼지면? | 매 파일 이동마다 이력을 저장해서 undo 가능해요 |
| 사용 중인 파일은? | 열려있는 파일은 자동으로 건너뛰어요 |
| 예전 스캔 결과로 실행하면? | 5분 지나면 자동 만료, 다시 스캔 안내해요 |

---

## 문제 해결

### "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다"
→ `.env` 파일이 프로젝트 폴더에 있는지 확인. `.env.example`이 아니라 `.env`여야 합니다.

### "pip 명령어를 찾을 수 없습니다"
→ Python 설치 시 "Add to PATH" 를 안 했을 수 있음. Python을 재설치하거나:
```bash
python -m pip install -r requirements.txt
```

### 봇이 응답하지 않음
→ `python bot.py`가 실행 중인지 확인. 터미널을 닫으면 봇도 꺼집니다.

### "Conflict: terminated by other getUpdates request"
→ 같은 봇이 이미 실행 중. 기존 Python 프로세스를 종료하세요:
- Windows: `작업 관리자 → Python 종료`
- Mac/Linux: `pkill python`

### 파일이 정리 안 됨
→ `/scan`은 미리보기만 보여줍니다. 실제 정리는 "정리 실행" 버튼을 누르거나 `/run`을 입력해야 합니다.

### 잘못 정리한 경우
→ `/undo`를 입력하면 마지막 정리가 되돌려집니다.

---

## 비용 관리 팁

OpenAI API 비용이 걱정된다면:

1. https://platform.openai.com/usage 에서 사용량 확인
2. Settings → Limits에서 월 한도 설정 가능 (예: $5)
3. `/scan`은 1회 호출당 약 $0.01~0.03
4. `/dup`, `/ver`, `/size`, `/old`는 OpenAI를 사용하지 않음 (무료)
5. `/report`는 `/scan` 1회 + 나머지 무료 분석 조합

→ 분석 기능(`/dup`, `/ver`, `/size`, `/old`)만 쓰면 완전 무료입니다.

---

## 프로젝트 구조

```
telegram-file-organizer/
├── bot.py              # 메인 봇 (건드릴 필요 없음)
├── scanner.py          # 파일 스캔
├── classifier.py       # AI 분류
├── organizer.py        # 파일 이동 + Undo
├── analyzer.py         # 중복/버전/용량 분석
├── rules.py            # 커스텀 규칙
├── config.py           # 설정
├── cloud/gdrive.py     # Google Drive (선택)
├── .env                # ★ 여기만 수정하면 됨
├── .env.example        # .env 템플릿
├── requirements.txt    # 패키지 목록
├── README.md           # 프로젝트 소개
└── ARCHITECTURE.md     # 기술 문서
```

> **핵심: `.env` 파일만 본인 것으로 채우면 나머지는 건드릴 필요 없습니다.**
