#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC MVRV 指标监控推送脚本
使用 OpenRouter API 获取比特币 MVRV 和 MVRV-Z 指标

作者：AI 助手
功能:
    1. 使用 OpenRouter API 搜索获取 BTC MVRV 和 MVRV-Z 指标
    2. 数据来源：Newhedge.io、Glassnode 等
    3. 当 MVRV < 1 且 MVRV-Z < 0 时提醒抄底
    4. 通过飞书机器人推送通知
"""

import os
import requests
import json
import re
import sys
from datetime import datetime, timedelta

# ==================== 配置区域 ====================
# OpenRouter API 配置
# 请访问 https://openrouter.ai 获取 API Key
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"  # 使用免费模型

# 推送标题
PUSH_TITLE = "📊 BTC MVRV 指标推送"

# ==================== 核心功能函数 ====================

def call_openrouter_search(api_key, query):
    """
    调用 OpenRouter API 获取相关信息

    参数:
        api_key: OpenRouter API 密钥
        query: 搜索查询词

    返回:
        dict: API 返回的结果
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/",
        "X-Title": "BTC MVRV Monitor"
    }

    # 构建提示词，让 AI 搜索并返回结构化数据
    prompt = f"""请搜索并提供以下比特币指标的最新数据：

查询：{query}

请返回：
1. MVRV Ratio 的具体数值
2. MVRV Z-Score 的具体数值
3. 数据来源（网站名称）
4. 数据日期

格式示例：
MVRV: 0.85
MVRV-Z: -0.5
来源：Newhedge.io
日期：2026-03-21

如果找不到精确数值，请说明原因。"""

    data = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.3
    }

    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=data,
            timeout=60
        )

        print(f"🔍 HTTP 状态码：{response.status_code}")

        if response.status_code != 200:
            print(f"🔍 响应内容：{response.text[:500]}")
            return {"error": f"API 请求失败 (HTTP {response.status_code})：{response.text[:200]}"}

        result = response.json()
        print(f"📥 API 响应：{json.dumps(result, ensure_ascii=False)[:1000]}")

        return result

    except requests.exceptions.Timeout:
        return {"error": "API 请求超时"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API 请求失败：{str(e)}"}
    except json.JSONDecodeError:
        return {"error": "API 响应解析失败"}
    except Exception as e:
        return {"error": f"未知错误：{str(e)}"}


def extract_mvrv_from_response(response_data):
    """
    从 API 响应中提取 MVRV 和 MVRV-Z 数值

    参数:
        response_data: API 返回的数据

    返回:
        dict: 包含 mvrv, mvrv_z, source, details 的字典
    """
    result = {
        "mvrv": None,
        "mvrv_z": None,
        "source": "未知来源",
        "details": "",
        "success": False
    }

    # 提取文本内容
    all_text = ""

    if isinstance(response_data, dict):
        if "choices" in response_data and len(response_data["choices"]) > 0:
            content = response_data["choices"][0].get("message", {})
            all_text = content.get("content", "")

    print(f"📥 待解析文本：{all_text[:800]}")

    # 使用正则表达式匹配 MVRV 和 MVRV-Z
    mvrv_patterns = [
        r"MVRV[:\s=]*(?:为 | 是)?\s*([0-9.]+)",
        r"MVRV\s+Ratio[:\s=]*([0-9.]+)",
        r"MVRV\s+value[:\s=]*([0-9.]+)",
        r"MVRV\s+is\s+([0-9.]+)",
        r"MVRV\s*=\s*([0-9.]+)",
        r"MVRV:\s*([0-9.]+)",
        r"ratio[:\s=]*([0-9.]+)",
    ]

    mvrv_z_patterns = [
        r"MVRV[-_\s]?Z[:\s=]*(?:为 | 是)?\s*([0-9.-]+)",
        r"MVRV[-_\s]?Z\s*Score[:\s=]*([0-9.-]+)",
        r"MVRV-Z\s*Score[:\s=]*([0-9.-]+)",
        r"MVRV-Z[:\s=]*([0-9.-]+)",
        r"MVRV\s+Z[-\s]?Score[:\s=]*([0-9.-]+)",
        r"MVRV\s+Z\s+is\s+([0-9.-]+)",
        r"MVRV-Z\s+is\s+([0-9.-]+)",
        r"Z[-\s]?Score[:\s=]*([0-9.-]+)",
        r"Z-Score[:\s=]*([0-9.-]+)",
    ]

    # 尝试匹配 MVRV
    for pattern in mvrv_patterns:
        match = re.search(pattern, all_text, re.IGNORECASE)
        if match:
            try:
                mvrv_value = float(match.group(1))
                if 0.1 <= mvrv_value <= 10:
                    result["mvrv"] = mvrv_value
                    print(f"✅ 找到 MVRV: {mvrv_value}")
                    break
            except ValueError:
                pass

    # 尝试匹配 MVRV-Z
    for pattern in mvrv_z_patterns:
        match = re.search(pattern, all_text, re.IGNORECASE)
        if match:
            try:
                mvrv_z_value = float(match.group(1))
                if -5 <= mvrv_z_value <= 5:
                    result["mvrv_z"] = mvrv_z_value
                    print(f"✅ 找到 MVRV-Z: {mvrv_z_value}")
                    break
            except ValueError:
                pass

    # 提取数据来源
    source_pattern = r"来源 [:\s=]*([^\n]+)"
    source_match = re.search(source_pattern, all_text, re.IGNORECASE)
    if source_match:
        result["source"] = source_match.group(1).strip()

    result["success"] = result["mvrv"] is not None and result["mvrv_z"] is not None

    if result["success"]:
        result["details"] = f"MVRV: {result['mvrv']}\nMVRV-Z: {result['mvrv_z']}"
    else:
        result["details"] = f"未能提取到精确数值\n\n原始响应：{all_text[:300]}"

    return result


def send_feishu_push(webhook_url, title, content):
    """
    通过飞书机器人发送推送
    """
    data = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                }
            ]
        }
    }

    try:
        response = requests.post(
            webhook_url,
            json=data,
            timeout=10
        )

        result = response.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            return True
        else:
            print(f"❌ 飞书推送失败：{result}")
            return False

    except Exception as e:
        print(f"❌ 飞书请求失败：{str(e)}")
        return False


