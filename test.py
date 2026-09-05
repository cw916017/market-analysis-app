import os
import sys

# 取得目前程式碼所在的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 將 libs 資料夾加入 Windows 64位元 DLL 搜尋路徑
libs_dir = os.path.join(script_dir, "libs")
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(libs_dir)

import time
import getpass
from SKDLLPython import CapitalAPIConnector

def main():
    print("-" * 40)
    print(" 🚀 啟動群益 API 自動化交易與資料接收測試 (64位元版)")
    print("-" * 40)

    user_id = input("請輸入您的身分證字號/帳號: ").strip()
    user_pw = getpass.getpass("請輸入您的密碼 (輸入時會隱藏): ").strip()
    print("-" * 40)

    connector = CapitalAPIConnector(account=user_id, password=user_pw)
    connector.login()

    target_symbols = ["2330", "2454"]
    print(f"正在訂閱即時 Tick 資料: {target_symbols}")
    connector.subscribe_realtime_ticks(target_symbols)

    print("正在取得歷史資料...")
    history_data = connector.get_historical_data("2330", timeframe="1d", count=60)
    print(f"成功取得歷史資料！")

    print("\n✨ 主程式架構運作正常，正在進入監控待命狀態...")
    for i in range(3, 0, -1):
        print(f"⏳ 系統運行中... 倒數 {i} 秒")
        time.sleep(1)

    print("🏁 測試執行結束！")

if __name__ == "__main__":
    main()