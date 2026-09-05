import os
import ctypes
import threading
import queue
from ctypes import Structure, c_int, c_char_p, WINFUNCTYPE, POINTER, c_void_p, c_longlong, c_wchar_p
from ctypes import *
from typing import Callable, List, Tuple, Optional

class AccountData:
    def __init__(self, login_id: str, acc_type: str, branch: str, account: str):
        self.LoginID = login_id
        self.Type = acc_type
        self.Branch = branch
        self.Account = account
    @property
    def FullAccount(self):
        return f"{self.Branch}{self.Account}"

class LoginResult:
    def __init__(self, code: int, raw_account_data: str, ts_accounts: List[AccountData],
                 os_accounts: List[AccountData], tf_accounts: List[AccountData], of_accounts: List[AccountData]):
        self.Code = code
        self.RawAccountData = raw_account_data
        self.TSAccounts = ts_accounts
        self.OSAccounts = os_accounts
        self.TFAccounts = tf_accounts
        self.OFAccounts = of_accounts

def parse_accounts(raw: Optional[str], login_id: str, acc_type: str) -> List[AccountData]:
    result = []
    if not raw:
        return result
    segments = [s for s in raw.split('#') if s.strip()]
    for segment in segments:
        fields = segment.split(',')
        if len(fields) < 4:
            continue
        if fields[0].upper() != acc_type.upper():
            continue
        result.append(AccountData(login_id, fields[0], fields[1], fields[3]))
    return result

class StockInfo:
    def __init__(self, strQuoteCode, strStockName, strOrderCode, strExpiryDate):
        self.strQuoteCode = strQuoteCode
        self.strStockName = strStockName
        self.strOrderCode = strOrderCode
        self.strExpiryDate = strExpiryDate

    def __str__(self):
        return f"{self.strQuoteCode},{self.strStockName},{self.strOrderCode},{self.strExpiryDate}"

class StockListResult:
    def __init__(self, TypeNo, TypeName):
        self.TypeNo = TypeNo
        self.TypeName = TypeName
        self.Items = []

    @property
    def All(self):
        return "\n".join(str(item) for item in self.Items)

class StockListParser:
    def __init__(self, rawData):
        self.raw_data = rawData
        self._typeNoToResult = {}
        self._parse(rawData)

    def _parse(self, rawData):
        tempSegments = rawData.split('%')
        segments = [seg for seg in tempSegments if seg]

        i = 0
        while i + 2 < len(segments):
            try:
                typeNo = int(segments[i])
            except ValueError:
                i += 3
                continue

            typeName = segments[i + 1]
            rawItems = segments[i + 2]

            result = StockListResult(typeNo, typeName)
            tempEntries = rawItems.split(';')
            for entry in tempEntries:
                if not entry.strip():
                    continue
                fields = entry.split(',')
                if len(fields) == 4:
                    result.Items.append(StockInfo(
                        fields[0].strip(), fields[1].strip(),
                        fields[2].strip(), fields[3].strip()
                    ))
            self._typeNoToResult[typeNo] = result
            i += 3

    def GetTypeNo(self, typeNo):
        return self._typeNoToResult.get(typeNo)

    @property
    def AllTypeLists(self):
        return list(self._typeNoToResult.values())

    def GetAllType(self):
        return [f"{typeNo}{res.TypeName}" for typeNo, res in self._typeNoToResult.items()]

    def RawData(self):
        return self.raw_data

class ForeignBlock(Structure):
    _fields_ = [
        ("BankCode", c_char_p),          # 銀行代碼
        ("BankBranchCode", c_char_p),   # 銀行分行代號
        ("BankAccount", c_char_p),      # 銀行帳號
        ("BankName", c_char_p),         # 銀行名稱
        ("Currency", c_char_p),         # 幣別
        ("UnpayableAmt", c_char_p),     # 圈存金額
        ("UnpayableBuy", c_char_p),     # 買進未扣款
        ("TodayOrder", c_char_p),       # 股市委買
        ("OutAmt", c_char_p),           # 匯出換匯金額
        ("UnblockAmt", c_char_p),       # 可解圈金額
        ("FundOrderAmt", c_char_p),     # 基金委買
    ]

class ForeignBlockParserResult:
    def __init__(self):
        self.StatusCode = 0           # 回傳狀態碼
        self.Message = ""           # 錯誤訊息
        self.RawData = ""           # 原始字串
        self.Blocks = []  # List[ForeignBlock]            # 多筆資料可以先存原始字串，解析成 list[ForeignBlock] 後使用 Python list

