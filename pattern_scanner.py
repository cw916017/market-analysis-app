import pandas as pd

class PatternScanner:
    @staticmethod
    def check_morning_star_doji(df: pd.DataFrame) -> bool:
        """
        檢查最後一根K線是否符合「晨星十字 (Morning Doji Star)」(底部反轉買進訊號)
        """
        if len(df) < 3:
            return False

        c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

        body1 = abs(c1['Close'] - c1['Open'])
        body2 = abs(c2['Close'] - c2['Open'])
        body3 = abs(c3['Close'] - c3['Open'])
        avg_body = (body1 + body2 + body3) / 3

        is_first_black = c1['Close'] < c1['Open'] and body1 > (avg_body * 0.5)
        is_second_small = body2 <= (avg_body * 0.4)
        mid_point_1 = (c1['Open'] + c1['Close']) / 2
        is_third_red = c3['Close'] > c3['Open'] and c3['Close'] >= mid_point_1

        return is_first_black and is_second_small and is_third_red

    @staticmethod
    def check_evening_star_doji(df: pd.DataFrame) -> bool:
        """
        檢查最後一根K線是否符合「夜星十字 (Evening Doji Star)」(頭部反轉賣出/警戒訊號)
        """
        if len(df) < 3:
            return False

        c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

        body1 = abs(c1['Close'] - c1['Open'])
        body2 = abs(c2['Close'] - c2['Open'])
        body3 = abs(c3['Close'] - c3['Open'])
        avg_body = (body1 + body2 + body3) / 3

        is_first_red = c1['Close'] > c1['Open'] and body1 > (avg_body * 0.5)
        is_second_small = body2 <= (avg_body * 0.4)
        mid_point_1 = (c1['Open'] + c1['Close']) / 2
        is_third_black = c3['Close'] < c3['Open'] and c3['Close'] <= mid_point_1

        return is_first_red and is_second_small and is_third_black