import yaml
import logging
import os
import sys
from data_collector import MarketDataCollector
from market_analyzer import MarketAnalyzer
from blog_poster import NaverBlogPoster
from datetime import datetime
from pathlib import Path
from utils import load_environment, setup_logging
import schedule
import time
from typing import Dict, Any
import pytz

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def user_confirm(message):
    """사용자 확인을 항상 승인합니다."""
    print(f"\n{message} (자동 승인됨)")
    return True  # 항상 True 반환

def get_kst_time():
    """현재 한국 시간을 반환합니다."""
    return datetime.now(KST)

def main():
    """메인 실행 함수"""
    try:
        print("\n=== 시장 분석 및 블로그 포스팅 프로그램 시작 ===\n")
        print(f"현재 한국 시간: {get_kst_time().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 환경 변수 로드
        print("환경 변수 및 설정 로드 중...")
        if not load_environment():
            print("✗ 환경 변수 설정에 실패했습니다. 프로그램을 종료합니다.")
            return
        
        # 현재 디렉토리 확인 및 설정 파일 경로 설정
        current_dir = Path(__file__).parent.parent
        config_path = current_dir / 'config' / 'config.yaml'
        
        # 설정 파일 존재 확인
        if not config_path.exists():
            print(f"✗ 설정 파일을 찾을 수 없습니다: {config_path}")
            return
            
        # 설정 파일 로드
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 로깅 설정
        logger = setup_logging(config)
        logger.info("프로그램 초기화 완료")
        print("✓ 환경 설정 로드 완료")
        
        # 데이터 수집
        print("\n1. 시장 데이터 수집 시작...")
        collector = MarketDataCollector(config)
        market_data = collector.get_market_data()
        news = collector.get_market_news()
        
        # 데이터 수집 결과 검증
        empty_categories = [k for k, df in market_data.items() if df.empty]
        if empty_categories:
            print(f"✗ 경고: 다음 카테고리의 데이터를 수집하지 못했습니다: {', '.join(empty_categories)}")
            
        if all(df.empty for df in market_data.values()):
            print("✗ 오류: 모든 시장 데이터 수집에 실패했습니다.")
            return
            
        if len(news) == 0:
            print("✗ 경고: 뉴스 데이터 수집에 실패했습니다.")
            if not user_confirm("뉴스 데이터 없이 계속하시겠습니까?"):
                print("프로그램을 종료합니다.")
                return
        
        # 수집된 데이터 확인
        print("\n수집된 데이터 요약:")
        for category, df in market_data.items():
            if not df.empty:
                print(f"- {category}: {len(df)}개 항목")
        print(f"- 뉴스: {len(news)}개 기사")
        
        if not user_confirm("수집된 데이터를 확인했습니다. 분석을 진행하시겠습니까?"):
            print("프로그램을 종료합니다.")
            return
        
        # 시장 분석
        print("\n2. 시장 분석 시작...")
        analyzer = MarketAnalyzer(config)
        analysis = analyzer.analyze_market_trend(market_data, news)
        
        # 분석 결과 확인
        print("\n=== 분석 결과 ===")
        print(f"\n제목: {analysis.get('title', '제목 생성 실패')}")
        print("\n핵심 이슈:")
        print(analysis.get('core_issue', '이슈 분석 실패'))
        print("\n본문 미리보기:")
        
        content = analysis.get('analysis', '본문 생성 실패')
        preview = content[:500] + "..." if len(content) > 500 else content
        print(preview)
        
        if not user_confirm("분석 결과를 확인했습니다. 블로그 포스팅을 진행하시겠습니까?"):
            print("프로그램을 종료합니다.")
            return
        
        # 블로그 포스팅
        print("\n3. 블로그 포스팅 시작...")
        poster = NaverBlogPoster(config)
        
        try:
            print("- 웹드라이버 설정 중...")
            if not poster.setup_driver():
                print("✗ 웹드라이버 설정에 실패했습니다.")
                return
                
            print("- 네이버 로그인 시도 중...")
            if poster.login():
                # 한국 시간 기준 현재 날짜 포맷
                today = get_kst_time().strftime('%Y-%m-%d')
                
                # 제목과 내용 준비
                title = analysis.get('title', f"오늘의 시장 동향 분석 - {today}")
                content = analysis.get('analysis', "분석 내용 생성에 실패했습니다.")
                tags = analysis.get('tags', ["주식", "시장분석", "투자", "경제", "미국주식"])
                
                print(f"\n포스팅 정보:")
                print(f"- 제목: {title}")
                print(f"- 태그: {', '.join(tags)}")
                print(f"- 본문 길이: {len(content)}자")
                
                if not user_confirm("포스팅 정보를 확인했습니다. 글을 발행하시겠습니까?"):
                    print("프로그램을 종료합니다.")
                    return
                
                print("\n- 블로그 글 작성 및 발행 중...")
                success = poster.create_post(title, content, tags)
                if success:
                    print("✓ 블로그 포스팅 완료!")
                    logger.info(f"블로그 포스팅 성공: {title}")
                else:
                    print("✗ 블로그 포스팅 실패")
                    logger.error("블로그 포스팅 실패")
            else:
                print("✗ 네이버 로그인 실패")
                logger.error("네이버 로그인 실패")
        except Exception as e:
            print(f"✗ 블로그 포스팅 중 오류 발생: {str(e)}")
            logger.error(f"블로그 포스팅 중 오류: {str(e)}", exc_info=True)
        finally:
            poster.close()
        
    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다.")
        return
    except Exception as e:
        print(f"\n✗ 오류 발생: {str(e)}")
        if 'logger' in locals():
            logger.error(f"프로그램 실행 중 오류 발생: {str(e)}", exc_info=True)
        else:
            print(f"로깅 초기화 전 오류 발생: {str(e)}")
    
    print("\n=== 프로그램 종료 ===")

if __name__ == "__main__":
    # 한국 시간 기준 매일 오전 7:30과 오후 9:00에 실행
    schedule.every().day.at("07:30").do(main)
    schedule.every().day.at("21:00").do(main)
    
    print(f"스케줄러 설정 완료. 매일 한국 시간 기준 오전 7:30과 오후 9:00에 자동 실행됩니다.")
    print(f"현재 한국 시간: {get_kst_time().strftime('%Y-%m-%d %H:%M:%S')}")
    
    while True:
        schedule.run_pending()
        time.sleep(60)
    #main()  # 테스트용 직접 실행