class OpenInterest(Structure):
    _fields_ = [
        ("MarketType", c_char_p),   # 市場別
        ("Account", c_char_p),      # 帳號
        ("FutureNo", c_char_p),     # 商品
        ("BuySell", c_char_p),      # 買賣別
        ("Qty", c_char_p),          # 未平倉部位
        ("Qty_Trade", c_char_p),    # 當沖未平倉部位
        ("AvgPrice", c_char_p),     # 平均成本(小數部分已處理)
        ("Fee", c_char_p),          # 單口手續費
        ("Tax", c_char_p),          # 交易稅(萬分之X)
        ("LoginID", c_char_p),      # LOGIN_ID
        ("StatusCode", c_int),      # 回傳狀態碼
        ("Message", c_char_p),      # 錯誤訊息
        ("RawData", c_char_p),      # 原始字串
    ]

class OpenInterestParserResult:
    def __init__(self):
        self.StatusCode = 0           # 回傳狀態碼
        self.Message = ""           # 錯誤訊息
        self.RawData = ""           # 原始字串
        self.Blocks = []  # List[OpenInterest]            # 多筆資料可以先存原始字串，解析成 list[OpenInterest] 後使用 Python list

class OFOpenInterest(Structure):
    _fields_ = [
        ("Account", c_char_p),                 # 帳號
        ("ExchangeCode", c_char_p),          # 交易所代號
        ("ExchangeName", c_char_p),          # 交易所中文名稱
        ("ProductCodeWithYM", c_char_p),     # 含年月-商品代號
        ("ProductCode", c_char_p),           # 不含年月-商品代碼
        ("ProductYM", c_char_p),             # 商品年月
        ("ProductNameWithYM", c_char_p),     # 商品中文名稱(含年月)
        ("BuySell", c_char_p),               # 買賣別
        ("OpenInterest", c_char_p),          # 未平口數
        ("AvgPrice", c_char_p),              # 平均價(成交均價)
        ("MarketPrice", c_char_p),           # (非即時)現價(市價)
        ("UnrealizedPL", c_char_p),          # 未平損益
        ("BidPrice", c_char_p),              # 委託買
        ("BidVolume", c_char_p),             # 買方委託口數
        ("AskPrice", c_char_p),              # 委託賣
        ("AskVolume", c_char_p),             # 賣方委託口數
        ("AskNewOpenVolume", c_char_p),      # 賣方委託新倉口數
        ("PrevSettlementPrice", c_char_p),   # 昨日結算價
        ("DayTradeOpenInterest", c_char_p),  # 當沖未平口數
        ("InitialMargin", c_char_p),         # 原始保證金
        ("IsOption", c_char_p),              # 是否為選擇權(0->期貨 1->選擇權)
        ("LoginID", c_char_p),               # LOGIN_ID
        ("StrikePrice", c_char_p),           # 履約價
        ("CallPut", c_char_p),               # C/P (C:Call / P:Put)
        ("StatusCode", c_int),               # 回傳狀態碼
        ("Message", c_char_p),               # 錯誤訊息
        ("RawData", c_char_p),               # 原始字串
    ]

class OFOpenInterestParserResult:
    def __init__(self):
        self.StatusCode = 0           # 回傳狀態碼
        self.Message = ""           # 錯誤訊息
        self.RawData = ""           # 原始字串
        self.Blocks = []  # List[OFOpenInterest]            # 多筆資料可以先存原始字串，解析成 list[OFOpenInterest] 後使用 Python list

class RealBalanceReport(Structure):
    _fields_ = [
        ("StockCode", c_char_p),              # 股票代號
        ("InventoryType", c_char_p),          # 庫存種類 (T:集保 C:融資 L:融券)
        ("CreditLimitOriginal", c_char_p),    # 資額度(原始)
        ("CreditLimitAvailable", c_char_p),   # 資額度(可用)
        ("ShortLimitOriginal", c_char_p),     # 券額度(原始)
        ("ShortLimitAvailable", c_char_p),    # 券額度(可用)
        ("YesterdayInventory", c_char_p),     # 股數:昨日庫存
        ("TodayBidQty", c_char_p),            # 今日委買
        ("TodayAskQty", c_char_p),            # 今日委賣
        ("TodayBuyMatched", c_char_p),        # 今日買進成交
        ("TodaySellMatched", c_char_p),       # 今日賣出成交
        ("AvailableToSellOrCover", c_char_p), # 今日資券可回補/集保庫存可賣出
        ("DayTradeBuyableQty", c_char_p),     # 可資沖股數
        ("DayTradeSellableQty", c_char_p),    # 可券沖股數
        ("RealTimeInventory", c_char_p),      # 即時庫存
        ("RealTimeMarginRate", c_char_p),     # 即時個股維持率
        ("LoginID", c_char_p),                # LOGIN_ID
        ("AccountNo", c_char_p),              # ACCOUNT_NO

        ("StatusCode", c_int),               # 回傳狀態碼
        ("Message", c_char_p),               # 錯誤訊息
        ("RawData", c_char_p),               # 原始字串
    ]

