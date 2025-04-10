import pandas as pd
import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, List
from datetime import datetime
from io import StringIO
from GoogleNews import GoogleNews

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
                
                if not price_col or not change_col:
                    raise ValueError(f"Could not find price or change columns in {df.columns}")
                
                # 데이터프레임 재구성
                result_df = pd.DataFrame()
                result_df['Symbol'] = df['Symbol']
                result_df['Name'] = df['Name']
                result_df['Price'] = df[price_col]
                result_df['% Change'] = df[change_col]
                
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
