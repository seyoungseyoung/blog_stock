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
import re

# --- Global Variable ---
logger = None # Logger will be initialized in setup_logging

def load_config() -> Dict[str, Any]:
    """설정 파일을 로드합니다."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"설정 파일 로드 실패: {e}")
        raise

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
    """메인 프로그램을 실행합니다."""
    global logger # Ensure we modify the global logger variable
    
    # --- 요일 확인 (주말 스킵) ---
    today_kst = get_kst_time()
    if today_kst.weekday() >= 5: # 5: Saturday, 6: Sunday
        day_name = "토요일" if today_kst.weekday() == 5 else "일요일"
        print(f"\n=== 주말({day_name}) 스킵: {today_kst.strftime('%Y-%m-%d %H:%M:%S %Z%z')} ===")
        # logger가 아직 설정되지 않았을 수 있으므로 print만 사용
        return # 주말에는 작업 실행 안 함
    # --------------------------
    
    # Get start time for logging (이미 위에서 구한 시간 사용)
    start_time_kst = today_kst 
    print(f"\n=== 작업 시작: {start_time_kst.strftime('%Y-%m-%d %H:%M:%S %Z%z')} ===")

    poster = None # Initialize poster to None for error handling
    try:
        # 환경 변수 및 설정 로드
        print("환경 변수 및 설정 로드 중...")
        config = load_config()
        
        # 로깅 설정 (main 실행 시마다 수행)
        print("로깅 설정 중...")
        logger = setup_logging(config) # Assign to the global logger
        logger.info(f"작업 시작: {start_time_kst.strftime('%Y-%m-%d %H:%M:%S')}")
        print("✓ 환경 설정 로드 및 로깅 설정 완료\n")
        
        # 1. 시장 데이터 수집
        print("1. 시장 데이터 수집 시작...")
        collector = MarketDataCollector(config)
        market_data = collector.get_market_data()
        news = collector.get_market_news()
        
        print("\n수집된 데이터 요약:")
        for category, df in market_data.items():
            print(f"- {category}: {len(df)}개 항목")
        print(f"- 뉴스: {len(news)}개 기사\n")
        
        print("- 종목 추천 생성 중...")
        recommendations = collector.get_stock_recommendations(market_data=market_data, num_recommendations=5)
        
        # 2. 시장 데이터 분석 및 콘텐츠 생성
        print("2. 시장 데이터 분석 및 콘텐츠 생성 시작...")
        analyzer = MarketAnalyzer(config)
        title, content, tags, analysis = analyzer.analyze_market_trend(market_data, news, recommendations)
        
        if not title or not content:
            logger.error("시장 분석 또는 콘텐츠 생성 실패: 제목 또는 내용 없음")
            print("✗ 시장 분석 또는 콘텐츠 생성 실패. 이번 실행을 중단합니다.")
            return # Exit current main execution

        tags = tags if tags is not None else ["주식", "투자"]
        analysis = analysis if analysis is not None else {}

        print("\n=== 분석 완료 ===\n")
        print(f"제목: {title}\n")
        print(f"\n포스팅 정보:")
        print(f"- 제목: {title}")
        print(f"- 태그: {', '.join(tags[:5])}... (총 {len(tags)}개)")
        print(f"- 콘텐츠 길이: {len(content)}자\n")
        
        # 4. 블로그 포스팅
        print("4. 블로그 포스팅 시작...")
        poster = NaverBlogPoster(config) # Assign poster here
        
        print("- 웹드라이버 설정 중...")
        if not poster.setup_driver():
            logger.error("웹드라이버 설정 실패")
            print("✗ 웹드라이버 설정 실패. 이번 실행을 중단합니다.")
            # No need to close poster here as setup failed
            return
        
        print("- 네이버 로그인 시도 중...")
        if not poster.manual_login():
            logger.error("네이버 로그인 실패")
            print("✗ 네이버 로그인 실패. 이번 실행을 중단합니다.")
            poster.close() # Close driver if login fails
            return
        
        print("- 블로그 글 작성 및 발행 중...")
        success = poster.create_post(title, content, tags)
        
        if success:
            logger.info(f"포스팅 성공: '{title}'")
            print("\n✓ 블로그 포스팅 완료!")
        else:
            logger.error(f"포스팅 실패: '{title}'")
            print("\n✗ 블로그 포스팅 실패.")
            # Optional: Raise an exception or handle failure differently

    except Exception as e:
        print(f"\n✗ 작업 중 오류 발생: {str(e)}")
        if logger: # Check if logger was initialized
             logger.error(f"작업 실행 중 오류 발생: {e}", exc_info=True)
        # No need to print "프로그램 종료" here, just log the error
        
    finally:
        # 항상 웹 드라이버 종료 시도 (poster 객체가 생성된 경우)
        if poster and hasattr(poster, 'close'):
            try:
                print("- 웹드라이버 종료 시도...")
                poster.close()
            except Exception as close_e:
                 print(f"✗ 웹드라이버 종료 중 오류: {close_e}")
                 if logger:
                     logger.error(f"웹드라이버 종료 중 오류: {close_e}")
        
        end_time_kst = get_kst_time()
        duration = end_time_kst - start_time_kst
        print(f"\n=== 작업 종료: {end_time_kst.strftime('%Y-%m-%d %H:%M:%S %Z%z')} (소요 시간: {duration}) ===")
        if logger:
             logger.info(f"작업 종료. 소요 시간: {duration}")


# 스케줄링 설정 및 실행
if __name__ == "__main__":
    print("프로그램 시작: 스케줄러 설정")
    
    # 매일 한국 시간 21:55에 main 함수 실행 예약
    schedule_time = "21:55"
    print(f"매일 {schedule_time} (시스템 시간 기준)에 작업 실행을 예약합니다.")
    print("(시스템 시간대가 한국 시간(KST)이 아닌 경우, 예상과 다른 시간에 실행될 수 있습니다.)")
    schedule.every().day.at(schedule_time).do(main)
    
    # 최초 실행 시 한번 로거 초기화 시도 (선택 사항)
    try:
        initial_config = load_config()
        logger = setup_logging(initial_config)
        logger.info("스케줄러 시작 및 초기 로거 설정 완료")
    except Exception as init_e:
        print(f"경고: 초기 로거 설정 실패 (스케줄된 작업 시 재시도): {init_e}")

    print("\n스케줄러 실행 중... (Ctrl+C 로 종료)")
    while True:
        schedule.run_pending()
        time.sleep(60) # 1분마다 다음 실행 시간 확인

    # main() # 스케줄링 사용 시 주석 처리 또는 제거