class RealBalanceReportParserResult:
    def __init__(self):
        self.StatusCode = 0           # 回傳狀態碼
        self.Message = ""           # 錯誤訊息
        self.RawData = ""           # 原始字串
        self.Blocks = []  # List[RealBalanceReport]            # 多筆資料可以先存原始字串，解析成 list[RealBalanceReport] 後使用 Python list
      
class FutureRights(Structure):
    _fields_ = [
        ("AccountBalance", c_char_p),             # 帳戶餘額
        ("FloatingPL", c_char_p),                 # 浮動損益
        ("RealizedFee", c_char_p),                # 已實現費用
        ("TransactionTax", c_char_p),             # 交易稅
        ("WithheldPremium", c_char_p),            # 預扣權利金
        ("PremiumPayment", c_char_p),             # 權利金收付
        ("Equity", c_char_p),                     # 權益數
        ("ExcessMargin", c_char_p),               # 超額保證金
        ("DepositWithdrawal", c_char_p),          # 存提款
        ("BuyerMarketValue", c_char_p),           # 買方市值
        ("SellerMarketValue", c_char_p),          # 賣方市值
        ("FuturesClosePL", c_char_p),             # 期貨平倉損益
        ("IntradayUnrealized", c_char_p),         # 盤中未實現
        ("InitialMargin", c_char_p),              # 原始保證金
        ("MaintenanceMargin", c_char_p),          # 維持保證金
        ("PositionInitialMargin", c_char_p),      # 部位原始保證金
        ("PositionMaintenanceMargin", c_char_p), # 部位維持保證金
        ("OrderMargin", c_char_p),                # 委託保證金
        ("ExcessOptimalMargin", c_char_p),        # 超額最佳保證金
        ("TotalPremiumValue", c_char_p),          # 權利總值
        ("WithheldFee", c_char_p),                # 預扣費用
        ("OriginalInitialMargin", c_char_p),      # 原始保證金
        ("YesterdayBalance", c_char_p),           # 昨日餘額
        ("OptionComboMarginFlag", c_char_p),      # 選擇權組合單加不加收保證金
        ("MaintenanceRate", c_char_p),            # 維持率
        ("Currency", c_char_p),                   # 幣別
        ("FullInitialMargin", c_char_p),          # 足額原始保證金
        ("FullMaintenanceMargin", c_char_p),      # 足額維持保證金
        ("FullAvailable", c_char_p),              # 足額可用
        ("OffsetAmount", c_char_p),               # 抵繳金額
        ("SecuritiesAvailable", c_char_p),        # 有價可用
        ("AvailableBalance", c_char_p),           # 可用餘額
        ("FullCashAvailable", c_char_p),          # 足額現金可用
        ("SecuritiesValue", c_char_p),            # 有價價值
        ("RiskIndicator", c_char_p),              # 風險指標
        ("OptionExpiryDifference", c_char_p),     # 選擇權到期差異
        ("OptionExpiryPL", c_char_p),             # 選擇權到期差損
        ("FuturesExpiryPL", c_char_p),            # 期貨到期損益
        ("AdditionalMargin", c_char_p),           # 加收保證金
        ("LoginID", c_char_p),                    # LOGIN_ID
        ("AccountNo", c_char_p),                  # ACCOUNT_NO

        ("StatusCode", c_int),                    # 回傳狀態碼
        ("Message", c_char_p),                    # 錯誤訊息
        ("RawData", c_char_p)                     # 原始字串
    ]

class FutureRightsParserResult:
    def __init__(self):
        self.StatusCode = 0           # 回傳狀態碼
        self.Message = ""           # 錯誤訊息
        self.RawData = ""           # 原始字串
        self.Blocks = []  # List[FutureRights]            # 多筆資料可以先存原始字串，解析成 list[FutureRights] 後使用 Python list

