import os
import sys
import yaml
from pathlib import Path
from datetime import datetime
from blog_poster import NaverBlogPoster
from market_analyzer import MarketAnalyzer
from data_collector import MarketDataCollector

def main():
    print("\n=== 네이버 블로그 포스팅 테스트 시작 ===\n")
    
    # 설정 파일 로드
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    print(f"설정 파일 경로: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"✗ 설정 파일 로드 실패: {e}")
        return
    
    # 분석 테스트 실행
    print("\n=== 시장 분석 테스트 ===")
    analyzer = MarketAnalyzer(config)
    
    # 먼저 데이터 수집
    collector = MarketDataCollector(config)
    market_data = collector.get_market_data()
    news = collector.get_market_news()
    
    # 추천 종목 생성
    print("- 종목 추천 생성 중...")
    recommendations = collector.get_stock_recommendations(market_data=market_data, num_recommendations=5)
    
    # 분석 실행
    title, content, tags, analysis = analyzer.analyze_market_trend(market_data, news)
    
    # 분석 결과에 추천 종목 추가
    if analysis:
        analysis['recommendations'] = recommendations
    
    if analysis:
        print("\n=== 분석 결과 구조 확인 ===")
        print("분석 결과 키:", list(analysis.keys()))
        
        print("\n=== 주요 분석 내용 ===")
        print(f"제목: {title}")
        
        if 'biggest_gainer' in analysis:
            bg = analysis['biggest_gainer']
            print(f"상승 주도주: {bg['Name']} ({bg['Change %']}%)")
        
        if 'biggest_loser' in analysis:
            bl = analysis['biggest_loser']
            print(f"하락 주도주: {bl['Name']} ({bl['Change %']}%)")
        
        # 추천 종목 확인
        if 'recommendations' in analysis:
            recs = analysis['recommendations']
            print(f"\n추천 종목 수: {len(recs)}")
            if recs:
                print("첫 번째 추천 종목 키:", list(recs[0].keys()))
    else:
        print("✗ 분석 실패")
        return
    
    # 테스트용 포스팅 내용
    test_title = f"테스트 포스팅 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    test_content = """# 테스트 포스팅

안녕하세요, 투자자 여러분! 오늘은 테스트 포스팅을 작성해보겠습니다.

## 오늘의 주목할 만한 움직임

### 상승 주도주 분석
오늘 가장 눈에 띄는 상승을 보인 테스트 주식 (TEST)의 움직임을 살펴보겠습니다.
현재 주가: 100.00 +10.00 (+10.00%)
이러한 강한 상승세는 시장의 높은 관심을 반영하고 있습니다.

### 주의 필요 종목
반면 테스트 하락주 (TEST2)은 다소 약세를 보였습니다.
현재 주가: 50.00 -5.00 (-10.00%)
단기적인 조정인지 추가적인 모니터링이 필요해 보입니다.

## 오늘의 투자 아이디어

시장 분석을 바탕으로 다음의 종목들이 관심을 끌고 있습니다:

### 1. 테스트 종목 1 (TEST1)
현재 100.00 +10.00 (+10.00%)에 거래되고 있습니다.

기술적 분석:
- RSI: 60.00 (과매수/과매도 판단 지표)
- MACD: 0.50 (모멘텀 지표)

종목 분석:
업종: Technology / Software
- 시가총액: 1000000000
- 거래량: 1000000
- 종합점수: 80.00점

## 주요 시장 뉴스

오늘의 핵심 뉴스를 통해 시장의 움직임을 이해해보겠습니다:
- 테스트 뉴스 1
- 테스트 뉴스 2
- 테스트 뉴스 3

## 투자 유의사항

이상의 분석은 투자 제안이 아닌 정보 제공 목적으로 작성되었습니다.
실제 투자는 본인의 판단과 책임 하에 신중하게 진행해주시기 바랍니다.

오늘도 안전하고 즐거운 투자 되세요!
"""
    test_tags = ["테스트", "블로그", "자동화", "HTML", "포맷팅테스트"]
    
    print(f"\n포스팅 정보:")
    print(f"- 제목: {test_title}")
    print(f"- 태그: {', '.join(test_tags)}")
    print(f"- 본문 길이: {len(test_content)}자")
    
    # 포스팅 진행 여부 확인
    print("\n포스팅 정보를 확인했습니다. 글을 발행하시겠습니까? (자동 승인됨)")
    
    # 블로그 포스터 초기화
    poster = NaverBlogPoster(config)
    
    # 웹드라이버 설정
    print("\n- 웹드라이버 설정 중...")
    if not poster.setup_driver():
        print("✗ 웹드라이버 설정 실패")
        return
    
    # 로그인
    print("- 네이버 로그인 시도 중...")
    if not poster.login():
        print("✗ 로그인 실패")
        poster.close()
        return
    
    # 포스팅 시도
    print("\n- 블로그 글 작성 및 발행 중...")
    success = poster.create_post(test_title, test_content, test_tags)
    
    if not success:
        print("✗ 테스트 중 오류 발생")
    
    # 웹드라이버 종료
    poster.close()
    
    print("\n=== 테스트 종료 ===\n")

if __name__ == "__main__":
    main()
