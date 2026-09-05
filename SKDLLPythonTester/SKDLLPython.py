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
        ("BankCode", c_char_p),         # 銀行代碼
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


#class ForeignBlockParserResult(Structure):
#    _fields_ = [
 #       ("StatusCode", c_int),          # 回傳狀態碼
 #       ("Message", c_char_p),          # 錯誤訊息
 #       ("RawData", c_char_p),          # 原始字串
 #       ("Blocks", c_char_p),           # 多筆資料可以先存原始字串，解析成 list[ForeignBlock] 後使用 Python list
 #   ]
class ForeignBlockParserResult:
    def __init__(self):
        self.StatusCode = 0          # 回傳狀態碼
        self.Message = ""          # 錯誤訊息
        self.RawData = ""          # 原始字串
        self.Blocks = []  # List[ForeignBlock]           # 多筆資料可以先存原始字串，解析成 list[ForeignBlock] 後使用 Python list

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
        self.StatusCode = 0          # 回傳狀態碼
        self.Message = ""          # 錯誤訊息
        self.RawData = ""          # 原始字串
        self.Blocks = []  # List[OpenInterest]           # 多筆資料可以先存原始字串，解析成 list[OpenInterest] 後使用 Python list

class OFOpenInterest(Structure):
    _fields_ = [
        ("Account", c_char_p),               # 帳號
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
        self.StatusCode = 0          # 回傳狀態碼
        self.Message = ""          # 錯誤訊息
        self.RawData = ""          # 原始字串
        self.Blocks = []  # List[OFOpenInterest]           # 多筆資料可以先存原始字串，解析成 list[OFOpenInterest] 後使用 Python list

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
        self.StatusCode = 0          # 回傳狀態碼
        self.Message = ""          # 錯誤訊息
        self.RawData = ""          # 原始字串
        self.Blocks = []  # List[RealBalanceReport]           # 多筆資料可以先存原始字串，解析成 list[RealBalanceReport] 後使用 Python list
      
class FutureRights(Structure):
    _fields_ = [
        ("AccountBalance", c_char_p),            # 帳戶餘額
        ("FloatingPL", c_char_p),                # 浮動損益
        ("RealizedFee", c_char_p),               # 已實現費用
        ("TransactionTax", c_char_p),            # 交易稅
        ("WithheldPremium", c_char_p),           # 預扣權利金
        ("PremiumPayment", c_char_p),            # 權利金收付
        ("Equity", c_char_p),                    # 權益數
        ("ExcessMargin", c_char_p),              # 超額保證金
        ("DepositWithdrawal", c_char_p),         # 存提款
        ("BuyerMarketValue", c_char_p),          # 買方市值
        ("SellerMarketValue", c_char_p),         # 賣方市值
        ("FuturesClosePL", c_char_p),            # 期貨平倉損益
        ("IntradayUnrealized", c_char_p),        # 盤中未實現
        ("InitialMargin", c_char_p),             # 原始保證金
        ("MaintenanceMargin", c_char_p),         # 維持保證金
        ("PositionInitialMargin", c_char_p),     # 部位原始保證金
        ("PositionMaintenanceMargin", c_char_p), # 部位維持保證金
        ("OrderMargin", c_char_p),               # 委託保證金
        ("ExcessOptimalMargin", c_char_p),       # 超額最佳保證金
        ("TotalPremiumValue", c_char_p),         # 權利總值
        ("WithheldFee", c_char_p),               # 預扣費用
        ("OriginalInitialMargin", c_char_p),     # 原始保證金
        ("YesterdayBalance", c_char_p),          # 昨日餘額
        ("OptionComboMarginFlag", c_char_p),     # 選擇權組合單加不加收保證金
        ("MaintenanceRate", c_char_p),           # 維持率
        ("Currency", c_char_p),                  # 幣別
        ("FullInitialMargin", c_char_p),         # 足額原始保證金
        ("FullMaintenanceMargin", c_char_p),     # 足額維持保證金
        ("FullAvailable", c_char_p),             # 足額可用
        ("OffsetAmount", c_char_p),              # 抵繳金額
        ("SecuritiesAvailable", c_char_p),       # 有價可用
        ("AvailableBalance", c_char_p),          # 可用餘額
        ("FullCashAvailable", c_char_p),         # 足額現金可用
        ("SecuritiesValue", c_char_p),           # 有價價值
        ("RiskIndicator", c_char_p),             # 風險指標
        ("OptionExpiryDifference", c_char_p),    # 選擇權到期差異
        ("OptionExpiryPL", c_char_p),            # 選擇權到期差損
        ("FuturesExpiryPL", c_char_p),           # 期貨到期損益
        ("AdditionalMargin", c_char_p),          # 加收保證金
        ("LoginID", c_char_p),                   # LOGIN_ID
        ("AccountNo", c_char_p),                 # ACCOUNT_NO

        ("StatusCode", c_int),                   # 回傳狀態碼
        ("Message", c_char_p),                   # 錯誤訊息
        ("RawData", c_char_p)                    # 原始字串
    ]

class FutureRightsParserResult:
    def __init__(self):
        self.StatusCode = 0          # 回傳狀態碼
        self.Message = ""          # 錯誤訊息
        self.RawData = ""          # 原始字串
        self.Blocks = []  # List[FutureRights]           # 多筆資料可以先存原始字串，解析成 list[FutureRights] 後使用 Python list

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

        ("StatusCode", c_int),                   # 回傳狀態碼
        ("Message", c_char_p),                   # 錯誤訊息
        ("RawData", c_char_p)                    # 原始字串
    ]