class OFFutureRights(Structure):
    _fields_ = [
        ("LoginID", c_char_p),                    # LOGIN_ID
        ("AccountNo", c_char_p),                  # 帳號
        ("Currency", c_char_p),                   # 幣別
        ("RiskIndicator", c_char_p),              # 風險指標/維持率
        ("FullMaintenanceMargin", c_char_p),      # 足額維持率
        ("WithdrawableMargin", c_char_p),         # 可動用(出金)保證金
        ("OrderMargin", c_char_p),                # 委託保證金
        ("MaintenanceMargin", c_char_p),          # 維持保證金
        ("InitialMargin", c_char_p),              # 原始保證金
        ("NetEquity", c_char_p),                  # 淨值權益數、權益總值
        ("WithheldPremium", c_char_p),            # 預扣權利金
        ("OptionLongMarketValue", c_char_p),      # 未沖銷買方選擇權市值
        ("OptionShortMarketValue", c_char_p),     # 未沖銷賣方選擇權市值
        ("AccountEquity", c_char_p),              # 帳戶權益、權益數
        ("IntradayUnrealized", c_char_p),         # 盤中未實現
        ("FuturesFloatingPL", c_char_p),          # 未沖銷期貨浮動損益
        ("PremiumPaidToday", c_char_p),           # 今日權利金支付
        ("FuturesClosePLToday", c_char_p),        # 本日期貨平倉損益淨額
        ("RealizedFee", c_char_p),                # 已實現費用、手續費
        ("DepositWithdrawalToday", c_char_p),     # 今日存提款
        ("PreviousDayBalance", c_char_p),         # 前日帳戶餘額
        ("ReferenceRate", c_char_p),              # 參考匯率
        ("OptionExpiryGain", c_char_p),           # 選擇權到期差益
        ("OptionExpiryLoss", c_char_p),           # 選擇權到期差損
        ("FuturesDeliveryPL", c_char_p),          # 期貨交割損益
        ("ExcessOrMarginCall", c_char_p),         # 超額/追繳保證金
        ("ExerciseSettlementPL", c_char_p),       # 到期履約損益
        ("AccountBalance", c_char_p),             # 帳戶餘額
        ("FixedMargin", c_char_p),                # 固定保證金
        ("VariableMargin", c_char_p),             # 變動保證金

        ("StatusCode", c_int),                    # 回傳狀態碼
        ("Message", c_char_p),                    # 錯誤訊息
        ("RawData", c_char_p)                     # 原始字串
    ]

class OFFutureRightsParserResult:
    def __init__(self):
        self.StatusCode = 0           # 回傳狀態碼
        self.Message = ""           # 錯誤訊息
        self.RawData = ""           # 原始字串
        self.Blocks = []  # List[OFFutureRights]            # 多筆資料可以先存原始字串，解析成 list[OFFutureRights] 後使用 Python list


class STOCKPROXYORDER2(Structure):
    _fields_ = [
        ("strStockNo", c_char_p),
        ("strFullAccount", c_char_p),
        ("strSeqNo", c_char_p),
        ("strBookNo", c_char_p),
        ("strPrice", c_char_p),
        ("strOrderType", c_char_p),
        ("nSpecialTradeType", c_int),
        ("nTradeType", c_int),
        ("nPeriod", c_int),
        ("nQty", c_int),
        ("nPriceMark", c_int),

        ("strPrice_forD", c_char_p),
        ("strBuySell_forD", c_char_p),
        ("nPrime", c_int),
        ("strOrderType2", c_char_p),
    ]

class FUTUREPROXYORDER2(Structure):
    _fields_ = [
        ("strStockNo", c_char_p),
        ("strFullAccount", c_char_p),
        ("strSeqNo", c_char_p),
        ("strBookNo", c_char_p),
        ("strPrice", c_char_p),
        ("strSettleYM", c_char_p),
        ("strStrike", c_char_p),
        ("strSettleYM2", c_char_p),
        ("strStrike2", c_char_p),
        ("strOrderType", c_char_p),
        ("nReserved", c_int),
        ("nQty", c_int),
        ("nCP", c_int),
        ("nBuySell", c_int),
        ("strStockNo2", c_char_p),
        ("nCP2", c_int),
        ("nBuySell2", c_int),
        ("nPriceFlag", c_int),
        ("nTradeType", c_int),
        ("nDayTrade", c_int),
    ]

