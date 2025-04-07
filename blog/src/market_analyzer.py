import pandas as pd
import logging
from typing import Dict, List, Any
import os
import requests
import json
from utils import parse_price_string
import time
from datetime import datetime

class MarketAnalyzer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        
        if not self.api_key:
            raise ValueError("DeepSeek API key not found in environment variables")

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

    def analyze_market_trend(self, market_data: Dict[str, pd.DataFrame], news: List[Dict]) -> Dict:
        """시장 데이터와 뉴스를 분석하여 트렌드를 파악합니다."""
        try:
            # 데이터 준비
            prepared_data = self._prepare_analysis_data(market_data, news)
            if not prepared_data:
                return self._create_fallback_content()
            
            # 종합적인 시장 논평 생성
            print("- 시장 논평 작성 중...")
            market_commentary = self._get_deepseek_analysis(self._create_market_commentary_prompt(prepared_data))
            if not market_commentary or "분석 내용 생성에 실패" in market_commentary:
                return self._create_fallback_content(prepared_data)
            print("✓ 시장 논평 작성 완료")
            
            # 논평을 바탕으로 제목 생성
            print("- 제목 생성 중...")
            title = self._get_deepseek_analysis(self._create_title_from_commentary_prompt(market_commentary))
            if not title or "분석 내용 생성에 실패" in title:
                title = self._create_fallback_title(prepared_data)
            print("✓ 제목 생성 완료")
            
            # 태그 생성
            print("- 태그 생성 중...")
            tags = self._create_tags_from_content(title, market_commentary)
            print("✓ 태그 생성 완료")
            
            # 분석 결과 구조 통일
            return {
                "title": title,
                "core_issue": market_commentary.split('\n')[0] if market_commentary else "시장 동향 분석",
                "analysis": market_commentary,
                "tags": tags
            }
            
        except Exception as e:
            self.logger.error(f"시장 분석 중 오류 발생: {e}", exc_info=True)
            return self._create_fallback_content()

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
            
            for category in ['gainers', 'losers', 'most_active']:
                if category in market_data and not market_data[category].empty:
                    df = market_data[category]
                    row = df.iloc[0]
                    
                    price, change_pct = parse_price_string(row['Price'])
                    
                    significant_moves[f'biggest_{category[:-1]}'] = {
                        'Name': row['Name'].strip(),
                        'Symbol': row['Symbol'].strip(),
                        'Price': price,
                        'Change_Pct': row['% Change'].strip('%') if '% Change' in row else change_pct
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
        """시장 데이터를 바탕으로 종합적인 논평을 생성하는 프롬프트를 만듭니다."""
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 기본 템플릿
        template = f"""다음 시장 데이터를 바탕으로 {current_date} 시장 동향에 대한 전문가적 관점의 종합적인 시장 논평을 작성해주세요.

시장 주요 지표:
"""
        
        # 시장 데이터 추가
        if 'biggest_gainer' in data:
            template += f"""
1. 상승 주도주
- 종목: {data['biggest_gainer']['Name']} ({data['biggest_gainer']['Symbol']})
- 상승률: {data['biggest_gainer']['Change_Pct']}%
"""

        if 'biggest_loser' in data:
            template += f"""
2. 하락 주도주
- 종목: {data['biggest_loser']['Name']} ({data['biggest_loser']['Symbol']})
- 하락률: {data['biggest_loser']['Change_Pct']}%
"""

        if 'biggest_active' in data:
            template += f"""
3. 거래대금 상위
- 종목: {data['biggest_active']['Name']} ({data['biggest_active']['Symbol']})
- 등락률: {data['biggest_active']['Change_Pct']}%
"""

        # 뉴스 데이터 추가 (있는 경우에만)
        if 'news' in data and data['news']:
            template += f"""
4. 주요 시장 뉴스
{self._format_news_list(data['news'])}
"""

        template += """
작성 요구사항:
- 주요 종목들의 급등락 원인과 시장 영향
- 시장 전반의 변동성과 불확실성 요인
- 섹터별 차별화 동향
- 금리, 통화정책, 경제지표와의 연관성
- 글로벌 시장 간 상호작용
- 주요 리스크 요인
- 단기 변동성 요인
- 중장기 시장 방향성
- 주요 모니터링 포인트

작성 스타일:
- 전문가적 관점에서 자연스럽게 줄글 형태로 서술
- 구체적인 데이터와 수치 활용
- 핵심 내용 중심으로 간결하게 작성
- 중복된 내용이나 반복적인 설명 제외
- 투자 조언이나 권유는 포함하지 않음
- 별표(*)나 다른 특수문자는 절대 사용하지 않음
"""
        
        return template

    def _create_title_from_commentary_prompt(self, commentary: str) -> str:
        """시장 논평을 바탕으로 제목을 생성하는 프롬프트를 만듭니다."""
        return f"""다음 시장 논평을 바탕으로 블로그 포스팅의 제목을 작성해주세요.

시장 논평: {commentary}

제목 작성 요구사항:
- 의문형으로 전문성 있게 작성
- 시장의 핵심 이슈를 반영해서 하나만 작성
- 종합적인 시장 동향을 대표할 수 있는 하나의 제목
- 별표(*)나 다른 특수문자는 사용하지 않음

제목 예시:
- S&P 500, 금리 불확실성 속 1.8% 하락… 시장 전망은?
- 테크주 약세 vs 금융주 강세…시장 분화 속 방향은?
- 10년물 금리 4.5% 돌파…시장 전환점 도래?

유의사항:
- 핵심이슈와 시장에 대한 영향력 강조
- 개별 종목명 대신 시장 전체의 흐름을 반영
- 별표(*)나 다른 특수문자는 절대 사용하지 않음
"""

    def _format_news_list(self, news: List[Dict]) -> str:
        """뉴스 목록을 포맷팅합니다."""
        return "\n".join([f"- {item['title']}" for item in news])

    def _get_deepseek_analysis(self, prompt: str, max_retries=3, timeout=60) -> str:
        """DeepSeek API를 호출하여 분석 결과를 얻습니다."""
        for attempt in range(max_retries):
            try:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                payload = {
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
                
                print(f"분석 생성 중... (시도 {attempt+1}/{max_retries})")
                response = requests.post(
                    'https://api.deepseek.com/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    result = response.json()['choices'][0]['message']['content']
                    # 결과에서 별표(*) 제거
                    result = result.replace('*', '')
                    
                    # 제목 생성의 경우 추가 다듬기 없이 바로 반환
                    if "제목을 작성해주세요" in prompt:
                        return result
                    
                    # 본문 내용인 경우에만 다듬기 진행
                    refinement_prompt = f"""다음 내용을 더 자연스럽고 전문적인 블로그 스타일로 다듬어주세요.
원문: {result}

다듬기 요구사항:
1. 하루 1번 게시되기에 현재 시황에 집중
2. 하나의 이슈에 대해서만 깊이있게 줄글로 작성하기
3. 불필요한 설명이나 내용, 강조표시를 제거하기
4. 전문적이지만 조언 금지
5. 핵심 내용은 유지하면서 자연스러운 흐름으로 재구성
6. 별표(*)나 다른 특수문자는 절대 사용하지 않음
"""
                    
                    refinement_payload = {
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "user",
                                "content": refinement_prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1500
                    }
                    
                    print("결과 다듬기 중...")
                    refinement_response = requests.post(
                        'https://api.deepseek.com/v1/chat/completions',
                        headers=headers,
                        json=refinement_payload,
                        timeout=timeout
                    )
                    
                    if refinement_response.status_code == 200:
                        refined_result = refinement_response.json()['choices'][0]['message']['content']
                        # 결과에서 별표(*) 제거
                        refined_result = refined_result.replace('*', '')
                        return refined_result
                    else:
                        self.logger.error(f"다듬기 API 오류: {refinement_response.status_code} - {refinement_response.text}")
                        return result
                else:
                    self.logger.error(f"API 오류 (시도 {attempt+1}): {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"재시도 대기 중... ({wait_time}초)")
                        time.sleep(wait_time)
                        continue
                    
                    return "시장 분석 생성에 실패했습니다. 잠시 후 다시 시도해 주세요."
                    
            except requests.exceptions.Timeout:
                self.logger.error(f"API 타임아웃 (시도 {attempt+1})")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"타임아웃 발생, 재시도 중... ({wait_time}초)")
                    time.sleep(wait_time)
                else:
                    return "시장 분석 생성에 실패했습니다. 서버 응답이 지연되고 있습니다."
                    
            except Exception as e:
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
- 상승 주도주: {data['biggest_gainer']['Name']} ({data['biggest_gainer']['Change_Pct']}%)
"""
            if 'biggest_loser' in data:
                fallback_commentary += f"""
- 하락 주도주: {data['biggest_loser']['Name']} ({data['biggest_loser']['Change_Pct']}%)
"""
            if 'biggest_active' in data:
                fallback_commentary += f"""
- 거래대금 상위: {data['biggest_active']['Name']} ({data['biggest_active']['Change_Pct']}%)
"""
            if 'news' in data:
                fallback_commentary += "\n주요 시장 뉴스:\n"
                for item in data['news']:
                    fallback_commentary += f"- {item['title']}\n"
        else:
            # 데이터가 없는 경우 기본 대체 내용
            fallback_title = f"오늘의 시장 동향 분석 - {current_date}"
            fallback_commentary = "시스템 오류로 인해 분석을 완료하지 못했습니다. 잠시 후 다시 시도해 주시기 바랍니다."
        
        return {
            "title": fallback_title,
            "commentary": fallback_commentary
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

    def format_blog_content(self, content: str) -> str:
        """블로그 포스팅용으로 콘텐츠를 포맷팅합니다."""
        try:
            # 원본 콘텐츠를 그대로 반환
            return content.strip()
            
        except Exception as e:
            self.logger.error(f"Content formatting error: {e}")
            return content  # 에러 발생 시 원본 콘텐츠 반환

    def _create_tags_from_content(self, title: str, content: str) -> List[str]:
        """제목과 본문 내용을 기반으로 태그를 생성합니다."""
        try:
            # 기본 태그 세트
            base_tag_sets = {
                "주식": ["주식", "주식투자", "주식시장", "주식분석", "주식공부"],
                "시장": ["시장분석", "시장동향", "시장전망", "시장이슈", "시장리뷰"],
                "투자": ["투자", "투자전략", "투자분석", "투자이슈", "투자전망"],
                "경제": ["경제", "경제동향", "경제이슈", "경제전망", "글로벌경제"],
                "미국": ["미국주식", "미국시장", "미국경제", "나스닥", "S&P500", "다우존스"]
            }
            
            # 섹터/산업 키워드 세트
            sector_sets = {
                "테크": ["테크", "기술", "AI", "반도체", "소프트웨어", "하드웨어", "클라우드", "메타버스"],
                "금융": ["금융", "은행", "증권", "보험", "핀테크", "디지털금융"],
                "에너지": ["에너지", "석유", "가스", "재생에너지", "태양광", "풍력", "원자력"],
                "소비재": ["소비재", "유통", "식품", "의류", "화장품", "패션", "소매"],
                "헬스케어": ["헬스케어", "바이오", "제약", "의료", "건강", "의료기기"],
                "산업재": ["산업재", "제조", "자동차", "항공", "방위", "기계", "건설"],
                "유틸리티": ["유틸리티", "전기", "가스", "수도", "인프라"],
                "부동산": ["부동산", "REITs", "상업용부동산", "주거용부동산"],
                "통신": ["통신", "텔레콤", "5G", "인터넷", "미디어", "엔터테인먼트"],
                "재료": ["재료", "화학", "철강", "비철금속", "플라스틱"]
            }
            
            # 기본 태그 선택 (각 세트에서 랜덤하게 1-2개 선택)
            base_tags = []
            for tag_set in base_tag_sets.values():
                import random
                selected = random.sample(tag_set, min(2, len(tag_set)))
                base_tags.extend(selected)
            
            # 제목에서 키워드 추출 (특수문자 제거)
            title_keywords = []
            for word in title.split():
                # 특수문자 제거
                clean_word = ''.join(c for c in word if c.isalnum() or c.isspace())
                if len(clean_word) > 1:
                    title_keywords.append(clean_word)
            
            # 본문에서 주요 키워드 추출 (특수문자 제거)
            content_keywords = []
            for line in content.split('\n'):
                if ':' in line:  # 주요 지표나 종목 정보가 있는 줄
                    key = line.split(':')[0].strip()
                    # 특수문자 제거
                    clean_key = ''.join(c for c in key if c.isalnum() or c.isspace())
                    if len(clean_key) > 1:
                        content_keywords.append(clean_key)
                elif len(line.strip()) > 0:  # 일반 텍스트 줄
                    words = line.strip().split()
                    for word in words:
                        # 특수문자 제거
                        clean_word = ''.join(c for c in word if c.isalnum() or c.isspace())
                        if len(clean_word) > 1:
                            content_keywords.append(clean_word)
            
            # 종목 심볼 추출 (특수문자 제거)
            symbols = []
            for word in title_keywords + content_keywords:
                if word.isupper() and len(word) <= 5:  # 대문자로 된 5자 이하의 단어는 종목 심볼로 간주
                    symbols.append(word)
            
            # 섹터/산업 키워드 추출 (특수문자 제거)
            sector_keywords = []
            for word in title_keywords + content_keywords:
                for sector, indicators in sector_sets.items():
                    for indicator in indicators:
                        if indicator in word:
                            sector_keywords.append(indicator)
                            break
            
            # 시장 지표 키워드 추출 (특수문자 제거)
            market_indicators = ["금리", "인플레이션", "고용", "GDP", "소비자물가", "생산자물가", 
                               "소매판매", "제조업지수", "서비스업지수", "주택가격", "실업률"]
            market_keywords = [indicator for indicator in market_indicators 
                             if any(indicator in word for word in title_keywords + content_keywords)]
            
            # 최종 태그 구성 (특수문자 제거)
            final_tags = []
            for tag in (base_tags + symbols + sector_keywords + market_keywords):
                # 특수문자 제거
                clean_tag = ''.join(c for c in tag if c.isalnum() or c.isspace())
                if len(clean_tag) > 1:
                    final_tags.append(clean_tag)
            
            # 중복 제거 및 정렬
            final_tags = sorted(list(set(final_tags)))
            
            # 태그 개수 제한 (최대 15개)
            return final_tags[:15]
            
        except Exception as e:
            self.logger.error(f"태그 생성 중 오류 발생: {e}")
            # 오류 발생 시 기본 태그 세트에서 랜덤하게 선택 (특수문자 제거)
            import random
            base_tags = ["주식", "시장분석", "투자", "경제", "미국주식"]
            return random.sample(base_tags, 3)
