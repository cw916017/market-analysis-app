import pandas as pd
import pandas_ta as ta
import numpy as np

class IndicatorEngine:
    def __init__(self, df: pd.DataFrame):
        """
        初始化引擎
        :param df: 必須包含欄位 ['Open', 'High', 'Low', 'Close', 'Volume'] 的 DataFrame
        """
        self.df = df.copy()
        self.df.columns = [str(col).capitalize() for col in self.df.columns]

    def calculate_all(self) -> pd.DataFrame:
        """
        一次計算指定的 5 大技術指標 (MA/EMA, BBands, MACD, RSI, CCI)
        """
        data = self.df

        # 1. 移動平均線 (MA / EMA)
        data['MA_20'] = data.ta.sma(length=20)
        data['EMA_20'] = data.ta.ema(length=20)

        # 2. 布林通道 (Bollinger Bands)
        bbands = data.ta.bbands(length=20, std=2)
        if bbands is not None:
            data = pd.concat([data, bbands], axis=1)

        # 3. MACD 指標
        macd = data.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None:
            data = pd.concat([data, macd], axis=1)

        # 4. 相對強弱指標 (RSI)
        data['RSI_14'] = data.ta.rsi(length=14)

        # 5. 順勢指標 (CCI)
        data['CCI_14'] = data.ta.cci(length=14)

        return data