class OVERSEAFUTUREORDER2(Structure):
    _fields_ = [
        ("strFullAccount", c_char_p),
        ("strExchangeNo", c_char_p),
        ("strStockNo", c_char_p),
        ("strYearMonth", c_char_p),
        ("strYearMonth2", c_char_p),
        ("strOrder", c_char_p),
        ("strOrderNumerator", c_char_p),
        ("strTrigger", c_char_p),
        ("strTriggerNumerator", c_char_p),
        ("strStrikePrice", c_char_p),
        ("strStockNo2", c_char_p),
        ("strOrderDenominator", c_char_p),
        ("strBookNo", c_char_p),
        ("strSeqNo", c_char_p),
        ("nBuySell", c_int),
        ("nNewClose", c_int),
        ("nDayTrade", c_int),
        ("nTradeType", c_int),
        ("nSpecialTradeType", c_int),
        ("nCallPut", c_int),
        ("nQty", c_int),
        ("nBuySell2", c_int),
        ("nSpreadFlag", c_int),
        ("nAlterType", c_int),
        ("strLongEndDate", c_char_p),
        ("strOrder2", c_char_p),
        ("strOrderNumerator2", c_char_p),
        ("strTriggerNumerator2", c_char_p),
        ("strTriggerDenominator", c_char_p),
        ("strOrderDenominator2", c_char_p),
        ("strTriggerDenominator2", c_char_p),
        ("strTrigger2", c_char_p),
        ("nLongActionFlag", c_int),
        ("nLAType", c_int),
        ("nReserved", c_int),
        ("nTimeFlag", c_int),
        ("nOrderPriceType", c_int),
        ("nMarketNo", c_int),
        ("nTriggerDirection", c_int),
        ("strExchangeNo2", c_char_p),
        ("nKind", c_int),
    ]

class OSSTOCKPROXYORDER2(Structure):
    _fields_ = [
        ("strFullAccount", c_char_p),
        ("strStockNo", c_char_p),
        ("strExchangeNo", c_char_p),
        ("strPrice", c_char_p),
        ("strCurrency1", c_char_p),
        ("strCurrency2", c_char_p),
        ("strCurrency3", c_char_p),
        ("strSeqNo", c_char_p),
        ("strBookNo", c_char_p),
        ("nAccountType", c_int),
        ("nQty", c_int),
        ("nOrderType", c_int),
        ("nTradeType", c_int),
        ("strProxyQty", c_char_p),
    ]

class OrderFulfillData:
    def __init__(self, raw_data: str):
        self._fields = raw_data.split(',')
        self._cache = {}

    def _get(self, index: int) -> str:
        return self._fields[index] if 0 <= index < len(self._fields) else ""

    def _lazy(index: int, name: str):
        return property(lambda self: self._cache.setdefault(name, self._get(index)))

    KeyNo                     = _lazy(0, "KeyNo")
    MarketType                 = _lazy(1, "MarketType")
    Type                       = _lazy(2, "Type")
    OrderErr                   = _lazy(3, "OrderErr")
    Broker                     = _lazy(4, "Broker")
    CustNo                     = _lazy(5, "CustNo")
    BuySell                    = _lazy(6, "BuySell")
    ExchangeID                 = _lazy(7, "ExchangeID")
    ComId                      = _lazy(8, "ComId")
    StrikePrice                = _lazy(9, "StrikePrice")
    OrderNo                    = _lazy(10, "OrderNo")
    Price                      = _lazy(11, "Price")
    Numerator                  = _lazy(12, "Numerator")
    Denominator                = _lazy(13, "Denominator")
    Price1                     = _lazy(14, "Price1")
    Numerator1                 = _lazy(15, "Numerator1")
    Denominator1               = _lazy(16, "Denominator1")
    Price2                     = _lazy(17, "Price2")
    Numerator2                 = _lazy(18, "Numerator2")
    Denominator2               = _lazy(19, "Denominator2")
    Qty                        = _lazy(20, "Qty")
    BeforeQty                  = _lazy(21, "BeforeQty")
    AfterQty                   = _lazy(22, "AfterQty")
    Date                       = _lazy(23, "Date")
    Time                       = _lazy(24, "Time")
    OkSeq                      = _lazy(25, "OkSeq")
    SubID                      = _lazy(26, "SubID")
    SaleNo                     = _lazy(27, "SaleNo")
    Agent                      = _lazy(28, "Agent")
    TradeDate                  = _lazy(29, "TradeDate")
    MsgNo                      = _lazy(30, "MsgNo")
    PreOrder                   = _lazy(31, "PreOrder")
    ComId1                     = _lazy(32, "ComId1")
    YearMonth1                 = _lazy(33, "YearMonth1")
    StrikePrice1               = _lazy(34, "StrikePrice1")
    ComId2                     = _lazy(35, "ComId2")
    YearMonth2                 = _lazy(36, "YearMonth2")
    StrikePrice2               = _lazy(37, "StrikePrice2")
    ExecutionNo                = _lazy(38, "ExecutionNo")
    PriceSymbol                = _lazy(39, "PriceSymbol")
    Reserved                   = _lazy(40, "Reserved")
    OrderEffective             = _lazy(41, "OrderEffective")
    CallPut                    = _lazy(42, "CallPut")
    OrderSeq                   = _lazy(43, "OrderSeq")
    ErrorMsg                   = _lazy(44, "ErrorMsg")
    CancelOrderMarkByExchange = _lazy(45, "CancelOrderMarkByExchange")
    ExchangeTandemMsg          = _lazy(46, "ExchangeTandemMsg")
    SeqNo                      = _lazy(47, "SeqNo")
    OFSTPFlag                  = _lazy(48, "OFSTPFlag")

    @property
    def Raw(self): return ",".join(self._fields)

