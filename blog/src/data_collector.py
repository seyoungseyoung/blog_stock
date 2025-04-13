import pandas as pd
import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from io import StringIO
from GoogleNews import GoogleNews
import yfinance as yf

def parse_volume(volume_str: str) -> float:
    """볼륨 문자열을 숫자로 변환합니다."""
    try:
        if not isinstance(volume_str, str):
            return float(volume_str)
            
        volume_str = volume_str.strip().upper()
        if not volume_str or volume_str == 'N/A':
            return 0.0
            
        # 접미사 제거 및 숫자 변환
        multiplier = 1
        if volume_str.endswith('K'):
            multiplier = 1_000
            volume_str = volume_str[:-1]
        elif volume_str.endswith('M'):
            multiplier = 1_000_000
            volume_str = volume_str[:-1]
        elif volume_str.endswith('B'):
            multiplier = 1_000_000_000
            volume_str = volume_str[:-1]
            
        # 콤마 제거 후 숫자 변환
        volume = float(volume_str.replace(',', ''))
        return volume * multiplier
        
    except (ValueError, TypeError, AttributeError):
        return 0.0

class MarketDataCollector:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Google News 설정
        self.gn = GoogleNews()
        self.gn.set_encode('utf-8')
        self.gn.set_lang('en')
        self.gn.set_topic('CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US%3Aen')

    def get_market_data(self) -> Dict[str, pd.DataFrame]:
        """Yahoo Finance에서 시장 데이터(상승주, 하락주, 거래량 상위, ETF)를 수집합니다."""
        urls = {
            'gainers': 'https://finance.yahoo.com/gainers',
            'losers': 'https://finance.yahoo.com/losers',
            'trending': 'https://finance.yahoo.com/markets/stocks/trending',
            'most_active': 'https://finance.yahoo.com/most-active',
            'top_etfs': 'https://finance.yahoo.com/etfs'
        }

        market_data = {}
        for category, url in urls.items():
            try:
                print(f"- {category} 데이터 수집 중...")
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()  # HTTP 오류 확인
                
                html_io = StringIO(response.text)
                df = pd.read_html(html_io)[0]
                
                # 데이터 검증
                if df.empty:
                    raise ValueError(f"Empty dataframe received for {category}")
                
                # 필요한 컬럼 매핑 및 선택
                print(f"Found columns for {category}: {df.columns.tolist()}")
                
                # 기본 컬럼 요구사항
                required_cols = {'Symbol', 'Name'}
                missing_cols = required_cols - set(df.columns)
                if missing_cols:
                    raise ValueError(f"Missing required columns: {missing_cols}")
                
                # 컬럼 매핑
                # 가격과 변화율 컬럼 찾기
                price_col = next((col for col in df.columns if 'Price' in col), None)
                change_col = next((col for col in df.columns if 'Change %' in col or '% Change' in col), None)
                volume_col = next((col for col in df.columns if 'Volume' in col), None)
                
                if not price_col or not change_col:
                    raise ValueError(f"Could not find price or change columns in {df.columns}")
                
                # 데이터프레임 재구성
                result_df = pd.DataFrame()
                result_df['Symbol'] = df['Symbol']
                result_df['Name'] = df['Name']
                result_df['Price'] = df[price_col]
                result_df['% Change'] = df[change_col]
                if volume_col:
                    result_df['Volume'] = df[volume_col]
                
                market_data[category] = result_df
                print(f"✓ {category} 데이터 수집 완료 (rows: {len(result_df)})")
                
            except Exception as e:
                self.logger.error(f"Error collecting {category} data: {e}")
                print(f"✗ {category} 데이터 수집 실패: {str(e)}")
                market_data[category] = pd.DataFrame()

        return market_data

    def get_market_news(self) -> List[Dict]:
        """Google News에서 최신 금융 뉴스를 수집합니다."""
        try:
            print("뉴스 데이터 수집 중...")
            
            # 오늘 날짜 설정
            today = datetime.now().strftime("%m/%d/%Y")
            
            # Google News 설정 및 데이터 가져오기
            self.gn.clear()
            self.gn.set_time_range(start=today, end=today)
            self.gn.get_news()
            
            # 결과를 DataFrame으로 변환
            results = self.gn.results()
            if not results:
                return []
                
            df = pd.DataFrame(results)[['title', 'datetime']]
            df['date'] = df['datetime'].dt.date
            
            # 중요 키워드 정의
            priority_keywords = {
                'high': ['tariff', 'trade', 'fed', 'interest rate', 'inflation', 'economy', 'market'],
                'medium': ['earnings', 'stock', 'company', 'industry'],
                'low': ['product', 'service', 'individual stock']
            }
            
            # 뉴스 데이터 변환
            news_items = []
            for _, row in df.iterrows():
                title = row['title']
                
                # 뉴스 중요도 평가
                importance = 'low'
                for level, keywords in priority_keywords.items():
                    if any(keyword.lower() in title.lower() for keyword in keywords):
                        importance = level
                        break
                
                news_items.append({
                    'title': title,
                    'time': row['date'].strftime('%Y-%m-%d'),
                    'importance': importance
                })
            
            # 중요도에 따라 정렬
            importance_order = {'high': 0, 'medium': 1, 'low': 2}
            news_items.sort(key=lambda x: importance_order[x['importance']])
            
            print(f"✓ 뉴스 데이터 수집 완료 (기사 수: {len(news_items)})")
            return news_items
            
        except Exception as e:
            self.logger.error(f"Error collecting news: {e}")
            print(f"✗ 뉴스 데이터 수집 실패: {str(e)}")
            return []

    def get_stock_recommendations(self, market_data: Dict[str, pd.DataFrame], num_recommendations: int = 5) -> List[Dict]:
        """주식 추천을 생성합니다. (벡터화 연산으로 효율적으로 계산)"""
        try:
            print("주식 추천 생성 중...")
            
            # 모든 종목을 하나의 DataFrame으로 통합
            all_stocks = pd.DataFrame()
            
            # 카테고리별 데이터 통합
            for category, df in market_data.items():
                if df.empty or category == 'top_etfs':  # ETF는 제외
                    continue
                
                # 카테고리 정보 추가
                df_copy = df.copy()
                df_copy['category'] = category
                all_stocks = pd.concat([all_stocks, df_copy], ignore_index=True)
            
            if all_stocks.empty:
                print("분석할 종목이 없습니다.")
                return []
            
            # % Change 컬럼 숫자 타입으로 변환
            all_stocks['change_pct'] = all_stocks['% Change'].apply(
                lambda x: float(str(x).strip('%').replace(',', ''))
            )
            
            # Volume 컬럼이 있으면 숫자 타입으로 변환
            if 'Volume' in all_stocks.columns:
                all_stocks['volume_numeric'] = all_stocks['Volume'].apply(parse_volume)
            
            # 주식 분석 결과를 저장할 리스트
            recommendations = []
            
            # 상위 20개 종목만 선택하여 자세한 분석 수행 (성능 최적화)
            potential_stocks = all_stocks.sort_values(by='change_pct', ascending=False).head(20)
            
            # yfinance 데이터 수집 및 기술적 지표 계산 (병렬 계산 준비)
            stock_data = {}
            print("기술적 지표 계산 중...")
            
            for _, row in potential_stocks.iterrows():
                symbol = row['Symbol']
                try:
                    # yfinance 데이터 수집
                    stock = yf.Ticker(symbol)
                    info = stock.info
                    hist = stock.history(period="1mo")
                    
                    if hist.empty:
                        continue
                    
                    # 기술적 지표 계산을 위한 준비
                    stock_data[symbol] = {
                        'history': hist,
                        'info': info,
                        'row': row
                    }
                except Exception as e:
                    self.logger.error(f"Error fetching data for {symbol}: {e}")
                    continue
            
            # 벡터화된 기술적 지표 계산 함수
            def calculate_technical_indicators(symbol, data):
                hist = data['history']
                row = data['row']
                info = data['info']
                
                # 공통 기술적 지표 계산
                # 1. RSI 계산 (벡터화 연산)
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]
                
                # 2. MACD 계산 (벡터화 연산)
                exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
                exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
                macd = exp1 - exp2
                signal = macd.ewm(span=9, adjust=False).mean()
                current_macd = macd.iloc[-1]
                
                # 3. 추천 점수 계산
                score = 0
                
                # 3.1 가격 변동성
                price_change = row['change_pct']
                if price_change > 0:
                    score += price_change * 0.5
                
                # 3.2 거래량
                if 'Volume' in row:
                    volume = parse_volume(str(row['Volume']))
                    avg_volume = hist['Volume'].mean()
                    if volume > avg_volume:
                        score += 10
                
                # 3.3 RSI
                if 30 <= current_rsi <= 70:
                    score += 15
                elif current_rsi < 30:  # 과매도
                    score += 20
                
                # 3.4 MACD
                if current_macd > signal.iloc[-1]:  # 골든크로스
                    score += 15
                
                # 결과 반환
                return {
                    'name': row['Name'].strip(),
                    'symbol': symbol,
                    'price': row['Price'],
                    'change_pct': price_change,
                    'volume': row.get('Volume', 'N/A'),
                    'rsi': current_rsi,
                    'macd': current_macd,
                    'score': score,
                    'market_cap': info.get('marketCap', 'N/A'),
                    'sector': info.get('sector', 'N/A'),
                    'industry': info.get('industry', 'N/A'),
                    'category': row['category']
                }
            
            # 각 종목별 기술적 지표 계산
            for symbol, data in stock_data.items():
                try:
                    result = calculate_technical_indicators(symbol, data)
                    recommendations.append(result)
                    print(f"- {symbol} 분석 완료 (점수: {result['score']})")
                except Exception as e:
                    self.logger.error(f"Error analyzing {symbol}: {e}")
                    continue
            
            # 점수 기준으로 정렬하고 상위 n개 선택
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            selected_recommendations = recommendations[:num_recommendations]
            
            print(f"\n✓ 주식 추천 생성 완료 (분석된 종목: {len(recommendations)}, 추천 종목: {len(selected_recommendations)})")
            return selected_recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
            return []