def build_search_query():
    """
    构建搜索查询词
    """
    beijing_time = datetime.utcnow() + timedelta(hours=8)
    current_date = beijing_time.strftime("%Y-%m-%d")

    query = f"Bitcoin MVRV Ratio MVRV Z-Score current value today {current_date} Newhedge Glassnode"
    return query


def build_push_content(mvrv_data, mvrv, mvrv_z):
    """
    构建推送内容
    """
    buy_signal = ""
    if mvrv is not None and mvrv_z is not None:
        mvrv_ok = mvrv < 1
        mvrv_z_ok = mvrv_z < 0

        if mvrv_ok and mvrv_z_ok:
            buy_signal = f"""
🎯 ⚠️ 【强烈抄底信号】⚠️ 🎯
━━━━━━━━━━━━━━━━━━
✅ MVRV = {mvrv} < 1 (低估)
✅ MVRV-Z = {mvrv_z} < 0 (低估)
━━━━━━━━━━━━━━━━━━
📌 结论：两个指标都满足抄底条件！
💰 建议：可以考虑分批建仓
"""
        elif mvrv_ok:
            buy_signal = f"""
🎯 【部分抄底信号】
━━━━━━━━━━━━━━━━━━
✅ MVRV = {mvrv} < 1 (低估)
❌ MVRV-Z = {mvrv_z} >= 0 (正常)
━━━━━━━━━━━━━━━━━━
📌 结论：仅 MVRV 满足条件，建议观望
"""
        elif mvrv_z_ok:
            buy_signal = f"""
🎯 【部分抄底信号】
━━━━━━━━━━━━━━━━━━
❌ MVRV = {mvrv} >= 1 (正常)
✅ MVRV-Z = {mvrv_z} < 0 (低估)
━━━━━━━━━━━━━━━━━━
📌 结论：仅 MVRV-Z 满足条件，建议观望
"""
        else:
            buy_signal = f"""
💰 【暂不建议抄底】
━━━━━━━━━━━━━━━━━━
❌ MVRV = {mvrv} >= 1 (正常)
❌ MVRV-Z = {mvrv_z} >= 0 (正常)
━━━━━━━━━━━━━━━━━━
📌 结论：未达到抄底条件
"""

    content = f"""📈 BTC MVRV 指标早报

━━━━━━━━━━━━━━━━━━
🔍 数据来源:
  • {mvrv_data.get('source', 'OpenRouter 搜索')}
━━━━━━━━━━━━━━━━━━

{mvrv_data.get('details', '数据获取中...')}

━━━━━━━━━━━━━━━━━━
💡 抄底条件:
  • MVRV < 1
  • MVRV-Z < 0
━━━━━━━━━━━━━━━━━━
{buy_signal}
⏰ 更新时间：{get_current_time()}"""

    return content


