!pip install -q pandas_ta requests beautifulsoup4 tabulate

import pandas as pd
import pandas_ta as ta
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from tabulate import tabulate
import warnings
import time
import re

warnings.filterwarnings("ignore")

def get_sector_leaders():
    """섹터별(테마별) 상승 우량주 수집"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    ticker_map = {}
    
    start_time = time.time()
    
    # 1. 시가총액 상위
    print("📊 [1/4] 시가총액 상위 우량주 수집 중...", end=' ', flush=True)
    step_start = time.time()
    urls_cap = [
        "https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page=1",
        "https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page=2",
        "https://finance.naver.com/sise/sise_market_sum.naver?sosok=1&page=1",
    ]
    
    for url in urls_cap:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a.tltle')
            for link in links:
                name, code = link.text, link['href'].split('=')[-1]
                ticker_map[code] = {'name': name, 'source': '시총상위'}
        except:
            continue
    print(f"완료 ({time.time() - step_start:.1f}초, {len(ticker_map)}개)")
    
    # 2. 상승률 상위
    print("📈 [2/4] 상승률 상위 종목 수집 중...", end=' ', flush=True)
    step_start = time.time()
    urls_rise = [
        "https://finance.naver.com/sise/sise_rise.naver?sosok=0",
        "https://finance.naver.com/sise/sise_rise.naver?sosok=1",
    ]
    
    count_before = len(ticker_map)
    for url in urls_rise:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a.tltle')
            for link in links[:30]:
                name, code = link.text, link['href'].split('=')[-1]
                if code not in ticker_map:
                    ticker_map[code] = {'name': name, 'source': '상승률상위'}
        except:
            continue
    print(f"완료 ({time.time() - step_start:.1f}초, +{len(ticker_map) - count_before}개)")
    
    # 3. 거래대금 상위
    print("💰 [3/4] 거래대금 상위 종목 수집 중...", end=' ', flush=True)
    step_start = time.time()
    urls_amount = [
        "https://finance.naver.com/sise/sise_deal_amount.naver?sosok=0",
        "https://finance.naver.com/sise/sise_deal_amount.naver?sosok=1",
    ]
    
    count_before = len(ticker_map)
    for url in urls_amount:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.select('a.tltle')
            for link in links[:30]:
                name, code = link.text, link['href'].split('=')[-1]
                if code not in ticker_map:
                    ticker_map[code] = {'name': name, 'source': '거래대금상위'}
        except:
            continue
    print(f"완료 ({time.time() - step_start:.1f}초, +{len(ticker_map) - count_before}개)")
    
    print(f"\n✅ 종목 수집 완료: 총 {len(ticker_map)}개 (소요 시간: {time.time() - start_time:.1f}초)\n")
    
    return ticker_map

def get_naver_stock_data(code):
    """네이버에서 주식 데이터 가져오기 (일봉)"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # 일봉 데이터 (최근 60일)
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=60&requestType=0"
        res = requests.get(url, headers=headers, timeout=5)
        
        if res.status_code != 200:
            return None
        
        # XML 파싱
        soup = BeautifulSoup(res.text, 'xml')
        items = soup.find_all('item')
        
        if not items:
            return None
        
        data = []
        for item in items:
            try:
                date_str = item['data'].split('|')[0]
                open_price = int(item['data'].split('|')[1])
                high_price = int(item['data'].split('|')[2])
                low_price = int(item['data'].split('|')[3])
                close_price = int(item['data'].split('|')[4])
                volume = int(item['data'].split('|')[5])
                
                data.append({
                    'Date': pd.to_datetime(date_str),
                    'Open': open_price,
                    'High': high_price,
                    'Low': low_price,
                    'Close': close_price,
                    'Volume': volume
                })
            except:
                continue
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        
        return df
        
    except Exception as e:
        return None

