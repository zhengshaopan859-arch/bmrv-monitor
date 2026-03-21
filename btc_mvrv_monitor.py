#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
<<<<<<< HEAD
BTC MVRV 数据监控脚本

功能：
1. 使用 Playwright 从 coinank.com 获取 BTC MVRV 和 MVRV-Z 数据
2. 判断抄底信号（MVRV < 1 且 MVRV-Z < 0）
3. 通过 Windows 弹窗提醒用户
4. 记录日志
5. 只在每天中午 12 点推送一次提醒

运行方式：
    python btc_mvrv_monitor.py
    或双击 run_btc_monitor.bat
"""

import json
import logging
import re
import requests
from datetime import datetime
from pathlib import Path

try:
    import winsound
    import ctypes
    WINDOWS_MODE = True
except ImportError:
    WINDOWS_MODE = False

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"btc_mvrv_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_FILE = Path("btc_mvrv_data.json")

CHROME_PATH = r"D:\Users\zsp\AppData\Local\Programs\chrome-win64\chrome.exe"


def show_windows_notification(title, message, is_alert=False):
    if WINDOWS_MODE:
        if is_alert:
            winsound.MessageBeep(winsound.MB_ICONHAND)
        else:
            winsound.MessageBeep(winsound.MB_OK)
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 if not is_alert else 0x30)
    else:
        print(f"\n{'='*60}")
        print(f"【{title}】")
        print(f"{message}")
        print(f"{'='*60}\n")


def get_btc_price():
    """获取 BTC 当前价格"""
    logger.info("正在获取 BTC 价格...")
    
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            price = response.json()['bitcoin']['usd']
            logger.info(f"✅ BTC 价格: ${price:,.2f}")
            return price
    except Exception as e:
        logger.warning(f"获取价格失败: {e}")
    
    return None


def get_mvrv_from_coinank():
    """从 coinank.com 获取 MVRV 和 MVRV-Z 数据"""
    logger.info("正在从 coinank.com 获取 MVRV 数据...")
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path=CHROME_PATH
            )
            page = browser.new_page()
            
            # 访问 coinank MVRV 页面
            page.goto("https://coinank.com/zh/chart/indicator/mvrv-z-score", timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # 等待页面加载
            page.wait_for_timeout(3000)
            
            # 获取页面内容
            content = page.content()
            
            # 尝试多种方式提取数据
            
            # 方法1: 查找数值
            # 页面通常会显示当前或最近的值
            patterns = {
                'mvrv': [
                    r'MVRV[\s\S]*?([\d.]+)',
                    r'mvrv["\s:]+([\d.]+)',
                    r'([\d.]+)[\s\S]*?MVRV',
                ],
                'mvrv_z': [
                    r'Z-Score[\s\S]*?([\-\d.]+)',
                    r'zscore["\s:]+([\-\d.]+)',
                    r'([\-\d.]+)[\s\S]*?Z-Score',
                    r'MVRV-Z[\s\S]*?([\-\d.]+)',
                ]
            }
            
            result = {}
            
            # 查找 MVRV 值
            for pattern in patterns['mvrv']:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1))
                        if 0 < value < 10:  # MVRV 通常在 0-10 之间
                            result['mvrv'] = value
                            logger.info(f"✅ MVRV: {value}")
                            break
                    except:
                        continue
            
            # 查找 MVRV-Z 值
            for pattern in patterns['mvrv_z']:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1))
                        if -5 < value < 10:  # MVRV-Z 通常在 -5 到 10 之间
                            result['mvrv_z'] = value
                            logger.info(f"✅ MVRV-Z: {value}")
                            break
                    except:
                        continue
            
            # 方法2: 尝试从 JavaScript 数据中提取
            if 'mvrv' not in result or 'mvrv_z' not in result:
                # 查找图表数据
                script_pattern = r'window\.\w+\s*=\s*(\{[\s\S]*?\})'
                scripts = re.findall(script_pattern, content)
                
                for script in scripts:
                    # 尝试在脚本中找到数据
                    mvrv_match = re.search(r'"mvrv"[:\s]*([0-9.]+)', script)
                    zscore_match = re.search(r'"zscore"[:\s]*([-\d.]+)', script)
                    
                    if mvrv_match and 'mvrv' not in result:
                        try:
                            result['mvrv'] = float(mvrv_match.group(1))
                            logger.info(f"✅ MVRV (from script): {result['mvrv']}")
                        except:
                            pass
                    
                    if zscore_match and 'mvrv_z' not in result:
                        try:
                            result['mvrv_z'] = float(zscore_match.group(1))
                            logger.info(f"✅ MVRV-Z (from script): {result['mvrv_z']}")
                        except:
                            pass
            
            browser.close()
            
            if result:
                return result
            
    except ImportError:
        logger.error("未安装 Playwright")
    except Exception as e:
        logger.warning(f"coinank.com 获取失败: {e}")
    
    return None


def get_btc_mvrv_data():
    """获取完整的 BTC MVRV 数据"""
    logger.info("=" * 60)
    logger.info("开始获取 BTC MVRV 数据")
    logger.info("=" * 60)
    
    result = {}
    
    # 1. 获取 BTC 价格
    price = get_btc_price()
    if price:
        result['price'] = price
    else:
        result['price'] = 0
    
    # 2. 从 coinank.com 获取 MVRV 数据
    mvrv_data = get_mvrv_from_coinank()
    
    if mvrv_data:
        result['mvrv'] = mvrv_data.get('mvrv', 0)
        result['mvrv_z'] = mvrv_data.get('mvrv_z', 0)
        result['source'] = 'coinank.com'
    else:
        logger.error("无法从 coinank.com 获取 MVRV 数据")
        return None
    
    # 添加时间戳
    result['timestamp'] = datetime.now().isoformat()
    result['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 输出结果
    logger.info("=" * 60)
    logger.info(f"✅ 数据获取完成:")
    logger.info(f"   BTC 价格: ${result.get('price', 0):,.2f}")
    logger.info(f"   MVRV: {result.get('mvrv', 0)}")
    logger.info(f"   MVRV-Z: {result.get('mvrv_z', 0)}")
    logger.info("=" * 60)
    
    return result


def save_data(data):
    """保存数据到 JSON 文件"""
    try:
        all_data = []
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        
        all_data.append(data)
        all_data = all_data[-30:]
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据已保存到 {DATA_FILE}")
    except Exception as e:
        logger.error(f"保存数据失败: {e}")


def check_buy_signal(data):
    """检查抄底信号"""
    if not data:
        return False
    
    mvrv = data.get("mvrv")
    mvrv_z = data.get("mvrv_z")
    
    if mvrv is None:
        return False
    
    is_buy_signal = mvrv < 1.0 and mvrv_z < 0.0
    
    logger.info(f"当前数据: MVRV={mvrv}, MVRV-Z={mvrv_z}")
    logger.info(f"抄底信号: {is_buy_signal}")
    
    return is_buy_signal


def should_notify_today():
    """检查今天是否已经推送过提醒"""
    if not DATA_FILE.exists():
        return True
    
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        
        if not all_data:
            return True
        
        # 获取最后一条记录的时间
        last_record = all_data[-1]
        last_date = last_record.get('date', '')
        
        if not last_date:
            return True
        
        # 解析日期
        last_datetime = datetime.strptime(last_date, "%Y-%m-%d %H:%M:%S")
        today = datetime.now()
        
        # 如果是同一天，且已经推送过，则不再推送
        if last_datetime.date() == today.date():
            logger.info(f"今天已推送过提醒 (上次推送时间：{last_date})")
            return False
        
        return True
    except Exception as e:
        logger.warning(f"检查推送状态失败：{e}")
        return True


def main():
    logger.info("=" * 60)
    logger.info("BTC MVRV 数据监控启动")
    logger.info("数据来源：coinank.com")
    logger.info("=" * 60)
    
    # 检查当前时间是否为中午 12 点（允许前后 5 分钟误差）
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # 只在 11:55 - 12:05 之间执行推送
    if not (current_hour == 12 and current_minute <= 5):
        logger.info(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("不在推送时间窗口内（中午 12:00-12:05），跳过本次检查")
        logger.info("监控完成")
        return
    
    # 检查今天是否已经推送过
    if not should_notify_today():
        logger.info("今天已经推送过提醒，跳过")
        logger.info("监控完成")
        return
    
    logger.info(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("开始执行中午 12 点推送...")
    
    data = get_btc_mvrv_data()
    
    if data:
        save_data(data)
        
        message = f"BTC MVRV 数据更新\n\n"
        message += f"BTC 价格：${data.get('price', 0):,.2f}\n\n"
        message += f"MVRV: {data.get('mvrv', 0)}\n"
        message += f"MVRV-Z: {data.get('mvrv_z', 0)}\n"
        message += f"\n时间：{data['date']}\n\n"
        
        if check_buy_signal(data):
            message += "🚨 抄底信号触发！\n"
            message += "MVRV < 1 且 MVRV-Z < 0\n"
            message += "建议关注买入机会！"
            show_windows_notification("🚨 BTC 抄底信号！", message, is_alert=True)
        else:
            message += "未触发抄底信号\n"
            message += "继续观察..."
            show_windows_notification("BTC MVRV 数据更新", message, is_alert=False)
    else:
        error_msg = "获取 BTC MVRV 数据失败，请检查网络连接。"
        logger.error(error_msg)
        show_windows_notification("⚠️ 数据获取失败", error_msg, is_alert=True)
    
    logger.info("监控完成")
=======
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
>>>>>>> 5cb7db1778700d1ae6f6db75aaf70dd65df304cd


if __name__ == "__main__":
    main()
