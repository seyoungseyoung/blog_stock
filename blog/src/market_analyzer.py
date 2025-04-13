import pandas as pd
import logging
from typing import Dict, List, Any, Tuple
import os
import requests
import json
from utils import parse_price_string
import time
from datetime import datetime
from data_collector import MarketDataCollector
import re
import random

class MarketAnalyzer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        
        if not self.api_key:
            raise ValueError("DeepSeek API key not found in environment variables")

    def _get_biggest_mover(self, df: pd.DataFrame, column: str, ascending: bool = True) -> Dict:
        """데이터프레임에서 가장 큰 변화를 보인 종목을 찾습니다."""
        try:
            if df.empty:
                return {}
            
            # 컬럼 이름이 정확히 일치하지 않을 경우를 대비한 처리
            change_col = None
            for col in df.columns:
                if column.lower() in col.lower():
                    change_col = col
                    break
            
            if not change_col:
                self.logger.error(f"Column {column} not found in dataframe")
                return {}
            
            # 변화율 기준으로 정렬
            df_sorted = df.sort_values(by=change_col, ascending=ascending)
            
            if df_sorted.empty:
                return {}
            
            # 첫 번째 행 선택
            row = df_sorted.iloc[0]
            
            # 결과 딕셔너리 생성
            result = {
                'Name': str(row['Name']).strip(),
                'Symbol': str(row['Symbol']).strip(),
                'Price': str(row['Price']).strip(),
                'Change %': float(str(row[change_col]).strip('%').replace(',', ''))
            }
            
            # Change가 있다면 추가
            if 'Change' in row:
                result['Change'] = str(row['Change']).strip()
            
            # Volume이 있다면 추가
            if 'Volume' in row:
                result['Volume'] = str(row['Volume'])
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in _get_biggest_mover: {e}")
            return {}

    def analyze_market(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """시장 분석을 수행합니다."""
        try:
            # 데이터 준비
            prepared_data = self._prepare_analysis_data(market_data)
            if not prepared_data:
                return None
            
            # 분석 수행 (자동 진행)
            analysis_result = self._perform_analysis(prepared_data)
            if not analysis_result:
                return None
            
            return analysis_result
        
        except Exception as e:
            self.logger.error(f"시장 분석 중 오류 발생: {e}")
            return None

    def analyze_market_trend(self, market_data: Dict[str, pd.DataFrame], news_data: List[Dict], recommendations: List[Dict]) -> Tuple[str, str, List[str], Dict]:
        """시장 동향을 분석하고 블로그 포스팅용 콘텐츠와 태그를 생성합니다."""
        try:
            # 1. 데이터 분석
            print("1. 시장 데이터 분석 중...")
            analysis = self._analyze_data(market_data)
            if not analysis:
                raise Exception("데이터 분석 실패")
            
            # 2. 뉴스 데이터 처리 및 분석 결과에 추가
            print("2. 뉴스 데이터 처리 중...")
            analysis['news'] = news_data[:5]  # 상위 5개 뉴스만 사용
            
            # 추천 종목 정보를 analysis 딕셔너리에 추가
            analysis['recommendations'] = recommendations
            
            # 3. 블로그 포스팅용 콘텐츠 생성 (이제 recommendations 포함된 analysis 사용)
            print("3. 블로그 포스팅용 콘텐츠 생성 중...")
            title, content = self._create_blog_content(analysis)
            
            # 4. 태그 생성
            print("4. 태그 생성 중...")
            tags = self._generate_market_tags(title, content, analysis)
            
            # 5. 결과 반환
            return title, content, tags, analysis
            
        except Exception as e:
            self.logger.error(f"시장 분석 실패: {e}", exc_info=True)
            return None, None, None, {}

    def _prepare_analysis_data(self, market_data: Dict[str, pd.DataFrame], news: List[Dict] = None) -> Dict:
        """시장 데이터를 분석용으로 가공합니다."""
        try:
            # 데이터 유효성 검증
            for key, df in market_data.items():
                if df.empty:
                    self.logger.warning(f"Empty dataframe for {key}")
                else:
                    # 날짜 정보 확인
                    if 'Date' in df.columns:
                        market_date = df['Date'].iloc[0]
                        self.logger.info(f"Market data date for {key}: {market_date}")
            
            # 각 카테고리의 첫 번째 종목 정보 추출
            significant_moves = {}
            
            for category in ['gainers', 'losers', 'most_active', 'trending']:
                if category in market_data and not market_data[category].empty:
                    df = market_data[category]
                    row = df.iloc[0]
                    
                    price = row['Price']
                    change_pct = float(str(row['% Change']).strip('%'))
                    
                    significant_moves[f'biggest_{category[:-1]}'] = {
                        'Name': row['Name'].strip(),
                        'Symbol': row['Symbol'].strip(),
                        'Price': price,
                        'Change_Pct': change_pct,
                        'Volume': row.get('Volume')
                    }
            
            # 뉴스 데이터 처리
            if news:
                current_date = datetime.now().strftime('%Y-%m-%d')
                processed_news = []
                for item in news[:5]:  # 최대 5개 뉴스만 처리
                    if isinstance(item, dict):
                        # 뉴스 항목에 date 필드 추가 (time을 date로 변환)
                        news_item = item.copy()
                        news_item['date'] = item.get('time', current_date)  # time이 있으면 사용, 없으면 현재 날짜
                        processed_news.append(news_item)
                
                if processed_news:
                    significant_moves['news'] = processed_news
                    self.logger.info(f"Processed {len(processed_news)} news items with date: {current_date}")
            
            print("\n처리된 데이터:")
            for key, value in significant_moves.items():
                if key != 'news':
                    print(f"\n{key}:")
                    for k, v in value.items():
                        print(f"- {k}: {v}")
            
            return significant_moves
            
        except Exception as e:
            self.logger.error(f"Error preparing analysis data: {e}")
            print(f"데이터 처리 중 오류 발생: {e}")
            # 시장 데이터만 있으면 계속 진행
            if 'biggest_gainer' in significant_moves or 'biggest_loser' in significant_moves:
                return significant_moves
            raise

    # 개별 시장 분석 관련 메서드 주석 처리
    """
    def _create_individual_analysis_prompt(self, data: Dict) -> str:
        # 개별 이슈 분석을 생성하는 프롬프트
        pass

    def _format_individual_analysis(self, analysis: str) -> str:
        # 개별 이슈 분석을 포맷팅하는 메서드
        pass
    """

    def _create_market_commentary_prompt(self, data: Dict) -> str:
        """시장 데이터를 바탕으로 종합적인 시장 분석 프롬프트를 만듭니다.
        첫 번째 API 호출을 위한 프롬프트로, 철저한 데이터 분석에 집중합니다.
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 기본 템플릿
        template = f"""다음 시장 데이터를 바탕으로 {current_date} 시장 분석 및 종목 추천 리포트를 작성해주세요.
이 분석은 첫 번째 단계로, 데이터에 기반한 객관적이고 전문적인 분석에 집중해야 합니다.

시장 주요 지표:
"""
        
        # 뉴스 데이터 우선 처리 (있는 경우에만)
        if 'news' in data and data['news']:
            template += """
1. 주요 시장 뉴스 (시장 및 종목 영향 분석)
"""
            # 뉴스 우선순위에 따라 정렬
            priority_keywords = {
                'high': ['실적', '계약', '특허', '인수합병', '정책', '규제', '기술개발', '금리', '인플레이션'],
                'medium': ['시장점유율', '신제품', '투자', '협력', '파트너십', '경쟁', '전망'],
                'low': ['일반뉴스', '인사', '기타']
            }
            
            for item in data['news']:
                title = item['title'].lower()
                priority = 'low'
                for level, keywords in priority_keywords.items():
                    if any(keyword in title for keyword in keywords):
                        priority = level
                        break
                
                template += f"- [{priority.upper()}] {item['title']}\n"

        # 시장 데이터 추가
        if 'biggest_gainer' in data:
            template += f"""
2. 상승 주도주 심층 분석
- 종목: {data['biggest_gainer']['Name']} ({data['biggest_gainer']['Symbol']})
- 현재가: {data['biggest_gainer']['Price']}
- 상승률: {data['biggest_gainer']['Change %']}%
- 거래량: {data['biggest_gainer'].get('Volume', 'N/A')}
- 분석 포인트: 이 종목의 상승 배경과 해당 업종 내에서의 포지셔닝, 향후 전망
"""

        if 'biggest_loser' in data:
            template += f"""
3. 하락 주도주 심층 분석
- 종목: {data['biggest_loser']['Name']} ({data['biggest_loser']['Symbol']})
- 현재가: {data['biggest_loser']['Price']}
- 하락률: {data['biggest_loser']['Change %']}%
- 거래량: {data['biggest_loser'].get('Volume', 'N/A')}
- 분석 포인트: 하락의 구조적 원인과 단기적 요인 구분, 반등 가능성 평가
"""

        if 'biggest_active' in data:
            template += f"""
4. 거래대금 상위 종목 심층 분석
- 종목: {data['biggest_active']['Name']} ({data['biggest_active']['Symbol']})
- 현재가: {data['biggest_active']['Price']}
- 등락률: {data['biggest_active']['Change %']}%
- 거래량: {data['biggest_active'].get('Volume', 'N/A')}
- 분석 포인트: 이례적 거래량 발생 원인과 가격 흐름과의 연관성 분석
"""

        # 추천 종목 정보 추가
        if 'recommendations' in data and data['recommendations']:
            template += """
5. 추천 종목 분석 (기술적/기본적 분석 기반)
각 종목에 대해 다음 사항을 포함하여 분석하세요:
- 기술적 지표가 시사하는 의미
- 투자 포인트와 주의해야 할 위험 요소
- 해당 산업 내 경쟁력과 차별화 요소
- 최근 뉴스가 해당 종목에 미치는 영향
"""
            for idx, rec in enumerate(data['recommendations'], 1):
                template += f"""
{idx}. {rec['name']} ({rec['symbol']})
- 현재가: {rec['price']}
- 등락률: {rec['change_pct']}%
- 기술적 분석:
  * RSI: {rec['rsi']:.2f} (과매수: >70, 과매도: <30)
  * MACD: {rec['macd']:.2f}
- 기본적 분석:
  * 시가총액: {rec.get('market_cap', 'N/A')}
  * 섹터: {rec.get('sector', 'N/A')}
  * 산업: {rec.get('industry', 'N/A')}
- 데이터 포인트:
  * 거래량: {rec.get('volume', 'N/A')}
  * 추천점수: {rec['score']}점
"""

        template += """
6. 종합 시장 분석 및 투자 전략
- 현재 시장 국면 진단
- 주요 경제지표와 시장 흐름 상관관계
- 단기/중기 시장 전망
- 섹터별 투자 접근법
- 리스크 요인과 대응 전략

분석 요구사항:
1. 데이터에 기반한 철저한 분석 수행
   - 현 시장 상황에 대한 객관적이고 정확한 평가
   - 각 지표와 데이터가 시사하는 의미 명확히 설명
   - 상관관계와 인과관계 구분
   - 뉴스가 시장과 종목에 미치는 영향 분석

2. 기술적/기본적 분석 통합
   - 기술적 지표(RSI, MACD 등)의 상세한 해석
   - 업종 및 산업 분석
   - 밸류에이션 관점 평가

3. 종목 추천 근거
   - 각 추천 종목의 투자 근거 명확히 제시
   - 해당 종목의 강점과 약점 균형있게 분석
   - 종목별 차별화 요소와 투자 매력도 평가

분석 결과물:
- 각 섹션별 심층적이고 데이터 기반의 분석
- 요약이나 단순 나열 금지, 각 포인트에 대한 충분한 설명 필요
- 현재 시장 상황을 정확히 반영한 분석
- 특수기호나 이모지는 사용하지 않음
"""
        
        return template

    def _create_title_from_commentary_prompt(self, commentary: str) -> str:
        """시장 논평을 바탕으로 제목을 생성하는 프롬프트를 만듭니다."""
        return f"""다음 시장 논평을 바탕으로 블로그 포스팅의 제목을 작성해주세요.

시장 논평: {commentary}

제목 작성 요구사항:
- 소비자들에게 불필요한 설명이나 내용, 강조표시를 제거하기 (예 : 프롬프트의 내용을 반영했다는 글)
- 핵심이슈와 시장에 대한 영향력 강조
- 종합적인 시장의 핵심 이슈를 반영해서 하나만 작성
- 별표(*)나 다른 특수문자는 사용하지 않음

제목 예시:
- [종목추천]금리 불확실성 속 1.8% 하락… 어떤 종목이 유망할까?
- [종목추천]테크주 약세 vs 금융주 강세…시장 분화 속 어떤 종목을?
- [종목추천]10년물 금리 4.5% 돌파…시장 어떤 종목에 주목?

유의사항:
- 소비자들에게 불필요한 설명이나 내용, 강조표시를 제거하기 (예 : 프롬프트의 내용을 반영했다는 글)
- 개별 종목명보다는 업종이나 시장 전체의 흐름을 반영
- 전문적이지만 졸언 금지
"""

    def _format_news_list(self, news: List[Dict]) -> str:
        """뉴스 목록을 포맷팅합니다."""
        return "\n".join([f"- {item['title']}" for item in news])

    def _get_deepseek_analysis(self, prompt: str, max_retries=3, timeout=60) -> str:
        """DeepSeek API를 호출하여 분석 결과를 얻습니다.
        (수정: 2단계 가다듬기 프롬프트에 줄바꿈 유지 지침 추가)
        (수정: 진단을 위해 가다듬기 단계 임시 비활성화)
        """
        for attempt in range(max_retries):
            try:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                # 첫 번째 API 호출 (분석 중심)
                analysis_payload = {
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.6, 
                    "max_tokens": 1500 # 분석 단계 토큰은 유지
                }
                
                print(f"1단계: 데이터 분석 생성 중... (시도 {attempt+1}/{max_retries}) (가다듬기 비활성화됨)")
                response = requests.post(
                    'https://api.deepseek.com/v1/chat/completions',
                    headers=headers,
                    json=analysis_payload,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    analysis_result = response.json()['choices'][0]['message']['content']
                    analysis_result = analysis_result.replace('*', '') # 별표 제거는 유지
                    
                    # 제목 생성의 경우 바로 반환 (기존 로직 유지)
                    if "제목을 작성해주세요" in prompt:
                        return analysis_result.strip()
                    
                    # === 진단을 위해 2단계 API 호출 (가다듬기) 임시 비활성화 ===
                    print("⚠ 2단계 가다듬기 비활성화됨. 1단계 원본 분석 결과 반환.")
                    return analysis_result.strip() # 1단계 결과 바로 반환
                    # ======================================================

                    # --- 기존 2단계 API 호출 (가다듬기) 코드 (현재는 실행되지 않음) ---
                    # refinement_prompt = f"""... (기존 가다듬기 프롬프트) ..."""
                    # refinement_payload = { ... }
                    # print("2단계: 소비자용 콘텐츠로 가다듬는 중 (줄바꿈 유지 강조)...")
                    # refinement_response = requests.post(...)                   
                    # if refinement_response.status_code == 200:
                    #     refined_result = ...
                    #     print("✓ 양질의 블로그 콘텐츠 생성 완료")
                    #     return refined_result.strip()
                    # else:
                    #     self.logger.error(f"다듬기 API 오류: ...")
                    #     print("⚠ 가다듬기 실패, 원본 분석 결과 사용")
                    #     return analysis_result # 가다듬기 실패 시 1단계 결과 반환
                    # --- 코드 끝 ---
                else:
                    # ... (기존 오류 처리 로직) ...
                    self.logger.error(f"API 오류 (시도 {attempt+1}): {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"재시도 대기 중... ({wait_time}초)")
                        time.sleep(wait_time)
                        continue
                    return "시장 분석 생성에 실패했습니다. 잠시 후 다시 시도해 주세요."
                    
            except requests.exceptions.Timeout:
                # ... (기존 타임아웃 처리 로직) ...
                self.logger.error(f"API 타임아웃 (시도 {attempt+1})")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"타임아웃 발생, 재시도 중... ({wait_time}초)")
                    time.sleep(wait_time)
                else:
                    return "시장 분석 생성에 실패했습니다. 서버 응답이 지연되고 있습니다."
                    
            except Exception as e:
                # ... (기존 예외 처리 로직) ...
                self.logger.error(f"API 호출 오류 (시도 {attempt+1}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"오류 발생, 재시도 중... ({wait_time}초)")
                    time.sleep(wait_time)
                else:
                    return "시장 분석 생성에 실패했습니다. 시스템 오류가 발생했습니다."
        
        return "시장 분석 생성에 실패했습니다. 여러 번 시도했으나 응답을 받지 못했습니다."

    def _create_fallback_content(self, data: Dict = None) -> Dict:
        """분석 실패 시 대체 내용을 생성합니다."""
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        if data:
            # 데이터가 있는 경우 이를 활용한 대체 내용 생성
            fallback_title = f"{current_date} 글로벌 시장 동향"
            
            fallback_commentary = f"""오늘의 시장 동향을 분석해보겠습니다.

주요 시장 지표:
"""
            if 'biggest_gainer' in data:
                fallback_commentary += f"""
- 상승 주도주: {data['biggest_gainer']['Name']} ({data['biggest_gainer']['Change %']}%)
"""
            if 'biggest_loser' in data:
                fallback_commentary += f"""
- 하락 주도주: {data['biggest_loser']['Name']} ({data['biggest_loser']['Change %']}%)
"""
            if 'biggest_active' in data:
                fallback_commentary += f"""
- 거래대금 상위: {data['biggest_active']['Name']} ({data['biggest_active']['Change %']}%)
"""
            if 'news' in data:
                fallback_commentary += "\n주요 시장 뉴스:\n"
                for item in data['news']:
                    fallback_commentary += f"- {item['title']}\n"
                    
            if 'recommendations' in data and data['recommendations']:
                fallback_commentary += "\n오늘의 추천 종목:\n"
                for idx, rec in enumerate(data['recommendations'], 1):
                    fallback_commentary += f"""
{idx}. {rec['name']} ({rec['symbol']})
- 현재가: {rec['price']}
- 등락률: {rec['change_pct']}%
- 추천 점수: {rec['score']}
- RSI: {rec['rsi']:.2f}
- MACD: {rec['macd']:.2f}
- 거래량: {rec.get('volume', 'N/A')}
- 시가총액: {rec.get('market_cap', 'N/A')}
- 섹터: {rec.get('sector', 'N/A')}
- 산업: {rec.get('industry', 'N/A')}
"""
        else:
            # 데이터가 없는 경우 기본 대체 내용
            fallback_title = f"오늘의 시장 동향 분석 - {current_date}"
            fallback_commentary = "시스템 오류로 인해 분석을 완료하지 못했습니다. 잠시 후 다시 시도해 주시기 바랍니다."
        
        return {
            "title": fallback_title,
            "commentary": fallback_commentary,
            "recommendations": data.get('recommendations', []) if data else []
        }

    def _create_fallback_title(self, data: Dict) -> str:
        """분석 실패 시 대체 제목을 생성합니다."""
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        if 'biggest_gainer' in data and 'biggest_loser' in data:
            return f"{current_date} 글로벌 시장: {data['biggest_gainer']['Name']}↑ vs {data['biggest_loser']['Name']}↓"
        else:
            return f"{current_date} 글로벌 시장 동향"

    def analyze_market_data(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """시장 데이터를 분석합니다."""
        try:
            # 데이터 요약 출력 (확인 프롬프트 제거)
            print("\n처리된 데이터:\n")
            
            # Gainer 정보
            biggest_gainer = self._get_biggest_mover(market_data['gainers'], 'Change %', ascending=False)
            print("biggest_gainer:")
            print(f"- Name: {biggest_gainer['Name']}")
            print(f"- Symbol: {biggest_gainer['Symbol']}")
            print(f"- Price: {biggest_gainer['Price']}")
            print(f"- Change_Pct: +{abs(biggest_gainer['Change %']):.2f}\n")
            
            # Loser 정보
            biggest_loser = self._get_biggest_mover(market_data['losers'], 'Change %', ascending=True)
            print("biggest_loser:")
            print(f"- Name: {biggest_loser['Name']}")
            print(f"- Symbol: {biggest_loser['Symbol']}")
            print(f"- Price: {biggest_loser['Price']}")
            print(f"- Change_Pct: {biggest_loser['Change %']:.2f}\n")
            
            # Most Active 정보
            biggest_most_active = self._get_biggest_mover(market_data['most_active'], 'Change %', ascending=False)
            print("biggest_most_activ:")
            print(f"- Name: {biggest_most_active['Name']}")
            print(f"- Symbol: {biggest_most_active['Symbol']}")
            print(f"- Price: {biggest_most_active['Price']}")
            print(f"- Change_Pct: {biggest_most_active['Change %']:.2f}\n")
            
            print("시장 분석 진행 중...")
            
            # 분석 진행 (자동)
            analysis_data = {
                'biggest_gainer': biggest_gainer,
                'biggest_loser': biggest_loser,
                'biggest_most_active': biggest_most_active,
                'market_data': market_data
            }
            
            return analysis_data
            
        except Exception as e:
            self.logger.error(f"데이터 분석 중 오류 발생: {e}")
            return None

    def _analyze_data(self, market_data: Dict[str, pd.DataFrame]) -> Dict:
        """시장 데이터를 분석합니다."""
        try:
            # 상승/하락/거래량 상위 종목 분석
            biggest_gainer = self._get_biggest_mover(market_data['gainers'], '% Change', ascending=False)
            biggest_loser = self._get_biggest_mover(market_data['losers'], '% Change', ascending=True)
            biggest_active = self._get_biggest_mover(market_data['most_active'], '% Change', ascending=False)
            
            # 분석 결과
            analysis = {
                'biggest_gainer': biggest_gainer,
                'biggest_loser': biggest_loser,
                'biggest_active': biggest_active
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"데이터 분석 오류: {e}", exc_info=True)
            return {}

    def _create_blog_content(self, analysis: dict) -> Tuple[str, str]:
        """분석 결과를 바탕으로 블로그 포스팅 내용을 생성합니다.
        (수정: 단일 문자열 반환으로 복구)
        """
        current_time = datetime.now()
        title = f"[종목추천] {current_time.strftime('%Y-%m-%d')} 오늘의 추천종목"
        
        # 섹션별 내용 생성
        sections = [
            f"# {title}", # 제목 포함 (포스팅 시 본문에 제목이 들어가지 않도록 주의)
            f"안녕하세요, {current_time.strftime('%m월 %d일')} 글로벌 시장의 주요 동향에 맞는 종목을 추천해드립니다.",
            self._create_market_trend_section(analysis),
            self._create_recommendations_section(analysis),
            self._create_news_section(analysis),
            self._create_strategy_section()
        ]
        
        # None 또는 빈 문자열인 섹션 제외하고 \n\n 으로 연결
        final_content = "\n\n".join(filter(None, [s.strip() if s else None for s in sections]))
        
        # 이모지 제거 (필요시)
        # emoji_list = [...]
        # for emoji in emoji_list:
        #     final_content = final_content.replace(emoji, "")
        
        # 제목과 최종 문자열 반환
        return title, final_content.strip() 

    def _create_market_trend_section(self, analysis: dict) -> str:
        """주요 시장 동향 섹션 생성"""
        if 'biggest_gainer' in analysis and analysis['biggest_gainer'] and \
           'biggest_loser' in analysis and analysis['biggest_loser']:
            gainer = analysis['biggest_gainer']
            loser = analysis['biggest_loser']
            return f"""## 주요 시장 동향

오늘 시장에서는 {gainer['Name']}와 {loser['Name']} 간의 뚜렷한 대비가 나타났습니다.

### 상승 주도주 분석
{gainer['Name']}({gainer['Symbol']})는 오늘 {gainer['Change %']:.2f}%의 상승세를 보였습니다. 현재 {gainer['Price']}에 거래되고 있으며, 이러한 강한 상승 흐름은 최근 시장의 관심이 집중되고 있음을 시사합니다.

### 주의 필요 종목
반면 {loser['Name']}({loser['Symbol']})은 {loser['Change %']:.2f}%의 하락을 보이며 현재 {loser['Price']}에 거래되고 있습니다. 이는 단기적인 조정인지 아니면 더 장기적인 약세 신호인지 면밀한 모니터링이 필요합니다."""
        else:
            self.logger.warning("주요 시장 동향 섹션 생성 실패: 데이터 누락")
            return "## 주요 시장 동향\n\n주요 시장 동향 데이터를 분석하는 중 오류가 발생했거나 데이터가 부족합니다."

    def _create_recommendations_section(self, analysis: dict) -> str:
        """오늘의 투자 유망 종목 섹션 생성"""
        if 'recommendations' in analysis and analysis['recommendations']:
            section_parts = [
                "## 오늘의 투자 유망 종목",
                "시장 상황을 종합적으로 분석한 결과, 다음 종목들이 현재 시장 환경에서 관심을 가질 만한 투자 기회를 제공할 수 있습니다:"
            ]
            
            stock_analysis_parts = []
            for i, stock in enumerate(analysis['recommendations'], 1):
                try:
                    stock_str = self._format_single_recommendation(i, stock)
                    stock_analysis_parts.append(stock_str)
                except Exception as stock_e:
                    self.logger.error(f"종목 {stock.get('symbol', 'N/A')} 처리 중 오류: {stock_e}")
                    stock_analysis_parts.append(f"### {i}. {stock.get('name', 'N/A')} ({stock.get('symbol', 'N/A')})\n\n[분석 중 오류가 발생했습니다.]")
            
            # 각 종목 분석 사이에 줄바꿈을 추가하여 연결
            section_parts.append("\n\n".join(stock_analysis_parts))
            return "\n\n".join(section_parts) # 섹션 제목, 소개 문장, 종목 분석 목록 연결
        else:
            self.logger.warning("오늘의 투자 유망 종목 섹션 생성 실패: 데이터 누락")
            return "## 오늘의 투자 유망 종목\n\n추천 종목 데이터를 분석하는 중 오류가 발생했거나 데이터가 부족합니다."

    def _format_single_recommendation(self, index: int, stock: dict) -> str:
        """개별 추천 종목의 분석 내용을 포맷팅합니다."""
        # 데이터 추출 및 기본값 설정
        score = round(float(stock.get('score', 0)), 2)
        rsi = round(float(stock.get('rsi', 0)), 2)
        macd = round(float(stock.get('macd', 0)), 2)
        change_pct = round(float(stock.get('change_pct', 0)), 2)
        price = stock.get('price', 'N/A')
        symbol = stock.get('symbol', 'N/A')
        name = stock.get('name', 'N/A')
        sector = stock.get('sector', 'N/A')
        industry = stock.get('industry', 'N/A')
        volume = stock.get('volume', 'N/A')
        market_cap = stock.get('market_cap', 'N/A')

        # 분석 내용 생성
        industry_analysis = self._get_industry_analysis(stock)
        rsi_interpretation = self._interpret_rsi(rsi, change_pct, industry)
        macd_interpretation = self._interpret_macd(macd, change_pct)
        volume_interpretation = self._interpret_volume(volume)
        market_cap_interpretation = self._interpret_market_cap(market_cap)
        industry_sector_analysis = self._get_industry_sector_analysis(stock)
        company_positioning = self._get_company_positioning(stock, change_pct)
        score_interpretation = self._interpret_score(score, name, industry, change_pct)

        # 최종 문자열 조합 (헤더 부분 수정)
        header = f"### {index}. {name} ({symbol})\n현재 {price}에 거래되며 {change_pct}%의 움직임을 보이고 있는 {name}은(는) {sector} 섹터의 {industry} 산업에 속해 있습니다."
        
        tech_analysis = (
            f"\n**기술적 분석 포인트:**\n"
            f"- RSI: {rsi:.2f}는 {rsi_interpretation}\n"
            f"- MACD: {macd:.2f}는 {macd_interpretation}\n"
            f"- 거래량: {volume}는 {volume_interpretation}\n"
            f"- 시가총액: {'$' + str(market_cap) if market_cap != 'N/A' else market_cap} ({market_cap_interpretation})"
        )
        industry_env = f"\n**산업 환경:**\n\n{industry_analysis}\n\n특히 {industry} 산업은 현재 {industry_sector_analysis}\n\n{name}의 경우, {company_positioning}"
        overall_eval = f"\n**종합 평가:**\n\n{score_interpretation}"
        
        # Join sections with double newlines for paragraph breaks
        return f"{header}\n\n{tech_analysis}\n\n{industry_env}\n\n{overall_eval}"

    def _create_news_section(self, analysis: dict) -> str:
        """주요 시장 뉴스 섹션 생성 (줄바꿈 개선)"""
        if 'news' in analysis and analysis['news']:
            news_items = [f"- {str(item.get('title', 'N/A')).strip()}" for item in analysis['news']]
            intro_sentence = "오늘의 핵심 뉴스는 시장 전반과 추천 종목들에 직접적인 영향을 미칠 수 있습니다:"
            # Add double newline after intro for paragraph break
            news_list_str = "\n".join(news_items)
            return f"## 주요 시장 뉴스\n\n{intro_sentence}\n\n{news_list_str}"
        else:
            self.logger.warning("주요 시장 뉴스 섹션 생성 실패: 데이터 누락")
            return None

    def _create_strategy_section(self) -> str:
        """투자 전략 제언 섹션 생성 (줄바꿈 최종 수정)"""
        # Add double newlines between numbered points and before disclaimer
        # Add newline before the section title
        return f""" \n## 투자 전략 제언

현재 시장 상황을 고려할 때, 다음과 같은 투자 접근법이 효과적일 수 있습니다:

1. 선별적 매수 전략: 상기 추천 종목들 중 산업 전망이 밝고 기술적 지표가 양호한 종목을 중심으로 분할 매수 전략을 고려해볼 수 있습니다.

2. 분산 투자 유지: 시장 변동성이 큰 상황에서는 특정 섹터에 집중하기보다 다양한 산업군에 분산 투자하는 것이 리스크 관리에 효과적입니다.

3. 기술적 지표 활용: RSI와 MACD 등의 지표를 통해 과매수/과매도 영역에서의 매매 타이밍을 참고하세요.


본 분석은 투자 제안이 아닌 정보 제공 목적으로 작성되었습니다.

실제 투자는 본인의 판단과 책임 하에 신중하게 진행해주시기 바랍니다.

오늘도 성공적인 투자 되시길 바랍니다."""

    # --- Helper methods for content creation ---
    def _get_industry_analysis(self, stock: dict) -> str:
        sector = stock.get('sector', '')
        if 'Healthcare' in sector: return "헬스케어 섹터는 고령화 사회와 의료 기술 발전에 따라 장기적 성장성이 높은 분야입니다."
        if 'Technology' in sector: return "기술 섹터는 디지털 전환 가속화와 AI 도입 확대로 계속해서 성장이 기대되는 영역입니다."
        if 'Consumer' in sector: return "소비자 관련 섹터는 경기 회복 기대감과 소비 패턴 변화를 주목해야 합니다."
        if 'Financial' in sector: return "금융 섹터는 금리 환경 변화에 민감하게 반응하며, 현재 시장 상황에서 면밀한 관찰이 필요합니다."
        if 'Basic Materials' in sector: return "원자재 섹터는 글로벌 공급망 이슈와 인프라 투자 확대로 주목받고 있습니다."
        return f"{sector or '일반'} 섹터 내에서 해당 종목의 시장 점유율과 경쟁력을 평가해볼 필요가 있습니다."
        
    def _interpret_rsi(self, rsi: float, change_pct: float, industry: str) -> str:
        if rsi > 70: return f"과매수 영역에 진입해 있습니다. 일반적으로 이는 단기 조정 가능성을 의미하지만, {change_pct}%라는 강한 상승률과 함께 고려하면 상승 추세의 강도가 매우 강함을 시사합니다. RSI가 70을 넘어선 채 유지되는 강한 상승장에서는 종종 추가 상승이 이어지는 경우가 많습니다. 특히 {industry} 업종의 전반적인 성장세와 함께 이 추세가 지속될 가능성이 높습니다."
        if rsi < 30: return f"과매도 영역에 있어 기술적 반등 가능성이 높습니다. 이는 시장이 해당 종목을 과도하게 비관적으로 평가하고 있음을 의미하며, 역발상 투자 기회를 제공합니다. {industry} 산업의 장기적 가치와 이 종목의 펀더멘털을 고려할 때, 현재 가격은 진입 기회로 평가됩니다. 과거 이와 유사한 RSI 수준에서는 평균 15-20% 내외의 반등이 있었습니다."
        return f"중립 구간에 위치하고 있어 균형 잡힌 흐름을 보이고 있습니다. 이는 과도한 낙관이나 비관에 치우치지 않은 건전한 상태로, {rsi}라는 수치는 {'상승 추세로의 진입 초기 단계로 볼 수 있습니다.' if 40 <= rsi < 60 else '하락 추세가 완화되며 반등을 준비하는 단계로 해석됩니다.' if 30 <= rsi < 40 else '상승 모멘텀이 강화되고 있음을 시사합니다.' if 60 <= rsi < 70 else '중립적 관망이 필요한 구간입니다.'}"

    def _interpret_macd(self, macd: float, change_pct: float) -> str:
        if macd > 0: return f"양의 값을 보이며 상승 추세가 우세함을 나타냅니다. 이는 단기 이동평균선이 장기 이동평균선을 상회하고 있음을 의미하며, 추세의 방향성이 상승임을 확인해주는 지표입니다. 특히 {change_pct}%의 최근 가격 변동과 함께 고려하면, {'추세의 초기 단계로 추가 상승 여력이 있다고 볼 수 있습니다.' if change_pct < 10 else '강한 상승 추세가 확립되어 있으나 단기적 과열 여부를 체크할 필요가 있습니다.' if change_pct > 30 else '상승 추세가 지속되고 있으며 모멘텀이 유지되고 있습니다.'}"
        return f"음의 값을 보이고 있으나 {abs(macd):.2f}의 값은 {'약한 하락 압력을 의미하며, 반등 가능성을 모색할 단계입니다.' if abs(macd) < 0.5 else '뚜렷한 하락 추세를 나타내며, 추세 전환 신호를 확인한 후 접근하는 것이 바람직합니다.' if abs(macd) > 1 else '중간 강도의 하락 추세를 보이고 있으나, RSI 등 다른 지표와 함께 고려할 때 기술적 반등 가능성도 있습니다.'}"

    def _interpret_volume(self, volume_str: str) -> str:
        try:
            if 'M' in str(volume_str) or 'B' in str(volume_str):
                return '높은 거래량으로 시장의 강한 관심이 집중되고 있음을 의미합니다.'
            return '적정 수준의 거래량으로 안정적인 가격 형성을 시사합니다.'
        except: return '거래량 정보 확인 불가'

    def _interpret_market_cap(self, market_cap_str: str) -> str:
        try:
            mc = int(str(market_cap_str).replace(',', ''))
            if mc > 10_000_000_000: return '대형주로 안정적인 기업 가치를 보유하고 있습니다.'
            if mc > 1_000_000_000: return '중형주로 성장과 안정성을 겸비하고 있습니다.'
            return '소형주로 높은 성장 잠재력을 가지고 있습니다.'
        except: return '시가총액 정보 확인 불가'

    def _get_industry_sector_analysis(self, stock: dict) -> str:
        sector = stock.get('sector', '')
        if 'Technology' in sector or 'Healthcare' in sector: return '글로벌 공급망 회복과 디지털 전환 가속화에 힘입어 구조적 성장이 예상됩니다.'
        if 'Financial' in sector or 'Real Estate' in sector: return '금리 환경 변화와 인플레이션 추세에 영향을 받고 있어 선별적 접근이 필요합니다.'
        if 'Consumer' in sector: return '소비자 심리와 경기 회복 속도에 민감하게 반응하는 특성을 보이고 있습니다.'
        return '산업 재편과 정책 변화에 따른 구조적 변화가 진행 중입니다.'

    def _get_company_positioning(self, stock: dict, change_pct: float) -> str:
        if change_pct > 20: return '업계 내 혁신 기술과 차별화된 비즈니스 모델을 바탕으로 높은 성장성을 인정받고 있습니다.'
        if -5 < change_pct < 5: return '안정적인 수익 구조와 견고한 시장 점유율을 바탕으로 방어적 특성을 갖추고 있습니다.'
        if change_pct < -5: return '현재의 가격 조정은 기업 가치 대비 투자 기회로 볼 여지가 있습니다.'
        return '업종 평균을 상회하는 실적과 함께 시장의 재평가가 진행 중입니다.'
        
    def _interpret_score(self, score: float, name: str, industry: str, change_pct: float) -> str:
        """점수 해석 및 투자 전략 제안 텍스트 생성 (줄바꿈 수정)"""
        score_intro = f"종합점수 {score}점으로, 현재 시장 환경에서는"
        # strategy_title already contains the desired \n\n before the markdown title
        strategy_title = " \n\n**투자 전략 제안:**"

        if score > 80:
            analysis_text = f"매우 유망한 투자 기회로 판단됩니다. 이 점수는 단순한 기술적 지표만이 아닌, 산업 동향, 모멘텀, 기업의 시장 내 포지셔닝을 종합적으로 고려한 결과입니다. {score}점이라는 높은 점수는 현재의 시장 상황과 {name}의 특성이 매우 잘 맞아떨어지고 있음을 의미합니다."
            strategy_text = f"{change_pct}%의 최근 상승을 고려할 때, 한 번에 모든 자금을 투입하기보다 2-3회에 걸친 분할 매수 전략이 리스크 관리에 효과적입니다. 특히 추가 상승 가능성이 높은 만큼, 첫 포지션은 현재 가격에서, 나머지는 5-7% 내외의 조정 시 추가하는 전략을 고려해볼 수 있습니다."
            # Combine intro, analysis, title (with \n\n), and strategy text with single newlines
            return f"{score_intro}\n{analysis_text}{strategy_title}\n{strategy_text}"
        elif score > 60:
            analysis_text = f"유망한 투자 대상으로 평가됩니다. {score}점의 종합 점수는 이 종목이 현재 시장에서 상위 30% 내외의 투자 매력도를 가지고 있음을 시사합니다. 특히 {industry} 산업 내에서 비교 우위를 점하고 있으며, 기술적 지표와 펀더멘털이 균형을 이루고 있습니다."
            strategy_text = f"중장기적 관점에서 포트폴리오 구성 요소로 적합하며, 현재 가격대는 3-6개월의 투자 시계에서 적절한 진입점으로 판단됩니다. RSI와 MACD 지표의 방향성을 추가로 모니터링하며 점진적인 포지션 구축을 권장합니다."
            # Combine intro, analysis, title (with \n\n), and strategy text with single newlines
            return f"{score_intro}\n{analysis_text}{strategy_title}\n{strategy_text}"
        else: # score <= 60
            analysis_text = f"중립적 관점에서 관찰이 필요한 종목입니다. {score}점은 현 시점에서 적극적 매수보다는 모니터링을 통한 상황 변화 관찰이 필요함을 시사합니다. 특히 {name}의 최근 {change_pct}% 가격 변동은 {'단기적 조정이 더 이어질 가능성을 배제할 수 없으므로, 명확한 바닥 형성 후 접근하는 것이 안전합니다.' if change_pct < 0 else '상승 추세의 지속 가능성을 추가로 확인할 필요가 있습니다.'}"
            strategy_text = f"현 단계에서는 소규모 초기 포지션 구축 후, 추세 확인에 따라 추가 매수를 고려하는 전략이 적합합니다. 특히 {industry} 산업의 전반적 흐름과 {name}의 실적 발표 일정을 함께 고려한 접근이 중요합니다."
            # Combine intro, analysis, title (with \n\n), and strategy text with single newlines
            return f"{score_intro}\n{analysis_text}{strategy_title}\n{strategy_text}"

    def _generate_market_tags(self, title: str, content: str, analysis: dict) -> List[str]:
        """글의 내용에 따라 적절한 태그를 생성합니다. (제공된 로직 기반)"""
        # 기본 태그 (항상 포함)
        base_tags = [
            "주식시장", "증권", "주식투자", "미국주식", "글로벌경제",
            "시장분석", "투자정보", "주식정보", "시장동향", "금융시장"
        ]
        
        # 시장 상황별 태그
        market_condition_tags = {
            "상승": ["주식상승", "매수전략", "상승장", "강세장", "매수기회"],
            "하락": ["주식하락", "매도전략", "하락장", "약세장", "리스크관리"],
            "변동성": ["변동성장세", "리스크관리", "투자전략", "자산관리", "포트폴리오"]
        }
        
        # 자산군 태그
        asset_tags = {
            "주식": ["개별주식", "성장주", "가치주", "배당주", "기술주"],
            "원자재": ["원자재", "금", "은", "원유", "commodities"],
            "채권": ["채권", "국채", "회사채", "금리", "채권투자"],
            "환율": ["환율", "달러", "외환시장", "달러인덱스", "외환"]
        }
        
        # 글의 내용에서 키워드 분석 (content만 사용)
        content_lower = content.lower()
        selected_tags = set(base_tags)  # 중복 방지를 위해 set 사용
        
        # 시장 상황 태그 추가
        if any(word in content_lower for word in ["상승", "급등", "강세", "매수"]):
            selected_tags.update(market_condition_tags["상승"])
        if any(word in content_lower for word in ["하락", "급락", "약세", "매도"]):
            selected_tags.update(market_condition_tags["하락"])
        if any(word in content_lower for word in ["변동성", "불확실성", "리스크"]):
            selected_tags.update(market_condition_tags["변동성"])
        
        # 자산군 태그 추가
        for asset_type, tags in asset_tags.items():
            # title이나 analysis 대신 content에서 키워드 검색
            if asset_type.lower() in content_lower: 
                selected_tags.update(tags)
        
        # 현재 날짜 태그 추가 (datetime 필요)
        today = datetime.now() # datetime 임포트 되어 있다고 가정
        date_tags = [
            today.strftime("%Y년%m월"), 
            today.strftime("%Y년%m월%d일"), 
            "데일리브리핑", 
            "시장브리핑"
        ]
        selected_tags.update(date_tags)

        # 종목명/심볼 태그 추가 (analysis 데이터 활용)
        if 'recommendations' in analysis:
             for stock in analysis['recommendations']:
                 name = stock.get('name')
                 symbol = stock.get('symbol')
                 if name: 
                    # 특수문자 제거 (간단히)
                    clean_name = re.sub(r'[^가-힣a-zA-Z0-9]', '', name.replace(' ', ''))
                    if clean_name:
                        selected_tags.add(clean_name.lower() if re.search(r'[a-zA-Z]', clean_name) else clean_name)
                 if symbol:
                    clean_symbol = re.sub(r'[^a-zA-Z0-9]', '', symbol)
                    if clean_symbol:
                         selected_tags.add(clean_symbol.lower())

        # 태그 리스트로 변환 및 최대 30개로 제한
        final_tags = sorted(list(selected_tags))[:30] # 정렬 후 제한
        print(f"- 생성된 태그 ({len(final_tags)}개): {final_tags}")
        return final_tags