class OFFutureRightsParserResult:
    def __init__(self):
        self.StatusCode = 0          # 回傳狀態碼
        self.Message = ""          # 錯誤訊息
        self.RawData = ""          # 原始字串
        self.Blocks = []  # List[OFFutureRights]           # 多筆資料可以先存原始字串，解析成 list[OFFutureRights] 後使用 Python list


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

    KeyNo                      = _lazy(0, "KeyNo")
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
    dll_path = os.path.join(os.path.dirname(__file__), "libs", "SKCOM.dll")
    _dll = ctypes.WinDLL(dll_path)


    # === Corresponding LOGINGW structure ===
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
            strCustCertID=cert,
            strPath=path
        )
        login_struct = login_obj.to_ctypes()

        ACCOUNT_BUFFER_SIZE = 4096
        account_buf = create_string_buffer(ACCOUNT_BUFFER_SIZE)

        code = SK._dll.SKCenterLib_Login(byref(login_struct), account_buf, ACCOUNT_BUFFER_SIZE)
        raw_account = account_buf.value.decode("ansi")
        return LoginResult(
            code=code,
            raw_account_data=raw_account,
            ts_accounts=parse_accounts(raw_account, id_, "TS"),
            os_accounts=parse_accounts(raw_account, id_, "OS"),
            tf_accounts=parse_accounts(raw_account, id_, "TF"),
            of_accounts=parse_accounts(raw_account, id_, "OF"),
        )
    @staticmethod
    def SKCenterLib_Login(login_struct: LOGINGW) -> int:
        return SK._dll.SKCenterLib_Login(login_struct.to_ctypes())

    @staticmethod
    def ManageServerConnection(login_id: str, status: int, target_type: int) -> int:
        return SK._dll.ManageServerConnection(login_id.encode("utf-8"), status, target_type)

    @staticmethod
    def LoadCommodity(nMarketNo: int) -> int:
        return SK._dll.LoadCommodity(nMarketNo)

    @staticmethod
    def RequestStockList(nMarketNo: int):
        ptr = SK._dll.SKQuoteLib_RequestStockList(nMarketNo)
        raw = ctypes.cast(ptr, ctypes.c_char_p).value
        decoded = raw.decode("ansi") if raw else ""
        return StockListParser(decoded)

    @staticmethod
    def GetMessage(code: int) -> str:
        """
        Corresponds to C# GetMessage(int code):
        Returns the error message string based on the error code
        """
        ptr = SK._dll.SKCenterLib_GetReturnCodeMessage(code)
        return ptr.decode("ansi") if ptr else ""

    @staticmethod
    def SendStockProxyOrder(*args):
        """
        Supports overloads:
        - (loginID: str, order: STOCKPROXYORDER2)
        - (loginID: str, stockNo: str, fullAccount: str, price: str, orderType: str, specialTradeType: int, tradeType: int, period: int, qty: int)
        - (loginID: str, stockNo: str, fullAccount: str, price: str, orderType: str, specialTradeType: int, tradeType: int, period: int, qty: int, priceMark: int)
        """
        if len(args) == 2 and isinstance(args[1], STOCKPROXYORDER2):
            return SK._send_internal(args[0], args[1])

        elif len(args) == 9:
            loginID, stockNo, fullAccount, price, orderType, specialTradeType, tradeType, period, qty = args
            order = STOCKPROXYORDER2(
                strStockNo=stockNo.encode('ansi'),
                strFullAccount=fullAccount.encode('ansi'),
                #strSeqNo=None,
                #strBookNo=None,
                strPrice=price.encode('ansi'),
                strOrderType=orderType.encode('ansi'),
                nSpecialTradeType=specialTradeType,
                nTradeType=tradeType,
                nPeriod=period,
                nQty=qty,
                #nPriceMark=0,
                #strPrice_forD=None,
                #strBuySell_forD=None,
                #nPrime=3, # 0=T,1=O,2=P
                #strOrderType2=None
            )
            return SK._send_internal(loginID, order)

        elif len(args) == 10:
            loginID, stockNo, fullAccount, price, orderType, specialTradeType, tradeType, period, qty, priceMark = args
            order = STOCKPROXYORDER2(
                strStockNo=stockNo.encode('ansi'),
                strFullAccount=fullAccount.encode('ansi'),
                #strSeqNo=None,
                #strBookNo=None,
                strPrice=price.encode('ansi'),
                strOrderType=orderType.encode('ansi'),
                nSpecialTradeType=specialTradeType,
                nTradeType=tradeType,
                nPeriod=period,
                nQty=qty,
                nPriceMark=priceMark,
                #strPrice_forD=None,
                #strBuySell_forD=None,
                #nPrime=3, # 0=T,1=O,2=P
                #strOrderType2=None
            )
            return SK._send_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendStockProxyOrder")

    @staticmethod
    def _send_internal(loginID: str, order: STOCKPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendStockProxyOrder(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SendStockProxyAlter(*args):
        """
        Supports overloads:
        - (loginID: str, order: STOCKPROXYORDER2)
        - (loginID: str, stockNo: str, fullAccount: str, seqNo: str, bookNo: str, price: str, orderType: str, specialTradeType: int, tradeType: int, period: int, qty: int)
        - (loginID: str, stockNo: str, fullAccount: str, seqNo: str, bookNo: str, price: str, orderType: str, specialTradeType: int, tradeType: int, period: int, qty: int, priceMark: int)
        """
        if len(args) == 2 and isinstance(args[1], STOCKPROXYORDER2):
            return SK._send_alter_internal(args[0], args[1])

        elif len(args) == 11:
            loginID, stockNo, fullAccount, seqNo, bookNo, price, orderType, specialTradeType, tradeType, period, qty = args
            order = STOCKPROXYORDER2(
                strStockNo=stockNo.encode('ansi'),
                strFullAccount=fullAccount.encode('ansi'),
                strSeqNo=seqNo.encode('ansi'),
                strBookNo=bookNo.encode('ansi'),
                strPrice=price.encode('ansi'),
                strOrderType=orderType.encode('ansi'),
                nSpecialTradeType=specialTradeType,
                nTradeType=tradeType,
                nPeriod=period,
                nQty=qty,
                #nPriceMark=0,
                #strPrice_forD=None,
                #strBuySell_forD=None,
                #nPrime=3, # 0=T,1=O,2=P
                #strOrderType2=None
            )
            return SK._send_alter_internal(loginID, order)

        elif len(args) == 12:
            loginID, stockNo, fullAccount, seqNo, bookNo, price, orderType, specialTradeType, tradeType, period, qty, priceMark = args
            order = STOCKPROXYORDER2(
                strStockNo=stockNo.encode('ansi'),
                strFullAccount=fullAccount.encode('ansi'),
                strSeqNo=seqNo.encode('ansi'),
                strBookNo=bookNo.encode('ansi'),
                strPrice=price.encode('ansi'),
                strOrderType=orderType.encode('ansi'),
                nSpecialTradeType=specialTradeType,
                nTradeType=tradeType,
                nPeriod=period,
                nQty=qty,
                nPriceMark=priceMark,
                #strPrice_forD=None,
                #strBuySell_forD=None,
                #nPrime=3, # 0=T,1=O,2=P
                #strOrderType2=None
            )
            return SK._send_alter_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendStockProxyAlter")

    @staticmethod
    def _send_alter_internal(loginID: str, order: STOCKPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendStockProxyAlter(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SendFutureProxyOrder(*args):
        """
        Supports overloads:
        - (loginID: str, order: FUTUREPROXYORDER2)
        - (loginID: str, fullAccount: str, stockNo: str, settleYM: str, buySell: int, priceFlag: int, dayTrade: int,
        orderType: str, reserved: int, qty: int, price: str, tradeType: int)
        """
        if len(args) == 2 and isinstance(args[1], FUTUREPROXYORDER2):
            return SK._send_future_proxy_order_internal(args[0], args[1])

        elif len(args) == 12:
            loginID, fullAccount, stockNo, settleYM, buySell, priceFlag, dayTrade, orderType, reserved, qty, price, tradeType = args

            order = FUTUREPROXYORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strStockNo=stockNo.encode("ansi"),
                strSettleYM=settleYM.encode("ansi"),
                nBuySell=buySell,
                nPriceFlag=priceFlag,
                nDayTrade=dayTrade,
                strOrderType=orderType.encode("ansi"),
                nReserved=reserved,
                nQty=qty,
                strPrice=price.encode("ansi"),

                strSeqNo=b"",
                strBookNo=b"",
                strStrike=b"",
                strSettleYM2=b"",
                strStrike2=b"",
                nCP=0,
                strStockNo2=b"",
                nCP2=0,
                nBuySell2=0
            )
            return SK._send_future_proxy_order_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendFutureProxyOrder")

    @staticmethod
    def _send_future_proxy_order_internal(loginID: str, order: FUTUREPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendFutureProxyOrderCLR(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SendFutureProxyAlter(*args):
        """
        Supports overloads:
        - (loginID:str, order:FUTUREPROXYORDER2)
        - (loginID:str, fullAccount:str, orderType:str, price:str, reserved:int,
        qty:int, tradeType:int, bookNo:str, seqNo:str)
        """
        if len(args) == 2 and isinstance(args[1], FUTUREPROXYORDER2):
            return SK._send_future_proxy_alter_internal(args[0], args[1])

        elif len(args) == 9:
            loginID, fullAccount, orderType, price, reserved, qty, tradeType, bookNo, seqNo = args

            order = FUTUREPROXYORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strOrderType=orderType.encode("ansi"),
                strPrice=price.encode("ansi"),
                nReserved=reserved,
                nQty=qty,
                nTradeType=tradeType,
                strBookNo=bookNo.encode("ansi"),
                strSeqNo=seqNo.encode("ansi"),
            )

            return SK._send_future_proxy_alter_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendFutureProxyAlter")

    @staticmethod
    def _send_future_proxy_alter_internal(loginID: str, order: FUTUREPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendFutureProxyAlter(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SendOptionProxyOrder(*args):
        """
        Supports overloads:
        - (loginID:str, order:FUTUREPROXYORDER2)
        - (loginID:str, fullAccount:str, stockNo:str, price:str, settleYM:str,
        strike:str, orderType:str, reserved:int, qty:int, cp:int, buySell:int,
        priceFlag:int, tradeType:int, dayTrade:int)
        """
        if len(args) == 2 and isinstance(args[1], FUTUREPROXYORDER2):
            return SK._send_option_proxy_order_internal(args[0], args[1])

        elif len(args) == 14:
            (loginID, fullAccount, stockNo, price, settleYM, strike, orderType,
            reserved, qty, cp, buySell, priceFlag, tradeType, dayTrade) = args

            order = FUTUREPROXYORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strStockNo=stockNo.encode("ansi"),
                strPrice=price.encode("ansi"),
                strSettleYM=settleYM.encode("ansi"),
                strStrike=strike.encode("ansi"),
                strOrderType=orderType.encode("ansi"),
                nReserved=reserved,
                nQty=qty,
                nCP=cp,
                nBuySell=buySell,
                nPriceFlag=priceFlag,
                nTradeType=tradeType,
                nDayTrade=dayTrade,
            )

            return SK._send_option_proxy_order_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendOptionProxyOrder")

    @staticmethod
    def _send_option_proxy_order_internal(loginID: str, order: FUTUREPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendOptionProxyOrder(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message


    @staticmethod
    def SendDuplexProxyOrder(*args):
        """
        Supports overloads:
        - (loginID: str, order: FUTUREPROXYORDER2)
        - (loginID: str, fullAccount: str, stockNo: str, price: str,
        settleYM: str, strike: str, settleYM2: str, strike2: str,
        orderType: str, reserved: int, qty: int,
        cp: int, buySell: int, stockNo2: str, cp2: int, buySell2: int,
        priceFlag: int, tradeType: int, dayTrade: int)
        """
        if len(args) == 2 and isinstance(args[1], FUTUREPROXYORDER2):
            return SK._send_duplex_proxy_order_internal(args[0], args[1])

        elif len(args) == 19:
            (loginID, fullAccount, stockNo, price, settleYM, strike,
            settleYM2, strike2, orderType, reserved, qty, cp, buySell,
            stockNo2, cp2, buySell2, priceFlag, tradeType, dayTrade) = args

            order = FUTUREPROXYORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strStockNo=stockNo.encode("ansi"),
                strPrice=price.encode("ansi"),
                strSettleYM=settleYM.encode("ansi"),
                strStrike=strike.encode("ansi"),
                strSettleYM2=settleYM2.encode("ansi"),
                strStrike2=strike2.encode("ansi"),
                strOrderType=orderType.encode("ansi"),
                nReserved=reserved,
                nQty=qty,
                nCP=cp,
                nBuySell=buySell,
                strStockNo2=stockNo2.encode("ansi"),
                nCP2=cp2,
                nBuySell2=buySell2,
                nPriceFlag=priceFlag,
                nTradeType=tradeType,
                nDayTrade=dayTrade,
            )

            return SK._send_duplex_proxy_order_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendDuplexProxyOrder")

    @staticmethod
    def _send_duplex_proxy_order_internal(loginID: str, order: FUTUREPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendDuplexProxyOrder(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SendOptionProxyAlter(*args):
        """
        Supports overloads:
        - (loginID: str, order: FUTUREPROXYORDER2)
        - (loginID: str, fullAccount: str, orderType: str,
        price: str, reserved: int, qty: int,
        tradeType: int, bookNo: str, seqNo: str)
        """
        if len(args) == 2 and isinstance(args[1], FUTUREPROXYORDER2):
            return SK._send_option_proxy_alter_internal(args[0], args[1])

        elif len(args) == 9:
            (loginID, fullAccount, orderType, price, reserved, qty,
            tradeType, bookNo, seqNo) = args

            order = FUTUREPROXYORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strOrderType=orderType.encode("ansi"),
                strPrice=price.encode("ansi"),
                nReserved=reserved,
                nQty=qty,
                nTradeType=tradeType,
                strBookNo=bookNo.encode("ansi"),
                strSeqNo=seqNo.encode("ansi"),
            )

            return SK._send_option_proxy_alter_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendOptionProxyAlter")

    @staticmethod
    def _send_option_proxy_alter_internal(loginID: str, order: FUTUREPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendOptionProxyAlter(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message


    @staticmethod
    def SendOverseaFutureProxyOrder(*args):
        """
        Supports overloads:
        - (loginID: str, order: OVERSEAFUTUREORDER2)
        - (loginID: str, fullAccount: str, exchangeNo: str, stockNo: str,
        yearMonth: str, order: str, orderNumerator: str,
        trigger: str, triggerNumerator: str, buySell: int,
        newClose: int, dayTrade: int, tradeType: int,
        specialTradeType: int, qty: int)
        """
        if len(args) == 2 and isinstance(args[1], OVERSEAFUTUREORDER2):
            return SK._send_oversea_future_proxy_order_internal(args[0], args[1])

        elif len(args) == 15:
            (loginID, fullAccount, exchangeNo, stockNo,
            yearMonth, order, orderNumerator,
            trigger, triggerNumerator, buySell,
            newClose, dayTrade, tradeType,
            specialTradeType, qty) = args

            order = OVERSEAFUTUREORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strExchangeNo=exchangeNo.encode("ansi"),
                strStockNo=stockNo.encode("ansi"),
                strYearMonth=yearMonth.encode("ansi"),
                strOrder=order.encode("ansi"),
                strOrderNumerator=orderNumerator.encode("ansi"),
                strTrigger=trigger.encode("ansi"),
                strTriggerNumerator=triggerNumerator.encode("ansi"),
                nBuySell=buySell,
                nNewClose=newClose,
                nDayTrade=dayTrade,
                nTradeType=tradeType,
                nSpecialTradeType=specialTradeType,
                nQty=qty,
                nKind = 0
            )

            return SK._send_oversea_future_proxy_order_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendOverseaFutureProxyOrder")

    @staticmethod
    def _send_oversea_future_proxy_order_internal(loginID: str, order: OVERSEAFUTUREORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendOverseaFutureProxyOrder(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message


    @staticmethod
    def SendOverseaFutureSpreadProxyOrder(*args):
        """
        Supports overloads:
        - (loginID: str, order: OVERSEAFUTUREORDER2)
        - (loginID: str, fullAccount: str, exchangeNo: str, stockNo: str,
        nearMonth: str, farMonth: str, order: str, orderNumerator: str,
        trigger: str, triggerNumerator: str, buySell: int, newClose: int,
        dayTrade: int, tradeType: int, specialTradeType: int, qty: int)
        """
        if len(args) == 2 and isinstance(args[1], OVERSEAFUTUREORDER2):
            return SK._send_oversea_future_spread_proxy_order_internal(args[0], args[1])

        elif len(args) == 16:
            (loginID, fullAccount, exchangeNo, stockNo,
            nearMonth, farMonth, order, orderNumerator,
            trigger, triggerNumerator, buySell, newClose,
            dayTrade, tradeType, specialTradeType, qty) = args

            order = OVERSEAFUTUREORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strExchangeNo=exchangeNo.encode("ansi"),
                strStockNo=stockNo.encode("ansi"),
                strYearMonth=nearMonth.encode("ansi"),
                strYearMonth2=farMonth.encode("ansi"),
                strOrder=order.encode("ansi"),
                strOrderNumerator=orderNumerator.encode("ansi"),
                strTrigger=trigger.encode("ansi"),
                strTriggerNumerator=triggerNumerator.encode("ansi"),
                nBuySell=buySell,
                nNewClose=newClose,
                nDayTrade=dayTrade,
                nTradeType=tradeType,
                nSpecialTradeType=specialTradeType,
                nQty=qty,
                nKind = 0
            )

            return SK._send_oversea_future_spread_proxy_order_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendOverseaFutureSpreadProxyOrder")

    @staticmethod
    def _send_oversea_future_spread_proxy_order_internal(loginID: str, order: OVERSEAFUTUREORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendOverseaFutureSpreadProxyOrder(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message
    @staticmethod
    def SendOverseaFutureProxyAlter(*args):
        """
        Supports overloads:
        - (loginID: str, order: OVERSEAFUTUREORDER2)
        - (loginID: str, fullAccount: str, exchangeNo: str, stockNo: str,
        yearMonth: str, yearMonth2: str, order: str, orderNumerator: str,
        orderDenominator: str, newClose: int, tradeType: int, specialTradeType: int,
        qty: int, bookNo: str, seqNo: str, spreadFlag: int, alterType: int,
        strikePrice: str, callPut: int)
        """
        if len(args) == 2 and isinstance(args[1], OVERSEAFUTUREORDER2):
            return SK._send_oversea_future_proxy_alter_internal(args[0], args[1])

        elif len(args) == 19:
            (loginID, fullAccount, exchangeNo, stockNo,
            yearMonth, yearMonth2, order, orderNumerator,
            orderDenominator, newClose, tradeType, specialTradeType,
            qty, bookNo, seqNo, spreadFlag, alterType,
            strikePrice, callPut) = args

            order = OVERSEAFUTUREORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strExchangeNo=exchangeNo.encode("ansi"),
                strStockNo=stockNo.encode("ansi"),
                strYearMonth=yearMonth.encode("ansi"),
                strYearMonth2=yearMonth2.encode("ansi"),
                strOrder=order.encode("ansi"),
                strOrderNumerator=orderNumerator.encode("ansi"),
                strOrderDenominator=orderDenominator.encode("ansi"),
                nNewClose=newClose,
                nTradeType=tradeType,
                nSpecialTradeType=specialTradeType,
                nQty=qty,
                strBookNo=bookNo.encode("ansi"),
                strSeqNo=seqNo.encode("ansi"),
                nSpreadFlag=spreadFlag,
                nAlterType=alterType,
                strStrikePrice=strikePrice.encode("ansi"),
                nCallPut=callPut,
                nKind = 0
            )

            return SK._send_oversea_future_proxy_alter_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendOverseaFutureProxyAlter")

    @staticmethod
    def _send_oversea_future_proxy_alter_internal(loginID: str, order: OVERSEAFUTUREORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendOverseaFutureProxyAlter(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SendOverseaOptionProxyOrder(*args):
        """
        Supports overloads:
        - (loginID: str, order: OVERSEAFUTUREORDER2)
        - (loginID: str, fullAccount: str, exchangeNo: str, stockNo: str,
        yearMonth: str, order: str, orderNumerator: str, orderDenominator: str,
        trigger: str, triggerNumerator: str, buySell: int, newClose: int, dayTrade: int,
        tradeType: int, specialTradeType: int, strikePrice: str, callPut: int, qty: int)
        """
        if len(args) == 2 and isinstance(args[1], OVERSEAFUTUREORDER2):
            return SK._send_oversea_option_proxy_order_internal(args[0], args[1])

        elif len(args) == 18:
            (loginID, fullAccount, exchangeNo, stockNo, yearMonth,
            order, orderNumerator, orderDenominator, trigger, triggerNumerator,
            buySell, newClose, dayTrade, tradeType, specialTradeType,
            strikePrice, callPut, qty) = args

            order = OVERSEAFUTUREORDER2(
                strFullAccount=fullAccount.encode("ansi"),
                strExchangeNo=exchangeNo.encode("ansi"),
                strStockNo=stockNo.encode("ansi"),
                strYearMonth=yearMonth.encode("ansi"),
                strOrder=order.encode("ansi"),
                strOrderNumerator=orderNumerator.encode("ansi"),
                strOrderDenominator=orderDenominator.encode("ansi"),
                strTrigger=trigger.encode("ansi"),
                strTriggerNumerator=triggerNumerator.encode("ansi"),
                nBuySell=buySell,
                nNewClose=newClose,
                nDayTrade=dayTrade,
                nTradeType=tradeType,
                nSpecialTradeType=specialTradeType,
                strStrikePrice=strikePrice.encode("ansi"),
                nCallPut=callPut,
                nQty=qty,
                nKind = 0
            )

            return SK._send_oversea_option_proxy_order_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendOverseaOptionProxyOrder")

    @staticmethod
    def _send_oversea_option_proxy_order_internal(loginID: str, order: OVERSEAFUTUREORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendOverseaOptionProxyOrder(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

 
    @staticmethod
    def SendForeignStockProxyOrder(*args):
        """
        Supports overloads:
        - (loginID: str, order: OSSTOCKPROXYORDER2)
        - (loginID: str, fullAccount: str, stockNo: str, exchangeNo: str, price: str,
        currency1: str, currency2: str, currency3: str, proxyQty: str,
        accountType: int, orderType: int, tradeType: int)
        """
        if len(args) == 2 and isinstance(args[1], OSSTOCKPROXYORDER2):
            return SK._send_foreign_stock_proxy_order_internal(args[0], args[1])

        elif len(args) == 12:
            (
                loginID, fullAccount, stockNo, exchangeNo, price,
                currency1, currency2, currency3, proxyQty,
                accountType, orderType, tradeType
            ) = args

            order = OSSTOCKPROXYORDER2(
                strFullAccount = fullAccount.encode("ansi"),
                strStockNo = stockNo.encode("ansi"),
                strExchangeNo = exchangeNo.encode("ansi"),
                strPrice = price.encode("ansi"),
                strCurrency1 = currency1.encode("ansi"),
                strCurrency2 = currency2.encode("ansi"),
                strCurrency3 = currency3.encode("ansi"),
                strSeqNo = None,
                strBookNo = None,
                nAccountType = accountType,
                nQty = 0,
                nOrderType = orderType,
                nTradeType = tradeType,
                strProxyQty = proxyQty.encode("ansi")
            )

            return SK._send_foreign_stock_proxy_order_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendForeignStockProxyOrder")

    @staticmethod
    def _send_foreign_stock_proxy_order_internal(loginID: str, order: OSSTOCKPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendForeignStockProxyOrder(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SendForeignStockProxyCancel(*args):
        """
        Supports overloads:
        - (loginID: str, order: OSSTOCKPROXYORDER2)
        - (loginID: str, fullAccount: str, stockNo: str, exchangeNo: str,
        seqNo: str, bookNo: str)
        """
        if len(args) == 2 and isinstance(args[1], OSSTOCKPROXYORDER2):
            return SK._send_foreign_stock_proxy_cancel_internal(args[0], args[1])

        elif len(args) == 6:
            loginID, fullAccount, stockNo, exchangeNo, seqNo, bookNo = args

            order = OSSTOCKPROXYORDER2(
                strFullAccount = fullAccount.encode("ansi"),
                strStockNo = stockNo.encode("ansi"),
                strExchangeNo = exchangeNo.encode("ansi"),
                strSeqNo = seqNo.encode("ansi"),
                strBookNo = bookNo.encode("ansi"),
                strPrice = None,
                strCurrency1 = None,
                strCurrency2 = None,
                strCurrency3 = None,
                strProxyQty = None,
                nAccountType = 0,
                nOrderType = 0,
                nTradeType = 0,
                nQty = 0
            )

            return SK._send_foreign_stock_proxy_cancel_internal(loginID, order)

        else:
            raise TypeError("Invalid arguments passed to SendForeignStockProxyCancel")

    @staticmethod
    def _send_foreign_stock_proxy_cancel_internal(loginID: str, order: OSSTOCKPROXYORDER2):
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendForeignStockProxyCancel(loginID.encode('ansi'), order, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message

    @staticmethod
    def SKQuoteLib_GetStockByStockNo(nMarketNo: int, strStockNo: str) -> 'SK.SKSTOCKLONG2':
  
        SK._dll.SKQuoteLib_GetStockByStockNo.argtypes = [c_int, c_char_p, POINTER(_SKSTOCKLONG2_Internal)]
        SK._dll.SKQuoteLib_GetStockByStockNo.restype = c_int

        internal = _SKSTOCKLONG2_Internal()
        result = SK._dll.SKQuoteLib_GetStockByStockNo(nMarketNo, strStockNo.encode("ansi"), byref(internal))

        return SK.SKSTOCKLONG2(internal, result)

    @staticmethod
    def SKQuoteLib_RequestStocks(strStockNos: str) -> int:
        SK._dll.SKQuoteLib_RequestStocks.argtypes = [c_char_p]
        SK._dll.SKQuoteLib_RequestStocks.restype = c_int

        return SK._dll.SKQuoteLib_RequestStocks(strStockNos.encode("ansi"))

    @staticmethod
    def SKQuoteLib_RequestStocksOddLot(strStockNos: str) -> int:
        SK._dll.SKQuoteLib_RequestStocksOddLot.argtypes = [c_char_p]
        SK._dll.SKQuoteLib_RequestStocksOddLot.restype = c_int

        return SK._dll.SKQuoteLib_RequestStocksOddLot(strStockNos.encode("ansi"))

    @staticmethod
    def SKQuoteLib_CancelRequestStocks(strStockNos: str) -> int:
        SK._dll.SKQuoteLib_CancelRequestStocks.argtypes = [c_char_p]
        SK._dll.SKQuoteLib_CancelRequestStocks.restype = c_int

        return SK._dll.SKQuoteLib_CancelRequestStocks(strStockNos.encode("ansi"))


    @staticmethod
    def SKQuoteLib_RequestTicks(nItemNo:int, strStockNos: str) -> int:
        SK._dll.SKQuoteLib_RequestTicks.argtypes = [c_int, c_char_p]
        SK._dll.SKQuoteLib_RequestTicks.restype = c_int

        return SK._dll.SKQuoteLib_RequestTicks(nItemNo, strStockNos.encode("ansi"))

    @staticmethod
    def SKQuoteLib_RequestTicksOddLot(nItemNo:int, strStockNos: str) -> int:
        SK._dll.SKQuoteLib_RequestTicksOddLot.argtypes = [c_int,c_char_p]
        SK._dll.SKQuoteLib_RequestTicksOddLot.restype = c_int

        return SK._dll.SKQuoteLib_RequestTicksOddLot(nItemNo, strStockNos.encode("ansi"))

    @staticmethod
    def SKQuoteLib_CancelRequestTicks(strStockNos: str) -> int:
        SK._dll.SKQuoteLib_CancelRequestTicks.argtypes = [c_char_p]
        SK._dll.SKQuoteLib_CancelRequestTicks.restype = c_int

        return SK._dll.SKQuoteLib_CancelRequestTicks(strStockNos.encode("ansi"))

    @staticmethod
    def GetForeignBlock(loginID: str, fullAccount: str, nFunc: int) -> ForeignBlockParserResult:
        result = ForeignBlockParserResult()
        BUFFER_SIZE = 8192
        buffer = create_string_buffer(BUFFER_SIZE)

        code = SK._dll.GetForeignBlock(
            loginID.encode("ansi"),
            fullAccount.encode("ansi"),
            nFunc,
            buffer,
            BUFFER_SIZE
        )
        result.StatusCode = code
        result.RawData = buffer.value.decode("ansi")

        if code != 0:
            result.Message = result.RawData
            return result

        data = result.RawData.rstrip('#')
        records = data.split('#')

        for record in records:
            tokens = record.split(',')
            if len(tokens) < 11:
                continue
            try:
                block = ForeignBlock()
                block.BankCode = tokens[0].encode("ansi")
                block.BankBranchCode = tokens[1].encode("ansi")
                block.BankAccount = tokens[2].encode("ansi")
                block.BankName = tokens[3].encode("ansi")
                block.Currency = tokens[4].encode("ansi")
                block.UnpayableAmt = tokens[5].encode("ansi")
                block.UnpayableBuy = tokens[6].encode("ansi")
                block.TodayOrder = tokens[7].encode("ansi")
                block.OutAmt = tokens[8].encode("ansi")
                block.UnblockAmt = tokens[9].encode("ansi")
                block.FundOrderAmt = tokens[10].encode("ansi")
                result.Blocks.append(block)
            except Exception as ex:
                result.StatusCode = -1
                result.Message = f"解析資料失敗: {ex}"
                break

        return result

    @staticmethod
    def WithDraw(strLogInID:str, strFullAccountOut: str, nTypeOut:int, strFullAccountIn: str, nTypeIn:int, nCurrency:int, strDollars:str, strPassword: str) -> int:
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.WithDraw(strLogInID.encode('ansi'), strFullAccountOut.encode('ansi'), nTypeOut, strFullAccountIn.encode('ansi'), nTypeIn, nCurrency, strDollars.encode('ansi'), strPassword.encode('ansi'), message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message
    
    @staticmethod
    def SendTFOffset(strLogInID:str, strAccount: str, nCommodity:int, strYearMonth: str, nBuySell:int, nQty:int, nQty2:str, nQty3: str) -> int:
        MESSAGE_BUFFER_SIZE = 1024
        message_buf = create_string_buffer(MESSAGE_BUFFER_SIZE)
        code = SK._dll.SendTFOffset(strLogInID.encode('ansi'), strAccount.encode('ansi'), nCommodity, strYearMonth.encode('ansi'), nBuySell, nQty, nQty2, nQty3, message_buf, MESSAGE_BUFFER_SIZE)
        message = message_buf.value.decode("ansi")

        return code, message
    
    @staticmethod
    def GetOpenInterestGW(loginID: str, fullAccount: str, nFormat: int) -> OpenInterestParserResult:
        result = OpenInterestParserResult()
        BUFFER_SIZE = 1024 * 1024
        buffer = create_string_buffer(BUFFER_SIZE)

        code = SK._dll.GetOpenInterestGW(
            loginID.encode("ansi"),
            fullAccount.encode("ansi"),
            nFormat,
            buffer,
            BUFFER_SIZE
        )
        result.StatusCode = code
        result.RawData = buffer.value.decode("ansi")

        if code != 0:
            result.Message = result.RawData
            return result

        data = result.RawData.rstrip('#')
        records = data.split('#')

        for record in records:
            tokens = record.split(',')
            if len(tokens) < 10:
                continue
            try:
                block = OpenInterest()
                block.MarketType = tokens[0].encode("ansi")
                block.Account = tokens[1].encode("ansi")
                block.FutureNo = tokens[2].encode("ansi")
                block.BuySell = tokens[3].encode("ansi")
                block.Qty = tokens[4].encode("ansi")
                block.Qty_Trade = tokens[5].encode("ansi")
                block.AvgPrice = tokens[6].encode("ansi")
                block.Fee = tokens[7].encode("ansi")
                block.Tax = tokens[8].encode("ansi")
                block.LoginID = tokens[9].encode("ansi")
                result.Blocks.append(block)
            except Exception as ex:
                result.StatusCode = -1
                result.Message = f"解析資料失敗: {ex}"
                break

        return result
    
    @staticmethod
    def GetOFOpenInterestGW(loginID: str, fullAccount: str, nFunc: int) -> OFOpenInterestParserResult:
        result = OFOpenInterestParserResult()
        BUFFER_SIZE = 1024 * 1024
        buffer = create_string_buffer(BUFFER_SIZE)

        code = SK._dll.GetOFOpenInterestGW(
            loginID.encode("ansi"),
            fullAccount.encode("ansi"),
            nFunc,
            buffer,
            BUFFER_SIZE
        )
        result.StatusCode = code
        result.RawData = buffer.value.decode("ansi")

        if code != 0:
            result.Message = result.RawData
            return result

        data = result.RawData.rstrip('#')
        records = data.split('#')

        for record in records:
            tokens = record.split(',')
            if len(tokens) < 24:
                continue
            try:
                block = OFOpenInterest()
                block.Account = tokens[0].encode("ansi")
                block.ExchangeCode = tokens[1].encode("ansi")
                block.ExchangeName = tokens[2].encode("ansi")
                block.ProductCodeWithYM = tokens[3].encode("ansi")
                block.ProductCode = tokens[4].encode("ansi")
                block.ProductYM = tokens[5].encode("ansi")
                block.ProductNameWithYM = tokens[6].encode("ansi")
                block.BuySell = tokens[7].encode("ansi")
                block.OpenInterest = tokens[8].encode("ansi")
                block.AvgPrice = tokens[9].encode("ansi")
                block.MarketPrice = tokens[10].encode("ansi")
                block.UnrealizedPL = tokens[11].encode("ansi")
                block.BidPrice = tokens[12].encode("ansi")
                block.BidVolume = tokens[13].encode("ansi")
                block.AskPrice = tokens[14].encode("ansi")
                block.AskVolume = tokens[15].encode("ansi")
                block.AskNewOpenVolume = tokens[16].encode("ansi")
                block.PrevSettlementPrice = tokens[17].encode("ansi")
                block.DayTradeOpenInterest = tokens[18].encode("ansi")
                block.InitialMargin = tokens[19].encode("ansi")
                block.IsOption = tokens[20].encode("ansi")
                block.StrikePrice = tokens[21].encode("ansi")
                block.CallPut = tokens[22].encode("ansi")
                block.LoginID = tokens[23].encode("ansi")
                result.Blocks.append(block)
            except Exception as ex:
                result.StatusCode = -1
                result.Message = f"解析資料失敗: {ex}"
                break

        return result
    
    @staticmethod
    def GetRealBalanceReport(loginID: str, fullAccount: str) -> RealBalanceReportParserResult:
        result = RealBalanceReportParserResult()
        BUFFER_SIZE = 1024 * 1024
        buffer = create_string_buffer(BUFFER_SIZE)

        code = SK._dll.GetRealBalanceReport(
            loginID.encode("ansi"),
            fullAccount.encode("ansi"),
            buffer,
            BUFFER_SIZE
        )
        result.StatusCode = code
        result.RawData = buffer.value.decode("ansi")

        if code != 0:
            result.Message = result.RawData
            return result

        data = result.RawData.rstrip('#')
        records = data.split('#')

        for record in records:
            tokens = record.split(',')
            if len(tokens) < 18:
                continue
            try:
                block = RealBalanceReport()
                block.StockCode = tokens[0].encode("ansi")
                block.InventoryType = tokens[1].encode("ansi")
                block.CreditLimitOriginal = tokens[2].encode("ansi")
                block.CreditLimitAvailable = tokens[3].encode("ansi")
                block.ShortLimitOriginal = tokens[4].encode("ansi")
                block.ShortLimitAvailable = tokens[5].encode("ansi")
                block.YesterdayInventory = tokens[6].encode("ansi")
                block.TodayBidQty = tokens[7].encode("ansi")
                block.TodayAskQty = tokens[8].encode("ansi")
                block.TodayBuyMatched = tokens[9].encode("ansi")
                block.TodaySellMatched = tokens[10].encode("ansi")
                block.AvailableToSellOrCover = tokens[11].encode("ansi")
                block.DayTradeBuyableQty = tokens[12].encode("ansi")
                block.DayTradeSellableQty = tokens[13].encode("ansi")
                block.RealTimeInventory = tokens[14].encode("ansi")
                block.RealTimeMarginRate = tokens[15].encode("ansi")
                block.LoginID = tokens[16].encode("ansi")
                block.AccountNo = tokens[17].encode("ansi")
                result.Blocks.append(block)
            except Exception as ex:
                result.StatusCode = -1
                result.Message = f"解析資料失敗: {ex}"
                break

        return result
    
    @staticmethod
    def GetFutureRights(loginID: str, fullAccount: str, nFunc: int) -> FutureRightsParserResult:
        result = FutureRightsParserResult()
        BUFFER_SIZE = 1024 * 1024
        buffer = create_string_buffer(BUFFER_SIZE)

        code = SK._dll.GetFutureRights(
            loginID.encode("ansi"),
            fullAccount.encode("ansi"),
            nFunc,
            buffer,
            BUFFER_SIZE
        )
        result.StatusCode = code
        result.RawData = buffer.value.decode("ansi")

        if code != 0:
            result.Message = result.RawData
            return result

        data = result.RawData.rstrip('#')
        records = data.split('#')

        for record in records:
            tokens = record.split(',')
            if len(tokens) < 41:
                continue
            try:
                block = RealBalanceReport()
                block.AccountBalance = tokens[0].encode("ansi")
                block.FloatingPL = tokens[1].encode("ansi")
                block.RealizedFee = tokens[2].encode("ansi")
                block.TransactionTax = tokens[3].encode("ansi")
                block.WithheldPremium = tokens[4].encode("ansi")
                block.PremiumPayment = tokens[5].encode("ansi")
                block.Equity = tokens[6].encode("ansi")
                block.ExcessMargin = tokens[7].encode("ansi")
                block.DepositWithdrawal = tokens[8].encode("ansi")
                block.BuyerMarketValue = tokens[9].encode("ansi")
                block.SellerMarketValue = tokens[10].encode("ansi")
                block.FuturesClosePL = tokens[11].encode("ansi")
                block.IntradayUnrealized = tokens[12].encode("ansi")
                block.InitialMargin = tokens[13].encode("ansi")
                block.MaintenanceMargin = tokens[14].encode("ansi")
                block.PositionInitialMargin = tokens[15].encode("ansi")
                block.PositionMaintenanceMargin = tokens[16].encode("ansi")
                block.OrderMargin = tokens[17].encode("ansi")
                block.ExcessOptimalMargin = tokens[18].encode("ansi")
                block.TotalPremiumValue = tokens[19].encode("ansi")
                block.WithheldFee = tokens[20].encode("ansi")
                block.OriginalInitialMargin = tokens[21].encode("ansi")
                block.YesterdayBalance = tokens[22].encode("ansi")
                block.OptionComboMarginFlag = tokens[23].encode("ansi")
                block.MaintenanceRate = tokens[24].encode("ansi")
                block.Currency = tokens[25].encode("ansi")
                block.FullInitialMargin = tokens[26].encode("ansi")
                block.FullMaintenanceMargin = tokens[27].encode("ansi")
                block.FullAvailable = tokens[28].encode("ansi")
                block.OffsetAmount = tokens[29].encode("ansi")
                block.SecuritiesAvailable = tokens[30].encode("ansi")
                block.AvailableBalance = tokens[31].encode("ansi")
                block.FullCashAvailable = tokens[32].encode("ansi")
                block.SecuritiesValue = tokens[33].encode("ansi")
                block.RiskIndicator = tokens[34].encode("ansi")
                block.OptionExpiryDifference = tokens[35].encode("ansi")
                block.OptionExpiryPL = tokens[36].encode("ansi")
                block.FuturesExpiryPL = tokens[37].encode("ansi")
                block.AdditionalMargin = tokens[38].encode("ansi")
                block.LoginID = tokens[39].encode("ansi")
                block.AccountNo = tokens[40].encode("ansi")
                result.Blocks.append(block)
            except Exception as ex:
                result.StatusCode = -1
                result.Message = f"解析資料失敗: {ex}"
                break

        return result
    
    @staticmethod
    def GetOFFutureRights(loginID: str, fullAccount: str, nFunc: int) -> FutureRightsParserResult:
        result = OFFutureRightsParserResult()
        BUFFER_SIZE = 1024 * 1024
        buffer = create_string_buffer(BUFFER_SIZE)

        code = SK._dll.GetOFFutureRights(
            loginID.encode("ansi"),
            fullAccount.encode("ansi"),
            nFunc,
            buffer,
            BUFFER_SIZE
        )
        result.StatusCode = code
        result.RawData = buffer.value.decode("ansi")

        if code != 0:
            result.Message = result.RawData
            return result

        data = result.RawData.rstrip('#')
        records = data.split('#')

        for record in records:
            tokens = record.split(',')
            if len(tokens) < 30:
                continue
            try:
                block = OFFutureRights()
                block.LoginID = tokens[0].encode("ansi")                  # LOGIN_ID
                block.AccountNo = tokens[1].encode("ansi")               # 帳號
                block.Currency = tokens[2].encode("ansi")                # 幣別
                block.RiskIndicator = tokens[3].encode("ansi")           # 風險指標/維持率
                block.FullMaintenanceMargin = tokens[4].encode("ansi")   # 足額維持率
                block.WithdrawableMargin = tokens[5].encode("ansi")      # 可動用(出金)保證金
                block.OrderMargin = tokens[6].encode("ansi")             # 委託保證金
                block.MaintenanceMargin = tokens[7].encode("ansi")       # 維持保證金
                block.InitialMargin = tokens[8].encode("ansi")           # 原始保證金
                block.NetEquity = tokens[9].encode("ansi")               # 淨值權益數、權益總值
                block.WithheldPremium = tokens[10].encode("ansi")        # 預扣權利金
                block.OptionLongMarketValue = tokens[11].encode("ansi")  # 未沖銷買方選擇權市值
                block.OptionShortMarketValue = tokens[12].encode("ansi") # 未沖銷賣方選擇權市值
                block.AccountEquity = tokens[13].encode("ansi")          # 帳戶權益、權益數
                block.IntradayUnrealized = tokens[14].encode("ansi")     # 盤中未實現
                block.FuturesFloatingPL = tokens[15].encode("ansi")      # 未沖銷期貨浮動損益
                block.PremiumPaidToday = tokens[16].encode("ansi")       # 今日權利金支付
                block.FuturesClosePLToday = tokens[17].encode("ansi")    # 本日期貨平倉損益淨額
                block.RealizedFee = tokens[18].encode("ansi")            # 已實現費用、手續費
                block.DepositWithdrawalToday = tokens[19].encode("ansi") # 今日存提款
                block.PreviousDayBalance = tokens[20].encode("ansi")     # 前日帳戶餘額
                block.ReferenceRate = tokens[21].encode("ansi")          # 參考匯率
                block.OptionExpiryGain = tokens[22].encode("ansi")       # 選擇權到期差益
                block.OptionExpiryLoss = tokens[23].encode("ansi")       # 選擇權到期差損
                block.FuturesDeliveryPL = tokens[24].encode("ansi")      # 期貨交割損益
                block.ExcessOrMarginCall = tokens[25].encode("ansi")     # 超額/追繳保證金
                block.ExerciseSettlementPL = tokens[26].encode("ansi")   # 到期履約損益
                block.AccountBalance = tokens[27].encode("ansi")         # 帳戶餘額
                block.FixedMargin = tokens[28].encode("ansi")            # 固定保證金
                block.VariableMargin = tokens[29].encode("ansi")         # 變動保證金
                result.Blocks.append(block)
            except Exception as ex:
                result.StatusCode = -1
                result.Message = f"解析資料失敗: {ex}"
                break

        return result
    
    # === OnProxyOrder ===
    _proxy_order_subscribers: List[Callable[[int, int, str], None]] = []
    _native_proxy_order_callback = None

    # callback prototype：int, int, string
    _PROXY_ORDER_CALLBACK_TYPE = WINFUNCTYPE(None, c_int, c_int, c_char_p)

    @staticmethod
    def _handle_proxy_order(stamp_id, code, message_ptr):
        try:
            message = message_ptr.decode("utf-8") if message_ptr else ""
        except UnicodeDecodeError:
            try:
                message = message_ptr.decode("mbcs")
            except Exception:
                message = "<DecodeError>"
        for callback in SK._proxy_order_subscribers:
            callback(stamp_id, code, message)

    @staticmethod
    def InitializeProxyOrderListener():
        if SK._native_proxy_order_callback is None:
            SK._native_proxy_order_callback = SK._PROXY_ORDER_CALLBACK_TYPE(SK._handle_proxy_order)
            SK._dll.RegisterEventOnProxyOrder(SK._native_proxy_order_callback)

    @staticmethod
    def OnProxyOrder(callback: Callable[[int, int, str], None]):
        SK.InitializeProxyOrderListener()
        SK._proxy_order_subscribers.append(callback)

    _dll.RegisterEventOnProxyOrder.argtypes = [_PROXY_ORDER_CALLBACK_TYPE]
    _dll.RegisterEventOnProxyOrder.restype = None

    # === OnConnection ===
    _on_connection_handlers: List[Callable[[str, int], None]] = []
    _is_connection_initialized = False
    _native_connection_callback = None
    _CONNECTION_CALLBACK_TYPE = WINFUNCTYPE(None, c_char_p, c_int)

    @staticmethod
    def _handle_connection(login_id_ptr, code):
        login_id = login_id_ptr.decode("ansi")
        for handler in SK._on_connection_handlers:
            handler(login_id, code)

    @staticmethod
    def _initialize_connection_listener():
        if not SK._is_connection_initialized:
            SK._native_connection_callback = SK._CONNECTION_CALLBACK_TYPE(SK._handle_connection)
            SK._dll.RegisterEventOnConnection(SK._native_connection_callback)
            SK._is_connection_initialized = True

    class _ConnectionEvent:
        def __call__(self, handler: Callable[[str, int], None]):
            SK._initialize_connection_listener()
            SK._on_connection_handlers.append(handler)

        def remove_handler(self, handler: Callable[[str, int], None]):
            if handler in SK._on_connection_handlers:
                SK._on_connection_handlers.remove(handler)

    OnConnection = _ConnectionEvent()

    # === OnComplete ===
    _on_complete_handlers: List[Callable[[str], None]] = []
    _is_complete_initialized = False
    _native_complete_callback = None
    _COMPLETE_CALLBACK_TYPE = WINFUNCTYPE(None, c_char_p)

    @staticmethod
    def _handle_complete(login_id_ptr):
        login_id = login_id_ptr.decode("ansi")
        for handler in SK._on_complete_handlers:
            handler(login_id)

    @staticmethod
    def _initialize_complete_listener():
        if not SK._is_complete_initialized:
            SK._native_complete_callback = SK._COMPLETE_CALLBACK_TYPE(SK._handle_complete)
            SK._dll.RegisterEventOnComplete(SK._native_complete_callback)
            SK._is_complete_initialized = True

    class _CompleteEvent:
        def __call__(self, handler: Callable[[str], None]):
            SK._initialize_complete_listener()
            SK._on_complete_handlers.append(handler)

        def remove_handler(self, handler: Callable[[str], None]):
            if handler in SK._on_complete_handlers:
                SK._on_complete_handlers.remove(handler)

    OnComplete = _CompleteEvent()

    # === OnNewData ===
    _on_new_data_handlers: List[Callable[[str, OrderFulfillData], None]] = []
    _on_new_order_handlers: List[Callable[[str, OrderFulfillData], None]] = []
    _on_new_fulfill_handlers: List[Callable[[str, OrderFulfillData], None]] = []

    _is_new_data_initialized = False
    _native_new_data_callback = None
    _NEW_DATA_CALLBACK_TYPE = WINFUNCTYPE(None, c_char_p, c_char_p)

    _order_queue = queue.Queue()
    _fulfill_queue = queue.Queue()

    @staticmethod
    def _handle_new_data(login_id_ptr, data_ptr):
        login_id = login_id_ptr.decode("ansi")
        data = data_ptr.decode("ansi")

        parsed_data = OrderFulfillData(data)
        for handler in SK._on_new_data_handlers:
            handler(login_id, parsed_data)

        fields = data.split(',')
        report_type = fields[2].strip() if len(fields) > 2 else ""
        if report_type == "D":
            SK._fulfill_queue.put((login_id, data))
        else:
            SK._order_queue.put((login_id, data))

    @staticmethod
    def _process_order_data():
        while True:
            login_id, data = SK._order_queue.get()
            parsed_data = OrderFulfillData(data)
            for handler in SK._on_new_order_handlers:
                handler(login_id, parsed_data)

    @staticmethod
    def _process_fulfill_data():
        while True:
            login_id, data = SK._fulfill_queue.get()
            parsed_data = OrderFulfillData(data)
            for handler in SK._on_new_fulfill_handlers:
                handler(login_id, parsed_data)

    @staticmethod
    def _initialize_new_data_listener():
        if not SK._is_new_data_initialized:
            SK._native_new_data_callback = SK._NEW_DATA_CALLBACK_TYPE(SK._handle_new_data)
            SK._dll.RegisterEventOnNewData(SK._native_new_data_callback)

            threading.Thread(target=SK._process_order_data, daemon=True).start()
            threading.Thread(target=SK._process_fulfill_data, daemon=True).start()

            SK._is_new_data_initialized = True

    class _NewDataEvent:
        def __call__(self, handler: Callable[[str, OrderFulfillData], None]):
            SK._initialize_new_data_listener()
            SK._on_new_data_handlers.append(handler)

        def remove_handler(self, handler: Callable[[str, OrderFulfillData], None]):
            if handler in SK._on_new_data_handlers:
                SK._on_new_data_handlers.remove(handler)

    class _NewOrderDataEvent:
        def __call__(self, handler: Callable[[str, OrderFulfillData], None]):
            SK._initialize_new_data_listener()
            SK._on_new_order_handlers.append(handler)

        def remove_handler(self, handler: Callable[[str, OrderFulfillData], None]):
            if handler in SK._on_new_order_handlers:
                SK._on_new_order_handlers.remove(handler)

    class _NewFulfillDataEvent:
        def __call__(self, handler: Callable[[str, OrderFulfillData], None]):
            SK._initialize_new_data_listener()
            SK._on_new_fulfill_handlers.append(handler)

        def remove_handler(self, handler: Callable[[str, OrderFulfillData], None]):
            if handler in SK._on_new_fulfill_handlers:
                SK._on_new_fulfill_handlers.remove(handler)

    OnNewData = _NewDataEvent()
    OnNewOrderData = _NewOrderDataEvent()
    OnNewFulfillData = _NewFulfillDataEvent()

    # === OnNotifyBest5LONG ===
    _on_notify_best5_long_handlers: List[Callable[[int, str, list, list, list, list, int, int, int, int, int], None]] = []
    _is_notify_best5_long_initialized = False
    _native_notify_best5_long_callback = None

    _NOTIFY_BEST5_LONG_CALLBACK_TYPE = WINFUNCTYPE(
        None,
        c_int, c_char_p,            # market_no, stockno
        c_int, c_int, c_int, c_int, c_int, c_int, c_int, c_int, c_int, c_int,  # bid1-5, bidQty1-5
        c_int, c_int,            # extend_bid, extend_bid_qty
        c_int, c_int, c_int, c_int, c_int, c_int, c_int, c_int, c_int, c_int,  # ask1-5, askQty1-5
        c_int, c_int,            # extend_ask, extend_ask_qty
        c_int                    # simulate
    )

    @staticmethod
    def _handle_notify_best5_long(
        market_no, stockno,
        bid1, bid_qty1, bid2, bid_qty2, bid3, bid_qty3, bid4, bid_qty4, bid5, bid_qty5,
        extend_bid, extend_bid_qty,
        ask1, ask_qty1, ask2, ask_qty2, ask3, ask_qty3, ask4, ask_qty4, ask5, ask_qty5,
        extend_ask, extend_ask_qty,
        simulate
    ):
        best_bids = [bid1, bid2, bid3, bid4, bid5]
        bid_qtys = [bid_qty1, bid_qty2, bid_qty3, bid_qty4, bid_qty5]
        best_asks = [ask1, ask2, ask3, ask4, ask5]
        ask_qtys = [ask_qty1, ask_qty2, ask_qty3, ask_qty4, ask_qty5]

        for handler in SK._on_notify_best5_long_handlers:
            handler(market_no, stockno, best_bids, bid_qtys, best_asks, ask_qtys,
                    extend_bid, extend_bid_qty, extend_ask, extend_ask_qty, simulate)

    @staticmethod
    def _initialize_notify_best5_long_listener():
        if not SK._is_notify_best5_long_initialized:
            SK._native_notify_best5_long_callback = SK._NOTIFY_BEST5_LONG_CALLBACK_TYPE(SK._handle_notify_best5_long)
            SK._dll.RegisterEventOnNotifyBest5LONG(SK._native_notify_best5_long_callback)
            SK._is_notify_best5_long_initialized = True

    class _NotifyBest5LONGEvent:
        def __call__(self, handler: Callable[[int, str, list, list, list, list, int, int, int, int, int], None]):
            SK._initialize_notify_best5_long_listener()
            SK._on_notify_best5_long_handlers.append(handler)

        def remove_handler(self, handler: Callable):
            if handler in SK._on_notify_best5_long_handlers:
                SK._on_notify_best5_long_handlers.remove(handler)

    OnNotifyBest5LONG = _NotifyBest5LONGEvent()

    # === OnReplyMessage ===
    _on_reply_message_handlers: List[Callable[[str,str], None]] = []
    _is_reply_message_initialized = False
    _native_reply_callback = None
    _REPLY_CALLBACK_TYPE = WINFUNCTYPE(None, c_char_p, c_char_p)

    @staticmethod
    def _handle_reply_message(message_ptr1, message_ptr2):
        message1 = message_ptr1.decode("ansi")
        message2 = message_ptr2.decode("ansi")
        for handler in SK._on_reply_message_handlers:
            handler(message1, message2)

    @staticmethod
    def _initialize_reply_message_listener():
        if not SK._is_reply_message_initialized:
            SK._native_reply_callback = SK._REPLY_CALLBACK_TYPE(SK._handle_reply_message)
            SK._dll.RegisterEventOnReplyMessage(SK._native_reply_callback)
            SK._is_reply_message_initialized = True

    class _ReplyMessageEvent:
        def __call__(self, handler: Callable[[str,str], None]):
            SK._initialize_reply_message_listener()
            SK._on_reply_message_handlers.append(handler)

    OnReplyMessage = _ReplyMessageEvent()

    # === OnNotifyQuoteLONG ===
    _on_notify_quote_long_handlers: List[Callable[[int, str], None]] = []
    _is_notify_quote_long_initialized = False
    _native_notify_quote_long_callback = None
    _NOTIFY_QUOTE_LONG_CALLBACK_TYPE = WINFUNCTYPE(None, c_int, c_char_p)

    @staticmethod
    def _handle_notify_quote_long(market_no: int, stock_no_ptr):
        stock_no = stock_no_ptr.decode("ansi")
        for handler in SK._on_notify_quote_long_handlers:
            handler(market_no, stock_no)

    @staticmethod
    def _initialize_notify_quote_long_listener():
        if not SK._is_notify_quote_long_initialized:
            SK._native_notify_quote_long_callback = SK._NOTIFY_QUOTE_LONG_CALLBACK_TYPE(SK._handle_notify_quote_long)
            SK._dll.RegisterEventOnNotifyQuoteLONG(SK._native_notify_quote_long_callback)
            SK._is_notify_quote_long_initialized = True

    class _NotifyQuoteLONGEvent:
        def __call__(self, handler: Callable[[int, str], None]):
            SK._initialize_notify_quote_long_listener()
            SK._on_notify_quote_long_handlers.append(handler)

    OnNotifyQuoteLONG = _NotifyQuoteLONGEvent()

    # === OnNotifyTicksLONG ===
    _on_notify_ticks_long_handlers: List[Callable[[int, str, int, int, int, int, int, int, int, int, int], None]] = []
    _is_notify_ticks_long_initialized = False
    _native_notify_ticks_long_callback = None

    _NOTIFY_TICKS_LONG_CALLBACK_TYPE = WINFUNCTYPE(
        None,
        c_int, c_char_p, c_int, c_int, c_int, c_int,
        c_int, c_int, c_int, c_int, c_int
    )

    @staticmethod
    def _handle_notify_ticks_long(
        market_no, stockno_ptr, ptr, date, time_hms, time_millismicros,
        bid, ask, close, qty, simulate
    ):
        try:
            stockno = stockno_ptr.decode("ansi") if stockno_ptr else ""

            for handler in SK._on_notify_ticks_long_handlers:
                try:
                    handler(market_no, stockno, ptr, date, time_hms, time_millismicros,
                            bid, ask, close, qty, simulate)
                except Exception as e:
                    print(f"[Handler Error] OnNotifyTicksLONG: {e}")

        except Exception as e:
            print(f"[Callback Decode Error] OnNotifyTicksLONG: {e}")

    @staticmethod
    def _initialize_notify_ticks_long_listener():
        if not SK._is_notify_ticks_long_initialized:
            SK._native_notify_ticks_long_callback = SK._NOTIFY_TICKS_LONG_CALLBACK_TYPE(SK._handle_notify_ticks_long)
            SK._dll.RegisterEventOnNotifyTicksLONG(SK._native_notify_ticks_long_callback)
            SK._is_notify_ticks_long_initialized = True

    class _NotifyTicksLONGEvent:
        def __call__(self, handler: Callable[[int, str, int, int, int, int, int, int, int, int, int], None]):
            SK._initialize_notify_ticks_long_listener()
            SK._on_notify_ticks_long_handlers.append(handler)

        def remove_handler(self, handler: Callable):
            if handler in SK._on_notify_ticks_long_handlers:
                SK._on_notify_ticks_long_handlers.remove(handler)

    OnNotifyTicksLONG = _NotifyTicksLONGEvent()


    # === OnNotifyOSQuoteLONG ===
    _on_notify_os_quote_long_handlers: List[Callable[[str], None]] = []
    _is_notify_os_quote_long_initialized = False
    _native_notify_os_quote_long_callback = None
    _NOTIFY_OS_QUOTE_LONG_CALLBACK_TYPE = WINFUNCTYPE(None, c_char_p)

    @staticmethod
    def _handle_notify_os_quote_long(stock_no_ptr):
        stock_no = stock_no_ptr.decode("ansi")
        for handler in SK._on_notify_os_quote_long_handlers:
            handler(stock_no)

    @staticmethod
    def _initialize_notify_os_quote_long_listener():
        if not SK._is_notify_os_quote_long_initialized:
            SK._native_notify_os_quote_long_callback = SK._NOTIFY_OS_QUOTE_LONG_CALLBACK_TYPE(SK._handle_notify_os_quote_long)
            SK._dll.RegisterEventOnNotifyOSQuoteLONG(SK._native_notify_os_quote_long_callback)
            SK._is_notify_os_quote_long_initialized = True

    class _NotifyOSQuoteLONGEvent:
        def __call__(self, handler: Callable[[str], None]):
            """註冊事件處理函式（接收 str stock_no）"""
            SK._initialize_notify_os_quote_long_listener()
            SK._on_notify_os_quote_long_handlers.append(handler)

    OnNotifyOSQuoteLONG = _NotifyOSQuoteLONGEvent()

    # === OnNotifyOOQuoteLONG ===
    _on_notify_oo_quote_long_handlers: List[Callable[[str], None]] = []
    _is_notify_oo_quote_long_initialized = False
    _native_notify_oo_quote_long_callback = None
    _NOTIFY_OO_QUOTE_LONG_CALLBACK_TYPE = WINFUNCTYPE(None, c_char_p)

    @staticmethod
    def _handle_notify_oo_quote_long(stock_no_ptr):
        try:
            stock_no = stock_no_ptr.decode("ansi")
        except Exception as e:
            print(f"[Decode Error] OnNotifyOOQuoteLONG stock_no_ptr: {stock_no_ptr}, error: {e}")
            stock_no = ""
        for handler in SK._on_notify_oo_quote_long_handlers:
            handler(stock_no)

    @staticmethod
    def _initialize_notify_oo_quote_long_listener():
        if not SK._is_notify_oo_quote_long_initialized:
            SK._native_notify_oo_quote_long_callback = SK._NOTIFY_OO_QUOTE_LONG_CALLBACK_TYPE(SK._handle_notify_oo_quote_long)
            SK._dll.RegisterEventOnNotifyOOQuoteLONG(SK._native_notify_oo_quote_long_callback)
            SK._is_notify_oo_quote_long_initialized = True

    class _NotifyOOQuoteLONGEvent:
        def __call__(self, handler: Callable[[str], None]):
            """註冊事件處理函式（接收 str stock_no）"""
            SK._initialize_notify_oo_quote_long_listener()
            SK._on_notify_oo_quote_long_handlers.append(handler)

    OnNotifyOOQuoteLONG = _NotifyOOQuoteLONGEvent()

    # === OnNotifyOSTicks ===
    _on_notify_os_ticks_handlers: List[Callable[[str, int, int, int, int, int], None]] = []
    _is_notify_os_ticks_initialized = False
    _native_notify_os_ticks_callback = None

    _NOTIFY_OS_TICKS_CALLBACK_TYPE = WINFUNCTYPE(
        None,
        c_char_p,  # strStockNo
        c_int,     # nPtr
        c_int,     # nDate
        c_int,     # nTime
        c_int,     # nClose
        c_int      # nQty
    )

    @staticmethod
    def _handle_notify_os_ticks(
        stockno_ptr: bytes, n_ptr: int, n_date: int, n_time: int, n_close: int, n_qty: int
    ):
        try:
            stockno = stockno_ptr.decode("ansi") if stockno_ptr else ""

            for handler in SK._on_notify_os_ticks_handlers:
                try:
                    handler(stockno, n_ptr, n_date, n_time, n_close, n_qty)
                except Exception as e:
                    print(f"[Handler Error] OnNotifyOSTicks: {e}")

        except Exception as e:
            print(f"[Callback Decode Error] OnNotifyOSTicks: {e}")

    @staticmethod
    def _initialize_notify_os_ticks_listener():
        if not SK._is_notify_os_ticks_initialized:
            SK._native_notify_os_ticks_callback = SK._NOTIFY_OS_TICKS_CALLBACK_TYPE(SK._handle_notify_os_ticks)
            SK._dll.RegisterEventOnNotifyOSTicks(SK._native_notify_os_ticks_callback)
            SK._is_notify_os_ticks_initialized = True

    class _NotifyOSTicksEvent:
        def __call__(self, handler: Callable[[str, int, int, int, int, int], None]):
            SK._initialize_notify_os_ticks_listener()
            SK._on_notify_os_ticks_handlers.append(handler)

        def remove_handler(self, handler: Callable):
            if handler in SK._on_notify_os_ticks_handlers:
                SK._on_notify_os_ticks_handlers.remove(handler)

    OnNotifyOSTicks = _NotifyOSTicksEvent()


    # === OnNotifyOSBest10 ===
    _on_notify_os_best10_handlers: List[Callable[[str, list, list, list, list], None]] = []
    _is_notify_os_best10_initialized = False
    _native_notify_os_best10_callback = None

    _NOTIFY_OS_BEST10_CALLBACK_TYPE = WINFUNCTYPE(
        None,
        c_char_p,  # stockno
        *([c_int] * 40)  # 10 bids + 10 bidQtys + 10 asks + 10 askQtys
    )

    @staticmethod
    def _handle_notify_os_best10(
        stockno,
        bid1, bid_qty1, bid2, bid_qty2, bid3, bid_qty3, bid4, bid_qty4, bid5, bid_qty5,
        bid6, bid_qty6, bid7, bid_qty7, bid8, bid_qty8, bid9, bid_qty9, bid10, bid_qty10,
        ask1, ask_qty1, ask2, ask_qty2, ask3, ask_qty3, ask4, ask_qty4, ask5, ask_qty5,
        ask6, ask_qty6, ask7, ask_qty7, ask8, ask_qty8, ask9, ask_qty9, ask10, ask_qty10
    ):
        best_bids = [bid1, bid2, bid3, bid4, bid5, bid6, bid7, bid8, bid9, bid10]
        bid_qtys = [bid_qty1, bid_qty2, bid_qty3, bid_qty4, bid_qty5, bid_qty6, bid_qty7, bid_qty8, bid_qty9, bid_qty10]
        best_asks = [ask1, ask2, ask3, ask4, ask5, ask6, ask7, ask8, ask9, ask10]
        ask_qtys = [ask_qty1, ask_qty2, ask_qty3, ask_qty4, ask_qty5, ask_qty6, ask_qty7, ask_qty8, ask_qty9, ask_qty10]

        for handler in SK._on_notify_os_best10_handlers:
            handler(stockno, best_bids, bid_qtys, best_asks, ask_qtys)

    @staticmethod
    def _initialize_notify_os_best10_listener():
        if not SK._is_notify_os_best10_initialized:
            SK._native_notify_os_best10_callback = SK._NOTIFY_OS_BEST10_CALLBACK_TYPE(SK._handle_notify_os_best10)
            SK._dll.RegisterEventOnNotifyOSBest10(SK._native_notify_os_best10_callback)
            SK._is_notify_os_best10_initialized = True

    class _NotifyOSBest10Event:
        def __call__(self, handler: Callable[[str, list, list, list, list], None]):
            SK._initialize_notify_os_best10_listener()
            SK._on_notify_os_best10_handlers.append(handler)

        def remove_handler(self, handler: Callable):
            if handler in SK._on_notify_os_best10_handlers:
                SK._on_notify_os_best10_handlers.remove(handler)

    OnNotifyOSBest10 = _NotifyOSBest10Event()

    # === OnNotifyOOTicks ===
    _on_notify_oo_ticks_handlers: List[Callable[[str, int, int, int, int, int], None]] = []
    _is_notify_oo_ticks_initialized = False
    _native_notify_oo_ticks_callback = None

    _NOTIFY_OO_TICKS_CALLBACK_TYPE = WINFUNCTYPE(
        None,
        c_char_p,  # strStockNo
        c_int,     # nPtr
        c_int,     # nDate
        c_int,     # nTime
        c_int,     # nClose
        c_int      # nQty
    )

    @staticmethod
    def _handle_notify_oo_ticks(
        stockno_ptr: bytes, n_ptr: int, n_date: int, n_time: int, n_close: int, n_qty: int
    ):
        try:
            stockno = stockno_ptr.decode("ansi") if stockno_ptr else ""

            for handler in SK._on_notify_oo_ticks_handlers:
                try:
                    handler(stockno, n_ptr, n_date, n_time, n_close, n_qty)
                except Exception as e:
                    print(f"[Handler Error] OnNotifyOOTicks: {e}")

        except Exception as e:
            print(f"[Callback Decode Error] OnNotifyOOTicks: {e}")

    @staticmethod
    def _initialize_notify_oo_ticks_listener():
        if not SK._is_notify_oo_ticks_initialized:
            SK._native_notify_oo_ticks_callback = SK._NOTIFY_OO_TICKS_CALLBACK_TYPE(SK._handle_notify_oo_ticks)
            SK._dll.RegisterEventOnNotifyOOTicks(SK._native_notify_oo_ticks_callback)
            SK._is_notify_oo_ticks_initialized = True

    class _NotifyOOTicksEvent:
        def __call__(self, handler: Callable[[str, int, int, int, int, int], None]):
            SK._initialize_notify_oo_ticks_listener()
            SK._on_notify_oo_ticks_handlers.append(handler)

        def remove_handler(self, handler: Callable):
            if handler in SK._on_notify_oo_ticks_handlers:
                SK._on_notify_oo_ticks_handlers.remove(handler)

    OnNotifyOOTicks = _NotifyOOTicksEvent()

    # === OnNotifyOOBest10 ===
    _on_notify_oo_best10_handlers: List[Callable[[str, list, list, list, list], None]] = []
    _is_notify_oo_best10_initialized = False
    _native_notify_oo_best10_callback = None

    _NOTIFY_OO_BEST10_CALLBACK_TYPE = WINFUNCTYPE(
        None,
        c_char_p,          # stockno
        *([c_int] * 40)    # 10 bids + 10 bidQtys + 10 asks + 10 askQtys
    )

    @staticmethod
    def _handle_notify_oo_best10(
        stockno,
        bid1, bid_qty1, bid2, bid_qty2, bid3, bid_qty3, bid4, bid_qty4, bid5, bid_qty5,
        bid6, bid_qty6, bid7, bid_qty7, bid8, bid_qty8, bid9, bid_qty9, bid10, bid_qty10,
        ask1, ask_qty1, ask2, ask_qty2, ask3, ask_qty3, ask4, ask_qty4, ask5, ask_qty5,
        ask6, ask_qty6, ask7, ask_qty7, ask8, ask_qty8, ask9, ask_qty9, ask10, ask_qty10
    ):
        best_bids = [bid1, bid2, bid3, bid4, bid5, bid6, bid7, bid8, bid9, bid10]
        bid_qtys = [bid_qty1, bid_qty2, bid_qty3, bid_qty4, bid_qty5, bid_qty6, bid_qty7, bid_qty8, bid_qty9, bid_qty10]
        best_asks = [ask1, ask2, ask3, ask4, ask5, ask6, ask7, ask8, ask9, ask10]
        ask_qtys = [ask_qty1, ask_qty2, ask_qty3, ask_qty4, ask_qty5, ask_qty6, ask_qty7, ask_qty8, ask_qty9, ask_qty10]

        for handler in SK._on_notify_oo_best10_handlers:
            handler(stockno.decode("ansi"), best_bids, bid_qtys, best_asks, ask_qtys)

    @staticmethod
    def _initialize_notify_oo_best10_listener():
        if not SK._is_notify_oo_best10_initialized:
            SK._native_notify_oo_best10_callback = SK._NOTIFY_OO_BEST10_CALLBACK_TYPE(SK._handle_notify_oo_best10)
            SK._dll.RegisterEventOnNotifyOOBest10(SK._native_notify_oo_best10_callback)
            SK._is_notify_oo_best10_initialized = True

    class _NotifyOOBest10Event:
        def __call__(self, handler: Callable[[str, list, list, list, list], None]):
            SK._initialize_notify_oo_best10_listener()
            SK._on_notify_oo_best10_handlers.append(handler)

        def remove_handler(self, handler: Callable):
            if handler in SK._on_notify_oo_best10_handlers:
                SK._on_notify_oo_best10_handlers.remove(handler)

    OnNotifyOOBest10 = _NotifyOOBest10Event()