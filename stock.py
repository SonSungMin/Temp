!pip install -q yfinance pandas_ta requests beautifulsoup4 tabulate

import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from tabulate import tabulate
import warnings

warnings.filterwarnings("ignore")

def get_dynamic_tickers():
    urls = ["https://finance.naver.com/sise/sise_quant.naver?sosok=0", "https://finance.naver.com/sise/sise_quant.naver?sosok=1"]
    headers = {'User-Agent': 'Mozilla/5.0'}
    ticker_map = {}
    for url in urls:
        try:
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a.tltle')
            for link in links[:25]:
                name, code = link.text, link['href'].split('=')[-1]
                ticker_map[code + (".KS" if "sosok=0" in url else ".KQ")] = name
        except: continue
    return list(ticker_map.keys()), ticker_map

def run_failsafe_scanner():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    tickers, name_map = get_dynamic_tickers()
    
    print(f"🔎 분석 시각: {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔄 데이터 분석 중... (수급이 부족해도 상위 종목을 무조건 출력합니다.)\n")
    
    results = []
    for ticker in tickers:
        try:
            df = yf.download(ticker, period='2d', interval='1m', progress=False, auto_adjust=True)
            if df.empty or len(df) < 15: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [c.capitalize() for c in df.columns]

            # 지표 계산
            df['ma5'] = ta.sma(df['Close'], length=5)
            df['ma20'] = ta.sma(df['Close'], length=20)
            df['rsi'] = ta.rsi(df['Close'], length=14)
            df['v_ma'] = ta.sma(df['Volume'], length=10)

            curr, prev = df.iloc[-1], df.iloc[-2]
            c_close, c_ma5, c_ma20, c_rsi, c_vol, v_ma = map(float, [curr['Close'], curr['ma5'], curr['ma20'], curr['rsi'], curr['Volume'], curr['v_ma']])
            
            # 점수 산정
            score, reasons = 0, []
            if c_ma5 > c_ma20: score += 30; reasons.append("정배열")
            v_ratio = c_vol / v_ma if v_ma > 0 else 0
            if v_ratio >= 2.0: score += 40; reasons.append("수급폭발")
            elif v_ratio >= 1.0: score += 15; reasons.append("수급유지")
            if 50 <= c_rsi <= 75: score += 20; reasons.append("에너지양호")
            if c_close > float(prev['High']): score += 10; reasons.append("전봉돌파")

            results.append([
                name_map[ticker], f"{score}점", f"{int(c_close):,}원", 
                f"{v_ratio:.1f}배", f"{int(c_close*1.012):,}원", f"{int(c_close*0.992):,}원",
                ", ".join(reasons) if reasons else "추세정체"
            ])
        except: continue
    
    if results:
        # 점수 기준 정렬 후 상위 10개 출력
        results.sort(key=lambda x: int(x[1].replace('점','')), reverse=True)
        headers = ["종목명", "적합도", "현재가", "거래폭증", "목표가(+1.2%)", "손절가(-0.8%)", "상태분석"]
        print(tabulate(results[:10], headers=headers, tablefmt="grid"))
        print(f"\n💡 현재 시간대 수급이 약해 점수가 낮을 수 있습니다. 80점 이상이 나올 때까지 반복 실행을 권장합니다.")
    else:
        print("❌ 야후 파이낸스 서버로부터 데이터를 가져오지 못했습니다. 잠시 후 시도하세요.")

if __name__ == "__main__":
    run_failsafe_scanner()
