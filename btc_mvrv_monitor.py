#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC MVRV 指标监控推送脚本
用于 GitHub Actions 每天早上自动获取 BTC MVRV 和 MVRV-Z 指标并推送飞书

作者：AI 助手
功能:
    1. 优先从 Newhedge.io 获取 BTC MVRV 和 MVRV-Z 指标
    2. 如果获取失败，从其他数据源（woobull、lookintobitcoin）获取
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
# Tavily 搜索 API 配置
# 请访问 https://tavily.com 获取 API Key
TAVILY_API_URL = "https://api.tavily.com/search"

# 推送标题
PUSH_TITLE = "📊 BTC MVRV 指标推送"

# ==================== 核心功能函数 ====================

def call_tavily_search(api_key, query, include_answer=True):
    """
    调用 Tavily 搜索 API 获取相关信息

    参数:
        api_key: Tavily API 密钥
        query: 搜索查询词
        include_answer: 是否包含 AI 摘要答案

    返回:
        dict: API 返回的搜索结果
    """
    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": include_answer
    }

    try:
        response = requests.post(
            TAVILY_API_URL,
            headers=headers,
            json=data,
            timeout=30
        )

        print(f"🔍 HTTP 状态码：{response.status_code}")

        if response.status_code != 200:
            print(f"🔍 响应内容：{response.text[:500]}")
            return {"error": f"API 请求失败 (HTTP {response.status_code})：{response.text[:200]}"}

        result = response.json()
        return result

    except requests.exceptions.Timeout:
        return {"error": "API 请求超时"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API 请求失败：{str(e)}"}
    except json.JSONDecodeError:
        return {"error": "API 响应解析失败"}
    except Exception as e:
        return {"error": f"未知错误：{str(e)}"}


def extract_mvrv_from_text(text, source_domain="unknown"):
    """
    从文本中提取 MVRV 和 MVRV-Z 数值

    参数:
        text: 待解析的文本
        source_domain: 数据来源域名

    返回:
        dict: 包含 mvrv, mvrv_z, source, details 的字典
    """
    result = {
        "mvrv": None,
        "mvrv_z": None,
        "source": source_domain,
        "details": "",
        "success": False
    }

    print(f"📥 待解析文本：{text[:500]}")

    # 扩展匹配模式，增加更多格式
    mvrv_patterns = [
        r"MVRV[:\s=]*(?:为|是)?\s*([0-9.]+)",
        r"MVRV\s+Ratio[:\s=]*([0-9.]+)",
        r"MVRV\s+value[:\s=]*([0-9.]+)",
        r"MVRV\s+is\s+([0-9.]+)",
        r"MVRV\s*=\s*([0-9.]+)",
        r"Market\s*Value\s*to\s*Realized\s*Value[:\s=]*([0-9.]+)",
        r"current\s+MVRV\s+(?:is\s+)?([0-9.]+)",
        r"MVRV\s+(?:ratio\s+)?(?:currently\s+)?(?:at\s+)?([0-9.]+)",
        r"MVRV.*?([0-9]+\.?[0-9]*)",
        r"MVRV\s+(?:at\s+)?([0-9]\.[0-9]+)",
        r"ratio\s+(?:is\s+)?([0-9]\.[0-9]+)",
    ]

    mvrv_z_patterns = [
        r"MVRV[-_\s]?Z[:\s=]*(?:为|是)?\s*([0-9.-]+)",
        r"MVRV[-_\s]?Z\s*Score[:\s=]*([0-9.-]+)",
        r"MVRV-Z\s*Score[:\s=]*([0-9.-]+)",
        r"MVRV-Z[:\s=]*([0-9.-]+)",
        r"MVRV\s+Z[-\s]?Score[:\s=]*([0-9.-]+)",
        r"MVRV\s+Z\s+is\s+([0-9.-]+)",
        r"MVRV-Z\s+is\s+([0-9.-]+)",
        r"Z[-\s]?Score[:\s=]*([0-9.-]+)",
        r"Z-Score[:\s=]*([0-9.-]+)",
        r"Z\s+Score[:\s=]*([0-9.-]+)",
    ]

    # 尝试匹配 MVRV
    for pattern in mvrv_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                mvrv_value = float(match.group(1))
                # 放宽范围：MVRV 值通常在 0.1 到 10 之间
                if 0.1 <= mvrv_value <= 10:
                    result["mvrv"] = mvrv_value
                    print(f"✅ 找到 MVRV: {mvrv_value}")
                    break
            except ValueError:
                pass

    # 尝试匹配 MVRV-Z
    for pattern in mvrv_z_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                mvrv_z_value = float(match.group(1))
                # 放宽范围：MVRV-Z 值通常在 -5 到 5 之间
                if -5 <= mvrv_z_value <= 5:
                    result["mvrv_z"] = mvrv_z_value
                    print(f"✅ 找到 MVRV-Z: {mvrv_z_value}")
                    break
            except ValueError:
                pass

    result["success"] = result["mvrv"] is not None and result["mvrv_z"] is not None

    if result["success"]:
        result["details"] = f"MVRV: {result['mvrv']}\nMVRV-Z: {result['mvrv_z']}"
    else:
        result["details"] = f"未能从 {source_domain} 提取到精确数值"

    return result


def extract_mvrv_from_search_results(search_results):
    """
    从搜索结果中提取 MVRV 和 MVRV-Z 数值

    参数:
        search_results: Tavily 搜索返回的结果

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

    all_text = ""
    sources = []

    # 从 answer 中提取
    if "answer" in search_results and search_results["answer"]:
        all_text += search_results["answer"] + "\n"
        print(f"📥 Tavily 答案：{search_results['answer'][:300]}")

    # 从 results 中提取
    if "results" in search_results:
        for item in search_results["results"]:
            all_text += item.get("content", "") + "\n"
            url = item.get("url", "")
            if url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    if domain and domain not in sources:
                        sources.append(domain)
                except:
                    pass

    if sources:
        result["source"] = " | ".join(sources[:3])

    return extract_mvrv_from_text(all_text, result["source"])


def search_newhedge(api_key):
    """
    优先从 Newhedge.io 获取数据

    参数:
        api_key: Tavily API 密钥

    返回:
        dict: MVRV 数据
    """
    print("\n🔍 优先从 Newhedge.io 搜索...")

    # 使用更精确的搜索词，直接搜索数值
    query = "site:newhedge.io Bitcoin MVRV Z-Score value 0."
    search_results = call_tavily_search(api_key, query, include_answer=True)

    if "error" in search_results:
        print(f"❌ Newhedge 搜索失败：{search_results['error']}")
        return None

    # 检查是否有来自 newhedge.io 的结果
    if "results" in search_results:
        newhedge_results = []
        other_results = []

        for item in search_results["results"]:
            url = item.get("url", "").lower()
            if "newhedge" in url:
                newhedge_results.append(item)
            else:
                other_results.append(item)

        # 优先处理 Newhedge 结果
        if newhedge_results:
            print(f"✅ 找到 {len(newhedge_results)} 条来自 Newhedge 的结果")
            combined_text = "\n".join([item.get("content", "") for item in newhedge_results])
            mvrv_data = extract_mvrv_from_text(combined_text, "newhedge.io")
            if mvrv_data["success"]:
                return mvrv_data

        # 如果 Newhedge 没有精确数值，使用其他结果
        if other_results:
            print(f"⚠️ Newhedge 未找到精确数值，使用其他数据源")
            combined_text = "\n".join([item.get("content", "") for item in other_results])
            source_domains = []
            for item in search_results["results"]:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(item.get("url", "")).netloc
                    if domain and domain not in source_domains:
                        source_domains.append(domain)
                except:
                    pass
            source = " | ".join(source_domains[:3]) if source_domains else "其他来源"
            return extract_mvrv_from_text(combined_text, source)

    return None


def search_all_sources(api_key):
    """
    从所有可用来源搜索数据

    参数:
        api_key: Tavily API 密钥

    返回:
        dict: MVRV 数据
    """
    print("\n🔍 从所有来源搜索...")

    # 使用更精确的搜索词，直接搜索数值
    query = "Bitcoin MVRV Z-Score 0. Glassnode Newhedge value"
    search_results = call_tavily_search(api_key, query, include_answer=True)

    if "error" in search_results:
        return {
            "mvrv": None,
            "mvrv_z": None,
            "source": "搜索失败",
            "details": f"搜索失败：{search_results['error']}",
            "success": False
        }

    return extract_mvrv_from_search_results(search_results)


def send_feishu_push(webhook_url, title, content):
    """
    通过飞书机器人发送推送

    参数:
        webhook_url: 飞书机器人 Webhook 地址
        title: 推送标题
        content: 推送内容

    返回:
        bool: 推送是否成功
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


def build_push_content(mvrv_data, mvrv, mvrv_z):
    """
    构建推送内容

    参数:
        mvrv_data: 提取的 MVRV 数据
        mvrv: 解析到的 MVRV 值
        mvrv_z: 解析到的 MVRV-Z 值

    返回:
        str: 格式化的推送内容
    """
    # 构建抄底信号判断
    buy_signal = ""
    if mvrv is not None and mvrv_z is not None:
        mvrv_ok = mvrv < 1
        mvrv_z_ok = mvrv_z < 0

        # 同时满足两个条件才建议抄底
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
  • {mvrv_data.get('source', '未知')}
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
    """
    获取当前北京时间

    返回:
        str: 格式化的时间字符串
    """
    beijing_time = datetime.utcnow() + timedelta(hours=8)
    return beijing_time.strftime("%Y-%m-%d %H:%M:%S")


def check_buy_signal(mvrv, mvrv_z):
    """
    检查是否满足抄底条件

    参数:
        mvrv: MVRV 数值
        mvrv_z: MVRV-Z 数值

    返回:
        bool: 是否满足抄底条件
    """
    return mvrv is not None and mvrv_z is not None and (mvrv < 1 or mvrv_z < 0)


def main():
    """
    主函数：程序的入口点

    流程:
    1. 获取环境变量中的 API Key
    2. 优先从 Newhedge 获取数据
    3. 如果失败，从其他来源获取
    4. 发送飞书推送
    """
    print("=" * 50)
    print("🚀 BTC MVRV 指标监控推送程序启动")
    print("=" * 50)

    print("\n📋 第一步：获取配置...")

    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    feishu_webhook = os.environ.get("FEISHU_WEBHOOK")

    if not tavily_api_key:
        print("❌ 错误：未设置 TAVILY_API_KEY 环境变量")
        print("请前往 https://tavily.com 注册获取 API Key")
        sys.exit(1)

    if not feishu_webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK 环境变量")
        print("请在 GitHub Secrets 中配置 FEISHU_WEBHOOK")
        sys.exit(1)

    print(f"✅ Tavily API Key 已获取 (长度：{len(tavily_api_key)})")
    print(f"✅ 飞书 Webhook 已获取 (长度：{len(feishu_webhook)})")

    print("\n📡 第二步：获取 MVRV 数据...")

    # 优先从 Newhedge 获取
    mvrv_data = search_newhedge(tavily_api_key)

    # 如果 Newhedge 没有成功获取，使用其他来源
    if not mvrv_data or not mvrv_data.get("success"):
        mvrv_data = search_all_sources(tavily_api_key)

    mvrv = mvrv_data.get("mvrv")
    mvrv_z = mvrv_data.get("mvrv_z")

    if mvrv_data.get("success"):
        print(f"\n✅ MVRV 解析成功：{mvrv}")
        print(f"✅ MVRV-Z 解析成功：{mvrv_z}")
        print(f"✅ 数据来源：{mvrv_data.get('source', '未知')}")
    else:
        print(f"\n⚠️ 数据解析失败")
        print(f"📋 详情：{mvrv_data.get('details', '')}")

    print("\n📱 第三步：发送飞书推送...")

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
