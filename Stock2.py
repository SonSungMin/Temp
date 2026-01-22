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
    """네이버 거래량 상위 종목 가져오기"""
    urls = ["https://finance.naver.com/sise/sise_quant.naver?sosok=0", 
            "https://finance.naver.com/sise/sise_quant.naver?sosok=1"]
    headers = {'User-Agent': 'Mozilla/5.0'}
    ticker_map = {}
    for url in urls:
        try:
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a.tltle')
            for link in links[:50]:  # 50개로 확대
                name, code = link.text, link['href'].split('=')[-1]
                ticker_map[code + (".KS" if "sosok=0" in url else ".KQ")] = name
        except: 
            continue
    return list(ticker_map.keys()), ticker_map

def run_surge_scanner():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    tickers, name_map = get_dynamic_tickers()
    
    print(f"🔎 분석 시각: {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔄 급등주 분석 중...\n")
    
    results = []
    for ticker in tickers:
        try:
            # 일봉 데이터로 변경 (더 신뢰성 있음)
            df = yf.download(ticker, period='60d', interval='1d', progress=False, auto_adjust=True)
            if df.empty or len(df) < 20: 
                continue
            
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.capitalize() for c in df.columns]

            # 지표 계산
            df['ma20'] = ta.sma(df['Close'], length=20)
            df['ma60'] = ta.sma(df['Close'], length=60)
            df['rsi'] = ta.rsi(df['Close'], length=14)
            df['vol_ma20'] = ta.sma(df['Volume'], length=20)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            c_close = float(curr['Close'])
            p_close = float(prev['Close'])
            c_vol = float(curr['Volume'])
            vol_ma20 = float(curr['vol_ma20'])
            c_ma20 = float(curr['ma20'])
            c_ma60 = float(curr['ma60'])
            c_rsi = float(curr['rsi'])
            
            # 급등률 계산 (핵심)
            surge_rate = ((c_close - p_close) / p_close) * 100
            
            # 거래량 증가율 (핵심)
            vol_ratio = c_vol / vol_ma20 if vol_ma20 > 0 else 0
            
            # 필터링: 급등주 기준
            if surge_rate < 3.0:  # 3% 미만 상승은 제외
                continue
            
            if vol_ratio < 1.5:  # 평균 거래량의 1.5배 미만은 제외
                continue
            
            # 점수 산정
            score = 0
            reasons = []
            
            # 급등률 점수 (가장 중요)
            if surge_rate >= 10:
                score += 40
                reasons.append(f"강급등{surge_rate:.1f}%")
            elif surge_rate >= 5:
                score += 30
                reasons.append(f"급등{surge_rate:.1f}%")
            elif surge_rate >= 3:
                score += 20
                reasons.append(f"상승{surge_rate:.1f}%")
            
            # 거래량 점수
            if vol_ratio >= 3.0:
                score += 30
                reasons.append(f"거래폭발{vol_ratio:.1f}배")
            elif vol_ratio >= 2.0:
                score += 20
                reasons.append(f"거래급증{vol_ratio:.1f}배")
            elif vol_ratio >= 1.5:
                score += 10
                reasons.append(f"거래증가{vol_ratio:.1f}배")
            
            # 추세 점수
            if c_ma20 > c_ma60:
                score += 15
                reasons.append("상승추세")
            
            # RSI 점수
            if 50 <= c_rsi <= 70:
                score += 10
                reasons.append("모멘텀양호")
            elif c_rsi > 70:
                score += 5
                reasons.append("과열구간")
            
            # 연속 상승
            if p_close > float(df.iloc[-3]['Close']):
                score += 5
                reasons.append("연속상승")

            results.append([
                name_map[ticker], 
                f"{score}점", 
                f"{int(c_close):,}원",
                f"+{surge_rate:.1f}%",
                f"{vol_ratio:.1f}배", 
                f"{int(c_close*1.012):,}원", 
                f"{int(c_close*0.992):,}원",
                ", ".join(reasons)
            ])
        except Exception as e:
            continue
    
    if results:
        # 점수 기준 정렬 후 상위 15개 출력
        results.sort(key=lambda x: int(x[1].replace('점','')), reverse=True)
        headers = ["종목명", "적합도", "현재가", "등락률", "거래증가", "목표가(+1.2%)", "손절가(-0.8%)", "상태분석"]
        print(tabulate(results[:15], headers=headers, tablefmt="grid"))
        print(f"\n💡 총 {len(results)}개 급등 후보 발견 (3% 이상 상승 + 거래량 1.5배 이상)")
        print(f"💡 70점 이상: 강력 추천 / 50-69점: 관심 종목 / 50점 미만: 관찰")
    else:
        print("❌ 현재 급등 조건(3% 이상 + 거래량 1.5배)을 만족하는 종목이 없습니다.")
        print("💡 장 시작 직후나 급등장에서 재시도하세요.")

if __name__ == "__main__":
    run_surge_scanner()
