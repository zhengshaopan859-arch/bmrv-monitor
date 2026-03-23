#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC MVRV 指标监控推送脚本
使用 Playwright 浏览器直接访问 newhedge.io 获取数据

作者：AI 助手
功能:
    1. 使用 Playwright 浏览器访问 newhedge.io 获取 BTC MVRV 和 MVRV-Z 数据
    2. 数据来源：https://newhedge.io/bitcoin/mvrv 和 https://newhedge.io/bitcoin/mvrv-z-score
    3. 当 MVRV < 1 且 MVRV-Z < 0 时提醒抄底
    4. 通过飞书机器人推送通知
    5. 每天只推送一次（通过推送记录文件控制）
"""

import os
import json
import re
import sys
import requests
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ 错误：未安装 Playwright")
    print("请运行：pip install playwright && playwright install chromium")
    sys.exit(1)

# ==================== 配置区域 ====================
# Chrome 浏览器路径（Windows 本地环境使用，GitHub Actions 会自动使用默认 Chromium）
CHROME_PATH = r"C:\Users\zsp\AppData\Local\Google\Chrome\Application\chrome.exe"

# 数据源 URLs
MVRV_URL = "https://newhedge.io/bitcoin/mvrv"
MVRV_Z_SCORE_URL = "https://newhedge.io/bitcoin/mvrv-z-score"

# 推送标题
PUSH_TITLE = "📊 BTC MVRV 指标推送"

# 推送记录文件（用于记录今天是否已推送）
PUSH_RECORD_FILE = Path("push_record.json")

# ==================== 核心功能函数 ====================

def should_notify_today():
    """
    检查今天是否已经推送过提醒

    返回:
        True: 今天还没有推送过，需要推送
        False: 今天已经推送过，跳过
    """
    try:
        if not PUSH_RECORD_FILE.exists():
            return True

        with open(PUSH_RECORD_FILE, 'r', encoding='utf-8') as f:
            record = json.load(f)

        last_push_date = record.get("last_push_date", "")
        today = datetime.now().strftime("%Y-%m-%d")

        if last_push_date != today:
            return True

        return False

    except Exception as e:
        print(f"⚠️ 检查推送状态失败：{e}")
        return True


def mark_as_pushed():
    """标记今天已经推送过"""
    try:
        record = {
            "last_push_date": datetime.now().strftime("%Y-%m-%d"),
            "last_push_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(PUSH_RECORD_FILE, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 标记推送状态失败：{e}")


def get_mvrv_data(page):
    """
    从 newhedge.io 获取 MVRV 数据

    参数:
        page: Playwright page 对象

    返回:
        float: MVRV 值，失败返回 None
    """
    print(f"🔍 正在访问：{MVRV_URL}")

    for attempt in range(3):
        try:
            page.goto(MVRV_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            content = page.content()

            patterns = [
                r'MVRV["\s:>]+([0-9.]+)',
                r'([0-9.]+)[\s\S]*?MVRV',
                r'"mvrv"[:\s]+([0-9.]+)',
                r'"value"[:\s]+([0-9.]+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1))
                        if 0.1 <= value <= 10:
                            print(f"✅ 找到 MVRV: {value}")
                            return value
                    except ValueError:
                        continue

            page_text = page.inner_text("body")

            mvrv_match = re.search(r'MVRV[\s\n\r]*?([0-9]+\.?[0-9]*)', page_text, re.IGNORECASE)
            if mvrv_match:
                try:
                    value = float(mvrv_match.group(1))
                    if 0.1 <= value <= 10:
                        print(f"✅ 找到 MVRV: {value}")
                        return value
                except ValueError:
                    pass

            numbers = re.findall(r'\b([0-9]+\.[0-9]{2,4})\b', page_text)
            for num in numbers:
                try:
                    value = float(num)
                    if 0.1 <= value <= 10:
                        print(f"✅ 找到 MVRV: {value}")
                        return value
                except ValueError:
                    continue

            if attempt < 2:
                print(f"⚠️ 第 {attempt + 1} 次尝试未能获取 MVRV，重试中...")
                page.wait_for_timeout(3000)
                continue

            print(f"⚠️ 未能从页面提取 MVRV 数据")
            return None

        except Exception as e:
            if attempt < 2:
                print(f"⚠️ 第 {attempt + 1} 次尝试失败：{e}，重试中...")
                page.wait_for_timeout(3000)
                continue
            print(f"❌ 获取 MVRV 数据失败：{e}")
            return None

    return None


def get_mvrv_z_score_data(page):
    """
    从 newhedge.io 获取 MVRV-Z Score 数据

    参数:
        page: Playwright page 对象

    返回:
        float: MVRV-Z 值，失败返回 None
    """
    print(f"🔍 正在访问：{MVRV_Z_SCORE_URL}")

    for attempt in range(3):
        try:
            page.goto(MVRV_Z_SCORE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            content = page.content()

            patterns = [
                r'MVRV-Z["\s:>]+?([\-\d.]+)',
                r'Z-Score["\s:>]+?([\-\d.]+)',
                r'([\-\d.]+)[\s\S]*?Z-Score',
                r'"zscore"[:\s]+([\-\d.]+)',
                r'"value"[:\s]+([\-\d.]+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1))
                        if -5 <= value <= 10:
                            print(f"✅ 找到 MVRV-Z: {value}")
                            return value
                    except ValueError:
                        continue

            page_text = page.inner_text("body")

            zscore_match = re.search(r'MVRV[-\s]?Z[\s\n\r]*?([\-\d]+\.?[0-9]*)', page_text, re.IGNORECASE)
            if zscore_match:
                try:
                    value = float(zscore_match.group(1))
                    if -5 <= value <= 10:
                        print(f"✅ 找到 MVRV-Z: {value}")
                        return value
                except ValueError:
                    pass

            numbers = re.findall(r'\b([\-\d]+\.[0-9]{2,4})\b', page_text)
            for num in numbers:
                try:
                    value = float(num)
                    if -5 <= value <= 10:
                        print(f"✅ 找到 MVRV-Z: {value}")
                        return value
                except ValueError:
                    continue

            if attempt < 2:
                print(f"⚠️ 第 {attempt + 1} 次尝试未能获取 MVRV-Z，重试中...")
                page.wait_for_timeout(3000)
                continue

            print(f"⚠️ 未能从页面提取 MVRV-Z 数据")
            return None

        except Exception as e:
            if attempt < 2:
                print(f"⚠️ 第 {attempt + 1} 次尝试失败：{e}，重试中...")
                page.wait_for_timeout(3000)
                continue
            print(f"❌ 获取 MVRV-Z 数据失败：{e}")
            return None

    return None


def get_mvrv_data_with_browser():
    """
    使用 Playwright 浏览器获取 MVRV 和 MVRV-Z 数据

    返回:
        dict: 包含 mvrv, mvrv_z 的字典
    """
    result = {
        "mvrv": None,
        "mvrv_z": None,
        "success": False
    }

    try:
        with sync_playwright() as p:
            print("🚀 启动浏览器...")

            import platform
            system = platform.system()

            try:
                if system == "Windows":
                    browser = p.chromium.launch(
                        headless=True,
                        executable_path=CHROME_PATH
                    )
                else:
                    browser = p.chromium.launch(headless=True)
            except Exception as e:
                print(f"⚠️ 启动浏览器失败，使用默认设置：{e}")
                browser = p.chromium.launch(headless=True)

            page = browser.new_page()

            # 设置 User-Agent 模拟真实浏览器
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            })

            # 禁用 webdriver 属性
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            mvrv = get_mvrv_data(page)
            result["mvrv"] = mvrv

            mvrv_z = get_mvrv_z_score_data(page)
            result["mvrv_z"] = mvrv_z

            print("🔒 关闭浏览器...")
            browser.close()

            result["success"] = result["mvrv"] is not None and result["mvrv_z"] is not None

            return result

    except Exception as e:
        print(f"❌ 浏览器操作失败：{e}")
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


def build_push_content(mvrv, mvrv_z):
    """
    构建推送内容
    """
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
    else:
        buy_signal = "\n⚠️ 数据获取不完整"

    content = f"""📈 BTC MVRV 指标早报