def get_current_time():
    """获取当前北京时间"""
    beijing_time = datetime.utcnow() + timedelta(hours=8)
    return beijing_time.strftime("%Y-%m-%d %H:%M:%S")


def check_buy_signal(mvrv, mvrv_z):
    """检查是否满足抄底条件"""
    return mvrv is not None and mvrv_z is not None and (mvrv < 1 or mvrv_z < 0)


def main():
    """主函数"""
    print("=" * 50)
    print("🚀 BTC MVRV 指标监控推送程序启动 (OpenRouter)")
    print("=" * 50)

    print("\n📋 第一步：获取配置...")

    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
    feishu_webhook = os.environ.get("FEISHU_WEBHOOK")

    if not openrouter_api_key:
        print("❌ 错误：未设置 OPENROUTER_API_KEY 环境变量")
        print("请前往 https://openrouter.ai 获取 API Key")
        sys.exit(1)

    if not feishu_webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK 环境变量")
        sys.exit(1)

    print(f"✅ OpenRouter API Key 已获取 (长度：{len(openrouter_api_key)})")
    print(f"✅ 飞书 Webhook 已获取 (长度：{len(feishu_webhook)})")

    print("\n📡 第二步：调用 OpenRouter API 获取数据...")

    query = build_search_query()
    print(f"🔍 搜索查询词：{query}")

    openrouter_response = call_openrouter_search(openrouter_api_key, query)

    print("\n🔧 第三步：解析 MVRV 数据...")

    mvrv_data = extract_mvrv_from_response(openrouter_response)

    mvrv = mvrv_data.get("mvrv")
    mvrv_z = mvrv_data.get("mvrv_z")

    if mvrv_data.get("success"):
        print(f"\n✅ MVRV 解析成功：{mvrv}")
        print(f"✅ MVRV-Z 解析成功：{mvrv_z}")
        print(f"✅ 数据来源：{mvrv_data.get('source', '未知')}")
    else:
        print(f"\n⚠️ 数据解析失败")
        print(f"📋 详情：{mvrv_data.get('details', '')}")

    print("\n📱 第四步：发送飞书推送...")

    push_content = build_push_content(mvrv_data, mvrv, mvrv_z)

    push_success = send_feishu_push(feishu_webhook, PUSH_TITLE, push_content)

    if push_success:
        print("✅ 飞书推送发送成功!")

        if check_buy_signal(mvrv, mvrv_z):
            print("\n" + "=" * 50)
            print("⚠️  ⚠️  ⚠️  重要提醒!!!  ⚠️  ⚠️  ⚠️")
            print("=" * 50)
            print(f"MVRV = {mvrv} {'< 1 ⚠️ 满足抄底条件!' if mvrv and mvrv < 1 else ''}")
            print(f"MVRV-Z = {mvrv_z} {'< 0 ⚠️ 满足抄底条件!' if mvrv_z and mvrv_z < 0 else ''}")
            print("=" * 50)
    else:
        print("❌ 飞书推送发送失败")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("✅ 程序执行完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