class _SKSTOCKLONG2_Internal(Structure):
    _fields_ = [
        ("nStockidx", c_int),
        ("nDecimal", c_int),
        ("nTypeNo", c_int),
        ("nMarketNo", c_int),
        ("strStockNo", c_char_p),
        ("strStockName", c_wchar_p),
        ("strStockNoSpread", c_char_p),
        ("nOpen", c_int),
        ("nHigh", c_int),
        ("nLow", c_int),
        ("nClose", c_int),
        ("nTickQty", c_int),
        ("nRef", c_int),
        ("nBid", c_int),
        ("nBc", c_int),
        ("nAsk", c_int),
        ("nAc", c_int),
        ("nTBc", c_int),
        ("nTAc", c_int),
        ("nFutureOI", c_int),
        ("nTQty", c_int),
        ("nYQty", c_int),
        ("nUp", c_int),
        ("nDown", c_int),
        ("nSimulate", c_int),
        ("nDayTrade", c_int),
        ("nTradingDay", c_int),
        ("nTradingLotFlag", c_int),
        ("nDealTime", c_int),
        ("nOddLotBid", c_int),
        ("nOddLotAsk", c_int),
        ("nOddLotClose", c_int),
        ("nOddLotQty", c_int),
    ]

class _SKFOREIGN_9LONG2_Internal(Structure):
    _fields_ = [
        ("nStockidx", c_int),
        ("nDecimal", c_int),
        ("nDenominator", c_int),

        ("nMarketNo", c_int),
        ("strExchangeNo", c_char_p),
        ("strExchangeName", c_char_p),
        ("strStockNo", c_char_p),
        ("strStockName", c_wchar_p),
        ("strCallPut", c_char_p),

        ("nOpen", c_longlong),
        ("nHigh", c_longlong),
        ("nLow", c_longlong),
        ("nClose", c_longlong),
        ("nSettlePrice", c_longlong),
        ("nTickQty", c_int),
        ("nRef", c_longlong),

        ("nBid", c_longlong),
        ("nBc", c_int),
        ("nAsk", c_longlong),
        ("nAc", c_int),

        ("nTQty", c_longlong),
        ("nStrikePrice", c_int),
        ("nTradingDay", c_int),
    ]

# SK COM component wrapper and interface provider for other Python modules