━━━━━━━━━━━━━━━━━━
🔍 数据来源:
  • MVRV: https://newhedge.io/bitcoin/mvrv
  • MVRV-Z: https://newhedge.io/bitcoin/mvrv-z-score
━━━━━━━━━━━━━━━━━━

📊 当前指标：
  • MVRV Ratio = {mvrv if mvrv is not None else '获取失败'}
  • MVRV Z-Score = {mvrv_z if mvrv_z is not None else '获取失败'}

━━━━━━━━━━━━━━━━━━
💡 抄底条件:
  • MVRV < 1
  • MVRV-Z < 0
━━━━━━━━━━━━━━━━━━
{buy_signal}
⏰ 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    return content


def check_buy_signal(mvrv, mvrv_z):
    """检查是否满足抄底条件"""
    return mvrv is not None and mvrv_z is not None and (mvrv < 1 and mvrv_z < 0)


def main():
    """主函数"""
    print("=" * 50)
    print("🚀 BTC MVRV 指标监控推送程序启动")
    print("=" * 50)

    if not should_notify_today():
        now = datetime.now()
        print(f"\n⏰ 当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("📍 今天已经推送过提醒，跳过本次推送")
        print("=" * 50)
        return

    print("\n📋 第一步：获取配置...")

    feishu_webhook = os.environ.get("FEISHU_WEBHOOK")

    if not feishu_webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK 环境变量")
        print("请在系统环境变量中设置飞书 Webhook 地址")
        sys.exit(1)

    print(f"✅ 飞书 Webhook 已获取")

    print("\n🌐 第二步：使用浏览器获取 newhedge.io 数据...")

    mvrv_data = get_mvrv_data_with_browser()

    mvrv = mvrv_data.get("mvrv")
    mvrv_z = mvrv_data.get("mvrv_z")

    if mvrv is not None:
        print(f"\n✅ MVRV 获取成功：{mvrv}")
    else:
        print(f"\n⚠️ MVRV 获取失败")

    if mvrv_z is not None:
        print(f"✅ MVRV-Z 获取成功：{mvrv_z}")
    else:
        print(f"⚠️ MVRV-Z 获取失败")

    print("\n📱 第三步：发送飞书推送...")

    push_content = build_push_content(mvrv, mvrv_z)

    push_success = send_feishu_push(feishu_webhook, PUSH_TITLE, push_content)

    if push_success:
        print("✅ 飞书推送发送成功!")
        mark_as_pushed()

        if check_buy_signal(mvrv, mvrv_z):
            print("\n" + "=" * 50)
            print("⚠️  ⚠️  ⚠️  重要提醒!!!  ⚠️  ⚠️  ⚠️")
            print("=" * 50)
            print(f"🎯 MVRV = {mvrv} < 1 ⚠️ 满足抄底条件!")
            print(f"🎯 MVRV-Z = {mvrv_z} < 0 ⚠️ 满足抄底条件!")
            print("=" * 50)
    else:
        print("❌ 飞书推送发送失败")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("✅ 程序执行完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
