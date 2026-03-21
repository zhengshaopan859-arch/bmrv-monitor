#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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
    """显示 Windows 系统通知弹窗"""
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
    """主函数：运行 BTC MVRV 监控"""
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


if __name__ == "__main__":
    main()