class SK:
    import os
    import ctypes

    dll_path = r"C:\Users\cw916\OneDrive\Desktop\happy\libs\SKCOM.dll"
    libs_dir = os.path.dirname(dll_path)

    # 1. 預先將 libs 加入 DLL 搜尋目錄
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(libs_dir)

    # 2. 先手動載入可能需要的底層執行階段（避免相依性報錯）
    try:
        ctypes.CDLL(os.path.join(libs_dir, "libsolclient_64.dll")) # 如果有的話
    except Exception:
        pass

    # 3. 正式載入 SKCOM.dll
    _dll = ctypes.WinDLL(dll_path)

    class _RawLOGINGW(Structure):
        _fields_ = [
            ("nAuthorityFlag", c_int),
            ("strLoginID", c_char_p),
            ("strPassword", c_char_p),
            ("strCustCertID", c_char_p),
            ("strPath", c_char_p),
        ]

    class LOGINGW:
        def __init__(self, nAuthorityFlag=0, strLoginID="", strPassword="", strCustCertID=None, strPath=None):
            self.nAuthorityFlag = nAuthorityFlag
            self.strLoginID = strLoginID
            self.strPassword = strPassword
            self.strCustCertID = strCustCertID
            self.strPath = strPath

        def to_ctypes(self):
            return SK._RawLOGINGW(
                self.nAuthorityFlag,
                self.strLoginID.encode("utf-8") if self.strLoginID else None,
                self.strPassword.encode("utf-8") if self.strPassword else None,
                self.strCustCertID.encode("utf-8") if self.strCustCertID else None,
                self.strPath.encode("utf-8") if self.strPath else None
            )

    class SKSTOCKLONG2:
        def __init__(self, internal: _SKSTOCKLONG2_Internal, code: int):
            self.nCode = code

            self.nStockidx = internal.nStockidx
            self.nDecimal = internal.nDecimal
            self.nTypeNo = internal.nTypeNo
            self.nMarketNo = internal.nMarketNo

            self.strStockNo = internal.strStockNo.decode("ansi") if internal.strStockNo else ""
            self.strStockName = internal.strStockName if internal.strStockName else ""
            self.strStockNoSpread = internal.strStockNoSpread.decode("ansi") if internal.strStockNoSpread else ""

            self.nOpen = internal.nOpen
            self.nHigh = internal.nHigh
            self.nLow = internal.nLow
            self.nClose = internal.nClose

            self.nTickQty = internal.nTickQty
            self.nRef = internal.nRef

            self.nBid = internal.nBid
            self.nBc = internal.nBc
            self.nAsk = internal.nAsk
            self.nAc = internal.nAc

            self.nTBc = internal.nTBc
            self.nTAc = internal.nTAc

            self.nFutureOI = internal.nFutureOI

            self.nTQty = internal.nTQty
            self.nYQty = internal.nYQty

            self.nUp = internal.nUp
            self.nDown = internal.nDown
            self.nSimulate = internal.nSimulate

            self.nDayTrade = internal.nDayTrade
            self.nTradingDay = internal.nTradingDay
            self.nTradingLotFlag = internal.nTradingLotFlag
            self.nDealTime = internal.nDealTime

            self.nOddLotBid = internal.nOddLotBid
            self.nOddLotAsk = internal.nOddLotAsk
            self.nOddLotClose = internal.nOddLotClose
            self.nOddLotQty = internal.nOddLotQty

    class SKFOREIGN_9LONG2:
        def __init__(self, internal: _SKFOREIGN_9LONG2_Internal, code: int):
            self.nCode = code

            self.nStockidx = internal.nStockidx
            self.nDecimal = internal.nDecimal
            self.nDenominator = internal.nDenominator

            self.nMarketNo = internal.nMarketNo
            self.strExchangeNo = internal.strExchangeNo.decode("ansi") if internal.strExchangeNo else ""
            self.strExchangeName = internal.strExchangeName.decode("ansi") if internal.strExchangeName else ""
            self.strStockNo = internal.strStockNo.decode("ansi") if internal.strStockNo else ""
            self.strStockName = internal.strStockName if internal.strStockName else ""
            self.strCallPut = internal.strCallPut.decode("ansi") if internal.strCallPut else ""

            self.nOpen = internal.nOpen
            self.nHigh = internal.nHigh
            self.nLow = internal.nLow
            self.nClose = internal.nClose
            self.nSettlePrice = internal.nSettlePrice
            self.nTickQty = internal.nTickQty
            self.nRef = internal.nRef

            self.nBid = internal.nBid
            self.nBc = internal.nBc
            self.nAsk = internal.nAsk
            self.nAc = internal.nAc

            self.nTQty = internal.nTQty
            self.nStrikePrice = internal.nStrikePrice
            self.nTradingDay = internal.nTradingDay

    # Functions
    _dll.SKCenterLib_Login.argtypes = [POINTER(_RawLOGINGW), c_char_p, c_int]
    _dll.SKCenterLib_Login.restype = c_int

    _dll.ManageServerConnection.argtypes = [c_char_p, c_int, c_int]
    _dll.ManageServerConnection.restype = c_int

    _dll.LoadCommodity.argtypes = [c_int]
    _dll.LoadCommodity.restype = c_int

    _dll.SKQuoteLib_RequestStockList.argtypes = [c_int]
    _dll.SKQuoteLib_RequestStockList.restype = c_char_p

    _dll.SKCenterLib_GetReturnCodeMessage.argtypes = [c_int]
    _dll.SKCenterLib_GetReturnCodeMessage.restype = c_char_p

    _dll.SendStockProxyOrder.argtypes = [c_char_p, STOCKPROXYORDER2, c_char_p, c_int]
    _dll.SendStockProxyOrder.restype = c_int

    _dll.SendStockProxyAlter.argtypes = [c_char_p, STOCKPROXYORDER2, c_char_p, c_int]
    _dll.SendStockProxyAlter.restype = c_int

    _dll.SendFutureProxyOrderCLR.argtypes = [c_char_p, FUTUREPROXYORDER2, c_char_p, c_int]
    _dll.SendFutureProxyOrderCLR.restype = c_int

    _dll.SendFutureProxyAlter.argtypes = [c_char_p, FUTUREPROXYORDER2, c_char_p, c_int]
    _dll.SendFutureProxyAlter.restype = c_int

    _dll.SendOptionProxyOrder.argtypes = [c_char_p, FUTUREPROXYORDER2, c_char_p, c_int]
    _dll.SendOptionProxyOrder.restype = c_int

    _dll.SendDuplexProxyOrder.argtypes = [c_char_p, FUTUREPROXYORDER2, c_char_p, c_int]
    _dll.SendDuplexProxyOrder.restype = c_int

    _dll.SendOptionProxyAlter.argtypes = [c_char_p, FUTUREPROXYORDER2, c_char_p, c_int]
    _dll.SendOptionProxyAlter.restype = c_int

    _dll.SendOverseaFutureProxyOrder.argtypes = [c_char_p, OVERSEAFUTUREORDER2, c_char_p, c_int]
    _dll.SendOverseaFutureProxyOrder.restype = c_int

    _dll.SendOverseaFutureSpreadProxyOrder.argtypes = [c_char_p, OVERSEAFUTUREORDER2, c_char_p, c_int]
    _dll.SendOverseaFutureSpreadProxyOrder.restype = c_int

    _dll.SendOverseaFutureProxyAlter.argtypes = [c_char_p, OVERSEAFUTUREORDER2, c_char_p, c_int]
    _dll.SendOverseaFutureProxyAlter.restype = c_int

    _dll.SendOverseaOptionProxyOrder.argtypes = [c_char_p, OVERSEAFUTUREORDER2, c_char_p, c_int]
    _dll.SendOverseaOptionProxyOrder.restype = c_int

    _dll.SendForeignStockProxyOrder.argtypes = [c_char_p, OSSTOCKPROXYORDER2, c_char_p, c_int]
    _dll.SendForeignStockProxyOrder.restype = c_int

    _dll.SendForeignStockProxyCancel.argtypes = [c_char_p, OSSTOCKPROXYORDER2, c_char_p, c_int]
    _dll.SendForeignStockProxyCancel.restype = c_int

    _dll.SKQuoteLib_GetStockByStockNo.argtypes = [c_int, c_char_p, POINTER(_SKSTOCKLONG2_Internal)]
    _dll.SKQuoteLib_GetStockByStockNo.restype = c_int

    _dll.SKQuoteLib_RequestStocks.argtypes = [c_char_p]
    _dll.SKQuoteLib_RequestStocks.restype = c_int

    _dll.SKQuoteLib_RequestStocksOddLot.argtypes = [c_char_p]
    _dll.SKQuoteLib_RequestStocksOddLot.restype = c_int

    _dll.SKQuoteLib_CancelRequestStocks.argtypes = [c_char_p]
    _dll.SKQuoteLib_CancelRequestStocks.restype = c_int

    _dll.SKQuoteLib_RequestTicks.argtypes = [c_int, c_char_p]
    _dll.SKQuoteLib_RequestTicks.restype = c_int

    _dll.SKQuoteLib_RequestTicksOddLot.argtypes = [c_int, c_char_p]
    _dll.SKQuoteLib_RequestTicksOddLot.restype = c_int

    _dll.SKQuoteLib_CancelRequestTicks.argtypes = [c_char_p]
    _dll.SKQuoteLib_CancelRequestTicks.restype = c_int

    _dll.GetForeignBlock.argtypes = [c_char_p, c_char_p, c_int, c_char_p, c_int]
    _dll.GetForeignBlock.restype = c_int

    _dll.WithDraw.argtypes = [c_char_p, c_char_p, c_int, c_char_p, c_int, c_int, c_char_p, c_char_p, c_char_p, c_int]
    _dll.WithDraw.restype = c_int

    _dll.SendTFOffset.argtypes = [c_char_p, c_char_p, c_int, c_char_p, c_int, c_int, c_int, c_int, c_char_p, c_int]
    _dll.SendTFOffset.restype = c_int

    _dll.GetOpenInterestGW.argtypes = [c_char_p, c_char_p, c_int, c_char_p, c_int]
    _dll.GetOpenInterestGW.restype = c_int

    @staticmethod
    def Login(*args) -> LoginResult:
        """
        Simulated overloads:
        - Login(id, pwd)
        - Login(id, pwd, flag)
        - Login(id, pwd, flag, cert)
        - Login(id, pwd, flag, cert, path)
        """
        id_ = pwd = cert = path = ""
        flag = 0

        if len(args) == 2:
            id_, pwd = args
        elif len(args) == 3:
            id_, pwd, flag = args
        elif len(args) == 4:
            id_, pwd, flag, cert = args
        elif len(args) == 5:
            id_, pwd, flag, cert, path = args
        else:
            raise TypeError("Login expects 2, 3, 4, or 5 arguments")

        login_obj = SK.LOGINGW(
            nAuthorityFlag=flag,
            strLoginID=id_,
            strPassword=pwd,
            strCustCertID=cert if cert else None,
            strPath=path if path else None
        )
        # 實際呼叫 DLL 登入邏輯可接在此處...