def get_naver_current_price(code):
    """네이버에서 현재가 정보 가져오기 (시가총액 포함)"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 시가총액 (억원)
        market_cap = 0
        market_cap_elem = soup.select_one('em#_market_sum')
        if market_cap_elem:
            cap_text = market_cap_elem.text.strip().replace(',', '')
            try:
                market_cap = int(cap_text)
            except:
                market_cap = 0
        
        return market_cap
        
    except:
        return 0

def check_market_status(now_kst):
    """장 운영 시간 확인"""
    weekday = now_kst.weekday()
    hour = now_kst.hour
    minute = now_kst.minute
    
    if weekday >= 5:
        return "주말 (장 마감)", False
    
    if hour < 9:
        return "장 시작 전", False
    elif hour == 9 and minute < 0:
        return "장 시작 전", False
    elif hour > 15 or (hour == 15 and minute > 30):
        return "장 마감 후", False
    else:
        return "장 운영 중", True

def check_support_resistance(df, current_price):
    """지지/저항 돌파 확인"""
    highs = df['High'].tail(20)
    lows = df['Low'].tail(20)
    resistance = highs.max()
    support = lows.min()
    breakout = current_price > resistance * 0.99
    near_support = current_price < support * 1.02
    return breakout, near_support, resistance, support

def check_volume_pattern(df):
    """거래량 패턴 분석"""
    vols = df['Volume'].tail(5)
    vol_ma = df['Volume'].tail(20).mean()
    volume_surge = all(vols.iloc[i] < vols.iloc[i+1] for i in range(len(vols)-1))
    volume_explosion = vols.iloc[-1] > vol_ma * 2.0
    return volume_surge, volume_explosion

def check_price_action(df):
    """가격 행동 패턴"""
    recent = df.tail(5)
    consecutive_green = all(recent['Close'].iloc[i] > recent['Open'].iloc[i] for i in range(len(recent)))
    
    pullback_rally = False
    if len(recent) >= 4:
        uptrend = recent['Close'].iloc[-4] < recent['Close'].iloc[-3] < recent['Close'].iloc[-2]
        pullback = recent['Close'].iloc[-2] > recent['Close'].iloc[-1]
        rally = recent['Close'].iloc[-1] > recent['Open'].iloc[-1]
        pullback_rally = uptrend and pullback and rally
    
    last = df.iloc[-1]
    body = abs(last['Close'] - last['Open'])
    total_range = last['High'] - last['Low']
    lower_shadow = min(last['Open'], last['Close']) - last['Low']
    hammer = (lower_shadow > body * 2) and (total_range > 0) and (last['Close'] > last['Open'])
    
    return consecutive_green, pullback_rally, hammer

def calculate_bollinger_bands(df):
    """볼린저 밴드"""
    try:
        bb = ta.bbands(df['Close'], length=20, std=2)
        if bb is None or bb.empty:
            return False, False
        
        current_price = df['Close'].iloc[-1]
        lower_band = bb['BBL_20_2.0'].iloc[-1]
        upper_band = bb['BBU_20_2.0'].iloc[-1]
        middle_band = bb['BBM_20_2.0'].iloc[-1]
        
        touch_lower = current_price < lower_band * 1.01
        cross_middle = current_price > middle_band and df['Close'].iloc[-2] < middle_band
        near_upper = current_price > upper_band * 0.98
        
        return (touch_lower or cross_middle), near_upper
    except:
        return False, False

def check_macd_signal(df):
    """MACD 신호"""
    try:
        macd = ta.macd(df['Close'])
        if macd is None or macd.empty:
            return False, False
        
        macd_line = macd['MACD_12_26_9']
        signal_line = macd['MACDs_12_26_9']
        
        golden_cross = (macd_line.iloc[-1] > signal_line.iloc[-1]) and (macd_line.iloc[-2] <= signal_line.iloc[-2])
        death_cross = (macd_line.iloc[-1] < signal_line.iloc[-1]) and (macd_line.iloc[-2] >= signal_line.iloc[-2])
        
        return golden_cross, death_cross
    except:
        return False, False

def run_sector_scanner():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    
    market_status, is_trading = check_market_status(now_kst)
    
    print(f"{'='*120}")
    print(f"🎯 섹터별 우량 상승주 스캐너 (네이버 금융 데이터)")
    print(f"📅 분석 실행 시각: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} ({now_kst.strftime('%A')})")
    print(f"🏢 시장 상태: {market_status}")
    print(f"{'='*120}\n")
    
    overall_start = time.time()
    
    ticker_map = get_sector_leaders()
    
    print(f"{'='*120}")
    print(f"📡 종목 데이터 다운로드 및 분석 시작 (총 {len(ticker_map)}개)")
    print(f"{'='*120}\n")
    
    # 통계
    stats = {
        'total': 0,
        'small_cap': 0,
        'data_fail': 0,
        'data_fail_reasons': {},
        'no_change': 0,
        'decline': 0,
        'upper_limit': 0,
        'low_volume': 0,
        'rsi_over': 0,
        'score_fail': 0,
        'passed': 0
    }
    
    results = []
    detailed_logs = []
    
    # 데이터 시간 추적
    latest_data_time = None
    
    # 성능 측정
    download_times = []
    analysis_times = []
    total_tickers = len(ticker_map)
    current_idx = 0
    
    for code, info in ticker_map.items():
        current_idx += 1
        stats['total'] += 1
        stock_name = info['name']
        source = info['source']
        
        # 진행률 표시
        if current_idx % 20 == 0 or current_idx == 1:
            print(f"진행: {current_idx}/{total_tickers} ({current_idx/total_tickers*100:.1f}%) - 현재: {stock_name}", flush=True)
        
        try:
            # === 시가총액 확인 ===
            market_cap = get_naver_current_price(code)
            if 0 < market_cap < 100:
                stats['small_cap'] += 1
                detailed_logs.append(f"❌ {stock_name} ({source}): 초소형주 제외 (시총 {market_cap:.0f}억)")
                continue
            
            # === 데이터 다운로드 ===
            download_start = time.time()
            
            df = get_naver_stock_data(code)
            
            download_time = time.time() - download_start
            download_times.append(download_time)
            
            if df is None or df.empty:
                stats['data_fail'] += 1
                reason = "데이터 없음"
                stats['data_fail_reasons'][reason] = stats['data_fail_reasons'].get(reason, 0) + 1
                detailed_logs.append(f"❌ {stock_name} ({source}): {reason}")
                continue
                
            if len(df) < 20:
                stats['data_fail'] += 1
                reason = f"데이터 부족 ({len(df)}개 < 20개)"
                stats['data_fail_reasons'][reason] = stats['data_fail_reasons'].get(reason, 0) + 1
                detailed_logs.append(f"❌ {stock_name} ({source}): {reason}")
                continue
            
            # 데이터 최신 시간
            data_latest_time = df.index[-1]
            data_latest_kst = data_latest_time.tz_localize(kst) if data_latest_time.tzinfo is None else data_latest_time.astimezone(kst)
            
            if latest_data_time is None or data_latest_kst > latest_data_time:
                latest_data_time = data_latest_kst
            
            # 데이터 신선도
            data_age_hours = (now_kst - data_latest_kst).total_seconds() / 3600
            if data_age_hours > 48:
                stats['data_fail'] += 1
                reason = "데이터 오래됨"
                stats['data_fail_reasons'][reason] = stats['data_fail_reasons'].get(reason, 0) + 1
                detailed_logs.append(f"⏰ {stock_name} ({source}): {reason} (최신: {data_latest_kst.strftime('%m-%d')}, {data_age_hours/24:.1f}일 전)")
                continue
            
            # === 기술적 분석 시작 ===
            analysis_start = time.time()
            
            # 기본 지표
            df['ma5'] = ta.sma(df['Close'], length=5)
            df['ma20'] = ta.sma(df['Close'], length=20)
            df['ma60'] = ta.sma(df['Close'], length=60)
            df['rsi'] = ta.rsi(df['Close'], length=14)
            df['vol_ma20'] = ta.sma(df['Volume'], length=20)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            c_close = float(curr['Close'])
            p_close = float(prev['Close'])
            c_vol = float(curr['Volume'])
            vol_ma20 = float(curr['vol_ma20']) if not pd.isna(curr['vol_ma20']) else 1
            c_ma5 = float(curr['ma5']) if not pd.isna(curr['ma5']) else c_close
            c_ma20 = float(curr['ma20']) if not pd.isna(curr['ma20']) else c_close
            c_ma60 = float(curr['ma60']) if not pd.isna(curr['ma60']) else c_close
            c_rsi = float(curr['rsi']) if not pd.isna(curr['rsi']) else 50
            
            surge_rate = ((c_close - p_close) / p_close) * 100
            vol_ratio = c_vol / vol_ma20 if vol_ma20 > 0 else 0
            
            # === 필터링 ===
            
            # 1. 보합/하락 제외
            if abs(surge_rate) < 0.5:
                stats['no_change'] += 1
                detailed_logs.append(f"⚪ {stock_name} ({source}): 보합 (등락 {surge_rate:.1f}%)")
                continue
            
            if surge_rate < -2.0:
                stats['decline'] += 1
                detailed_logs.append(f"🔻 {stock_name} ({source}): 하락 중 ({surge_rate:.1f}%)")
                continue
            
            # 2. 상한가 제외
            if surge_rate >= 28.0:
                stats['upper_limit'] += 1
                detailed_logs.append(f"🚫 {stock_name} ({source}): 상한가 근접 ({surge_rate:.1f}%)")
                continue
            
            # 3. 거래량
            if vol_ratio < 1.0:
                stats['low_volume'] += 1
                detailed_logs.append(f"📉 {stock_name} ({source}): 거래량 부족 ({vol_ratio:.1f}배)")
                continue
            
            # 4. RSI 과열
            if c_rsi > 85:
                stats['rsi_over'] += 1
                detailed_logs.append(f"🔥 {stock_name} ({source}): RSI 과열 ({c_rsi:.1f})")
                continue
            
            # === 점수 산정 ===
            score = 0
            signals = []
            risk_flags = []
            
            # 우량주 보너스
            if market_cap > 10000:
                score += 15
                signals.append(f"대형주{int(market_cap/10000)}조")
            elif market_cap > 5000:
                score += 12
                signals.append(f"중대형{int(market_cap/1000)}천억")
            elif market_cap > 1000:
                score += 8
                signals.append(f"중형{int(market_cap/1000)}천억")
            elif market_cap > 500:
                score += 5
                signals.append(f"중소형{int(market_cap)}억")
            elif market_cap > 200:
                score += 3
                signals.append(f"소형{int(market_cap)}억")
            else:
                signals.append(f"초소형{int(market_cap)}억")
            
            # 지지/저항
            breakout, near_support, resistance, support = check_support_resistance(df, c_close)
            if breakout:
                score += 20
                signals.append("고점돌파")
            
            # 거래량 패턴
            vol_surge, vol_explosion = check_volume_pattern(df)
            if vol_explosion:
                score += 20
                signals.append("거래폭발")
            elif vol_surge:
                score += 10
                signals.append("거래증가")
            
            # 가격 행동
            consecutive_green, pullback_rally, hammer = check_price_action(df)
            if consecutive_green:
                score += 12
                signals.append("연속상승")
            if pullback_rally:
                score += 18
                signals.append("조정후반등")
            if hammer:
                score += 12
                signals.append("반전캔들")
            
            # 볼린저 밴드
            bb_buy_signal, bb_overbought = calculate_bollinger_bands(df)
            if bb_buy_signal:
                score += 12
                signals.append("BB매수")
            if bb_overbought:
                score -= 10
                risk_flags.append("과열")
            
            # MACD
            macd_golden, macd_death = check_macd_signal(df)
            if macd_golden:
                score += 18
                signals.append("MACD골든")
            if macd_death:
                score -= 15
                risk_flags.append("MACD매도")
            
            # 이동평균선
            if c_ma5 > c_ma20 > c_ma60:
                score += 12
                signals.append("정배열")
            elif c_ma5 < c_ma20:
                score -= 8
                risk_flags.append("역배열")
            
            # RSI
            if 50 <= c_rsi <= 75:
                score += 10
                signals.append("RSI양호")
            elif 30 <= c_rsi < 50:
                score += 8
                signals.append("RSI회복")
            
            # 급등률
            if 10 <= surge_rate < 28:
                score += 15
                signals.append(f"강상승{surge_rate:.1f}%")
            elif 5 <= surge_rate < 10:
                score += 12
                signals.append(f"상승{surge_rate:.1f}%")
            elif 2 <= surge_rate < 5:
                score += 8
                signals.append(f"완만{surge_rate:.1f}%")
            elif -2 <= surge_rate < 2:
                score += 3
                signals.append(f"보합{surge_rate:.1f}%")
            
            # 최소 점수
            if market_cap > 5000:
                min_score = 40
            elif market_cap > 1000:
                min_score = 45
            elif market_cap > 500:
                min_score = 50
            else:
                min_score = 55
                
            if score < min_score:
                stats['score_fail'] += 1
                detailed_logs.append(f"⚠️  {stock_name} ({source}): 신뢰도 부족 ({score}점 < {min_score}점, 시총 {int(market_cap)}억)")
                continue
            
            # 통과!
            stats['passed'] += 1
            risk_level = "높음" if len(risk_flags) >= 2 else "중간" if len(risk_flags) == 1 else "낮음"
            
            cap_display = f"{int(market_cap/10000)}조" if market_cap > 10000 else f"{int(market_cap/1000)}천억" if market_cap > 1000 else f"{int(market_cap)}억"
            
            data_time_display = data_latest_kst.strftime('%m/%d')
            
            detailed_logs.append(f"✅ {stock_name} ({source}): 통과! 시총 {cap_display} | 점수 {score}점 | 데이터: {data_time_display}")
            
            results.append([
                stock_name,
                source,
                cap_display,
                f"{score}점", 
                risk_level,
                f"{int(c_close):,}원",
                f"{surge_rate:+.1f}%",
                f"{vol_ratio:.1f}배", 
                f"{int(c_close*1.015):,}원",
                f"{int(c_close*0.985):,}원",
                " | ".join(signals[:3]) if signals else "-"
            ])
            
            # 분석 시간 기록
            analysis_time = time.time() - analysis_start
            analysis_times.append(analysis_time)
            
        except Exception as e:
            stats['data_fail'] += 1
            error_msg = str(e)[:80]
            reason = f"예외발생: {error_msg}"
            stats['data_fail_reasons'][reason] = stats['data_fail_reasons'].get(reason, 0) + 1
            detailed_logs.append(f"❌ {stock_name} ({source}): {reason}")
            continue
    
    total_time = time.time() - overall_start
    
    # === 성능 통계 ===
    print(f"\n{'='*120}")
    print(f"⏱️  성능 분석")
    print(f"{'='*120}")
    print(f"전체 소요 시간: {total_time:.1f}초 ({total_time/60:.1f}분)")
    
    if download_times:
        avg_download = sum(download_times) / len(download_times)
        total_download = sum(download_times)
        print(f"\n📡 데이터 다운로드 (네이버 금융):")
        print(f"  - 총 다운로드 시간: {total_download:.1f}초 ({total_download/total_time*100:.1f}%)")
        print(f"  - 평균 다운로드 시간: {avg_download:.3f}초/종목")
        print(f"  - 최대 다운로드 시간: {max(download_times):.2f}초")
        print(f"  - 다운로드 횟수: {len(download_times)}회")
        
    if analysis_times:
        avg_analysis = sum(analysis_times) / len(analysis_times)
        total_analysis = sum(analysis_times)
        print(f"\n📈 기술적 분석:")
        print(f"  - 총 분석 시간: {total_analysis:.1f}초 ({total_analysis/total_time*100:.1f}%)")
        print(f"  - 평균 분석 시간: {avg_analysis:.3f}초/종목")
        print(f"  - 분석 종목 수: {len(analysis_times)}개")
    
    print(f"\n💡 종목당 평균 처리: {total_time/total_tickers:.2f}초")
    print(f"💡 Yahoo Finance 대비 예상 속도 향상: 5~10배")
    
    # === 결과 출력 ===
    print(f"\n{'='*120}")
    print(f"📊 데이터 정보")
    print(f"{'='*120}")
    print(f"📡 데이터 출처: 네이버 금융 (한국 서버)")
    if latest_data_time:
        print(f"📅 데이터 최신 시각: {latest_data_time.strftime('%Y-%m-%d')} (일봉)")
        data_delay = (now_kst - latest_data_time).total_seconds() / 3600
        if data_delay < 24:
            print(f"⏱️  데이터 지연: {data_delay:.1f}시간 (신선)")
        else:
            print(f"⏱️  데이터 지연: {data_delay/24:.1f}일")
    
    print(f"\n{'='*120}")
    print(f"📊 필터링 통계")
    print(f"{'='*120}")
    print(f"총 분석: {stats['total']}개")
    print(f"  ├─ 소형주 제외: {stats['small_cap']}개")
    print(f"  ├─ 데이터 오류: {stats['data_fail']}개")
    
    if stats['data_fail_reasons']:
        print(f"  │   └─ 오류 상세:")
        for reason, count in sorted(stats['data_fail_reasons'].items(), key=lambda x: x[1], reverse=True):
            print(f"  │       ├─ {reason}: {count}개")
    
    print(f"  ├─ 보합: {stats['no_change']}개")
    print(f"  ├─ 하락: {stats['decline']}개")
    print(f"  ├─ 상한가: {stats['upper_limit']}개")
    print(f"  ├─ 거래량 부족: {stats['low_volume']}개")
    print(f"  ├─ RSI 과열: {stats['rsi_over']}개")
    print(f"  ├─ 신뢰도 부족: {stats['score_fail']}개")
    print(f"  └─ ✅ 최종 통과: {stats['passed']}개")
    
    print(f"\n{'='*120}")
    print(f"📋 상세 로그 (최근 50개)")
    print(f"{'='*
