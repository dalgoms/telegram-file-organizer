import json
from openai import OpenAI
from scanner import FileInfo
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

SYSTEM_PROMPT = """당신은 파일 정리 전문가입니다.
사용자가 보내는 파일 목록을 분석하여 최적의 폴더 구조로 분류해주세요.

규칙:
1. 폴더명은 한글로, 2단계까지만 (예: "문서/보고서", "이미지/스크린샷")
2. 파일의 이름, 확장자, 크기, 날짜를 종합적으로 판단
3. 비슷한 성격의 파일은 같은 폴더로
4. 이미 폴더 안에 있는 파일은 현재 위치를 존중
5. 폴더 이름은 직관적이고 실무적으로

반드시 아래 JSON 형식으로만 응답:
{
  "folders": {
    "폴더경로": ["파일명1", "파일명2"],
    ...
  },
  "reasoning": "분류 근거 한 줄 요약"
}

예시 카테고리:
- 문서/보고서, 문서/회의록, 문서/기획
- 이미지/사진, 이미지/스크린샷, 이미지/디자인
- 영상/촬영, 영상/편집
- 개발/코드, 개발/설정
- 데이터/스프레드시트, 데이터/CSV
- 기타
"""


def build_file_list_prompt(files: list[FileInfo]) -> str:
    """파일 목록을 GPT 프롬프트용 텍스트로 변환한다."""
    lines = ["파일 목록:"]
    for i, f in enumerate(files, 1):
        if f.is_dir:
            lines.append(f"{i}. [폴더] {f.name} ({f.modified_str})")
        else:
            lines.append(f"{i}. {f.name} ({f.size_human}, {f.modified_str})")
    return "\n".join(lines)


def classify_files(files: list[FileInfo], custom_instruction: str = "") -> dict | None:
    """GPT를 사용하여 파일을 분류한다. 결과는 {folders: {경로: [파일명]}, reasoning: str}"""
    if not client:
        return None

    file_only = [f for f in files if not f.is_dir]
    if not file_only:
        return None

    prompt = build_file_list_prompt(file_only)
    if custom_instruction:
        prompt += f"\n\n추가 지시: {custom_instruction}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        content = response.choices[0].message.content.strip()

        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        return json.loads(content)

    except (json.JSONDecodeError, Exception) as e:
        return {"error": str(e)}


def format_classification(result: dict, root_path: str) -> str:
    """분류 결과를 텔레그램 미리보기 메시지로 포맷한다."""
    if not result:
        return "[분류 실패] OpenAI API 키가 설정되지 않았습니다."

    if "error" in result:
        return f"[분류 실패] {result['error']}"

    folders = result.get("folders", {})
    reasoning = result.get("reasoning", "")

    lines = [f"[AI 분류 결과] {root_path}", ""]

    total = 0
    for folder, file_list in folders.items():
        lines.append(f"/{folder}/")
        for fname in file_list:
            lines.append(f"  -> {fname}")
            total += 1
        lines.append("")

    lines.append(f"총 {total}개 파일 -> {len(folders)}개 폴더로 정리")
    if reasoning:
        lines.append(f"\n분류 근거: {reasoning}")

    lines.append("\n이대로 정리할까요? /run 으로 실행")

    return "\n".join(lines)
