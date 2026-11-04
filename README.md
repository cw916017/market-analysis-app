# 台股分析與觀察工具

本儲存庫保留原有的市場分析與券商 API 程式，並新增一個以 Streamlit 執行的研究介面 `app.py`。

## 啟動研究介面

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

預設標的是台積電 `2330.TW`。上市代號通常使用 `.TW`，上櫃代號通常使用 `.TWO`。

## 研究介面功能

- 個股日、週、月 K 線與均線、成交量、MACD、RSI、KD
- 與加權指數、櫃買指數比較區間績效
- Yahoo Finance 可提供的估值、公司概況與新聞
- 自訂觀察清單快速掃描
- 資料缺漏時明確顯示，不以隨機或生成內容補值

## 資料說明

行情、公司基本面和新聞透過 Yahoo Finance (`yfinance`) 取得，可能延遲、缺漏或因供應商介面改變而失效。這個介面目前沒有串接法人買賣超、完整財報時間序列、除權息事件或正式全市場掃描；請勿將其視為即時報價或投資建議。

`market_analysis.py` 和券商 SDK 相關檔案是原有專案內容，這次新增的介面不會取代它們。

