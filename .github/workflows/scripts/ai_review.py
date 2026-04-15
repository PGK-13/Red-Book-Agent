#!/usr/bin/env python3
"""AI Code Review Script - 使用 Claude API 检测代码中的 Bug。"""

import anthropic
import json
import os
import sys


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", None)

    if not api_key:
        print("ANTHROPIC_API_KEY not set, skipping AI review")
        return

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**client_kwargs)

    # 读取 diff 内容
    try:
        with open("/tmp/pr_diff.txt", "r") as f:
            diff_content = f.read()
    except FileNotFoundError:
        print("No diff file found, skipping AI review")
        return

    if not diff_content:
        print("Empty diff, skipping AI review")
        return

    # 截取 diff（避免超出上下文限制）
    if len(diff_content) > 15000:
        diff_content = diff_content[:15000] + "\n... (truncated)"

    prompt = f"""你是一个代码审查助手。请分析以下代码变更，找出潜在的 bug、安全问题、逻辑错误或违反最佳实践的地方。

请只返回 JSON 格式的审查结果，不要返回其他内容：
{{
  "bugs": [
    {{
      "file": "文件路径",
      "line": "行号（如适用）",
      "severity": "high|medium|low",
      "description": "问题描述",
      "suggestion": "修复建议"
    }}
  ],
  "security_issues": [
    {{
      "file": "文件路径",
      "description": "安全问题描述"
    }}
  ],
  "summary": "总体评价（1-2句话）"
}}

代码变更（diff）：
{diff_content}

请仔细检查：
1. 空指针/None 检查是否完整
2. 异常处理是否完善
3. 并发安全（async/await 使用是否正确）
4. 资源泄漏（数据库连接、文件句柄等）
5. 业务逻辑错误
6. 敏感信息泄露风险
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        response_text = message.content[0].text

        try:
            result = json.loads(response_text)
            bugs = result.get("bugs", [])
            security_issues = result.get("security_issues", [])
            summary = result.get("summary", "")

            print("=== AI 代码审查结果 ===")
            print()
            print(summary)
            print()

            if bugs:
                print("发现 Bug:")
                for i, bug in enumerate(bugs, 1):
                    print(f"  {i}. [{bug['severity'].upper()}] {bug['file']}")
                    if bug.get('line'):
                        print(f"     行 {bug['line']}: {bug['description']}")
                    else:
                        print(f"     {bug['description']}")
                    if bug.get('suggestion'):
                        print(f"     建议: {bug['suggestion']}")
                    print()

            if security_issues:
                print("安全问题:")
                for i, issue in enumerate(security_issues, 1):
                    print(f"  {i}. {issue['file']}: {issue['description']}")
                print()

            high_severity_bugs = [b for b in bugs if b.get('severity') == 'high']
            if high_severity_bugs:
                print("❌ 发现高严重性问题，建议修复后再合并")
                sys.exit(1)
            else:
                print("✅ AI 审查未发现高严重性问题")

        except json.JSONDecodeError:
            print("AI 响应解析失败:")
            print(response_text)

    except Exception as e:
        print(f"⚠️ AI 审查请求失败: {e}")
        print("跳过 AI 审查，继续其他检查")


if __name__ == "__main__":
    main()
