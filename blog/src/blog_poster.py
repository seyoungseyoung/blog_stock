from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import os
import time
import pickle
from pathlib import Path
from typing import List
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from datetime import datetime
from selenium.webdriver.common.action_chains import ActionChains
import re

class NaverBlogPoster:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.username = os.getenv('NAVER_USERNAME')
        self.password = os.getenv('NAVER_PASSWORD')
        self.driver = None
        self.cookies_file = Path(__file__).parent.parent / 'config' / 'naver_cookies.pkl'
        
        if not self.username or not self.password:
            self.logger.error("Naver credentials not found in environment variables")
            raise ValueError("네이버 로그인 정보가 환경변수에 설정되지 않았습니다.")

    def setup_driver(self):
        """Selenium WebDriver를 초기화합니다."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User-Agent 설정
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36')
            
            # ChromeDriver 경로 직접 지정
            chromedriver_path = Path(__file__).parent / 'chromedriver' / 'chromedriver-win64' / 'chromedriver.exe'
            service = Service(executable_path=str(chromedriver_path))
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            
            # JavaScript 코드 실행하여 웹드라이버 감지 방지
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to setup WebDriver: {e}", exc_info=True)
            print(f"✗ 웹드라이버 설정 실패: {str(e)}")
            return False

    def login(self):
        """네이버에 로그인합니다."""
        try:
            # 네이버 로그인 페이지로 이동
            self.driver.get('https://nid.naver.com/nidlogin.login')
            time.sleep(2)
            
            # JavaScript를 통한 로그인 정보 입력
            self.driver.execute_script(
                f"document.getElementsByName('id')[0].value='{self.username}'")
            time.sleep(0.5)
            
            self.driver.execute_script(
                f"document.getElementsByName('pw')[0].value='{self.password}'")
            time.sleep(0.5)
            
            # 로그인 버튼 클릭
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'btn_login'))
            )
            login_button.click()
            
            # 로그인 성공 확인
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: 'nid.naver.com/nidlogin.login' not in d.current_url
                )
                print("✓ 네이버 로그인 성공")
                return True
            except TimeoutException:
                print("✗ 로그인 실패: 아이디 또는 비밀번호를 확인해주세요.")
                return False
                
        except Exception as e:
            self.logger.error(f"Login failed: {e}", exc_info=True)
            print(f"✗ 로그인 실패: {str(e)}")
            return False

    def check_login_status(self):
        """현재 로그인 상태를 확인합니다."""
        try:
            self.driver.get('https://blog.naver.com/gongnyangi')
            time.sleep(2)
            
            # 로그인 버튼이 있는지 확인
            login_buttons = self.driver.find_elements(By.CLASS_NAME, 'log_btn')
            return len(login_buttons) == 0
            
        except Exception:
            return False

    def create_post(self, title: str, content: str, tags: List[str]) -> bool:
        """네이버 블로그에 글을 포스팅합니다. (참고 코드 기반 수정)"""
        if not self.driver:
            self.logger.error("WebDriver가 초기화되지 않았습니다.")
            return False

        try:
            # 글쓰기 페이지로 이동
            print("- 글쓰기 페이지로 이동 중...")
            self.driver.get("https://blog.naver.com/gongnyangi/postwrite")
            print("- 페이지 로딩 대기 (7초)...")
            time.sleep(7)
            print(f"현재 URL: {self.driver.current_url}")
            time.sleep(3) # 팝업 로드 대기

            # 이전 글 작성 확인 팝업 처리 (참고 코드 방식)
            try:
                print("- 이전 글 팝업 확인 중...")
                # 팝업 버튼이 나타날 때까지 조금 더 대기
                WebDriverWait(self.driver, 5).until(
                     EC.presence_of_element_located((By.CLASS_NAME, 'se-popup-button-text'))
                )
                cancel_buttons = self.driver.find_elements(By.CLASS_NAME, 'se-popup-button-text')
                if cancel_buttons:
                    for button in cancel_buttons:
                        if button.text == '취소':
                            button.click()
                            time.sleep(3) # 팝업 닫히는 시간
                            print("- 이전 글 '취소' 처리 완료")
                            break
            except TimeoutException:
                 print("- 이전 글 팝업 없음 - 계속 진행")
            except Exception as e:
                print(f"- 이전 글 팝업 처리 중 오류 (무시하고 계속): {e}")

            # 도움말 닫기 버튼 처리 (참고 코드 방식)
            time.sleep(2)
            try:
                print("- 도움말 팝업 확인 중...")
                help_buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                for button in help_buttons:
                     try:
                         if button.get_attribute('class') and '닫기' in button.get_attribute('class'):
                             if button.is_displayed() and button.is_enabled():
                                 button.click()
                                 time.sleep(2)
                                 print("- 도움말 닫기 완료")
                                 break
                     except: # StaleElementReference 등 예외 처리
                         continue
            except Exception as e:
                print(f"- 도움말 팝업 처리 중 오류 (무시하고 계속): {e}")

            # 제목 입력 (참고 코드 방식)
            try:
                print("- 제목 영역 찾는 중...")
                title_area = None
                try:
                    # 시도 1: Placeholder
                    title_placeholder_selector = 'span.se-placeholder.__se_placeholder' # 좀 더 일반적일 수 있는 선택자
                    title_area = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, title_placeholder_selector))
                    )
                    print("- 제목 영역 찾음 (Placeholder)")
                except TimeoutException:
                    print("- 제목 Placeholder 없음, 다른 선택자 시도")
                    # 시도 2: 특정 클래스 (참고 코드와 유사)
                    title_class_selector = 'span.se-ff-nanumgothic.se-fs32.__se-node'
                    try:
                         title_area = WebDriverWait(self.driver, 5).until(
                             EC.element_to_be_clickable((By.CSS_SELECTOR, title_class_selector))
                         )
                         print("- 제목 영역 찾음 (클래스)")
                    except TimeoutException:
                         print("✗ 제목 영역을 찾을 수 없습니다.")
                         return False

                title_area.click()
                time.sleep(1)
                print("- 제목 입력 중...")
                actions = ActionChains(self.driver)
                actions.send_keys(title).perform()
                print("- 제목 입력 완료")
                time.sleep(1)
                print("- Enter 키 입력 (본문 이동)")
                actions.send_keys(Keys.ENTER).perform()
                time.sleep(3) # 본문 영역 활성화 대기
            except Exception as e:
                print(f"✗ 제목 입력 실패: {e}")
                return False

            # 본문 입력 (문자 단위 send_keys 및 초소형 대기)
            try:
                print("- 본문 문자 단위 입력 시작 (매우 느릴 수 있음)...")
                # --- iframe 전환 필요 시 여기에 추가 --- 
                # try: self.driver.switch_to.frame(...) except: ...

                # 본문 영역 포커스 확보 (기존 로직 유지)
                editor_body_selector = 'div.se-component-content p.se-text-paragraph'
                try:
                    editor_element = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, editor_body_selector))
                    )
                    self.driver.execute_script("arguments[0].click();", editor_element)
                    print("- 본문 영역 포커스 확보 완료")
                    time.sleep(1)
                except Exception as focus_e:
                    print(f"- 본문 영역 포커스 실패 (무시하고 입력 시도): {focus_e}")
                    # 포커스 실패해도 입력은 시도
                
                actions = ActionChains(self.driver) # ActionChains 객체 생성
                cleaned_content = content.strip()
                total_chars = len(cleaned_content)
                print(f"- 총 {total_chars} 문자 입력 예정")
                
                for i, char in enumerate(cleaned_content):
                    if char == '\n':
                        actions.send_keys(Keys.ENTER)
                    else:
                        actions.send_keys(char)
                    
                    actions.perform() # 각 문자/Enter 전송
                    time.sleep(0.05) # 각 문자 입력 후 0.05초 대기 (속도 조절 가능)
                    
                    # 진행 상황 로그 (너무 자주 찍히지 않도록 조절)
                    if (i + 1) % 100 == 0 or (i + 1) == total_chars:
                        print(f"  ... {i+1}/{total_chars} 문자 입력 완료")
                        
                print("- 모든 본문 문자 입력 완료.")
                time.sleep(3) # 모든 본문 입력 후 안정화 시간

                # --- iframe 전환했다면 복귀 --- 
                # try: self.driver.switch_to.default_content() except: ...

            except Exception as e:
                print(f"✗ 본문 문자 단위 입력 중 오류 발생: {e}")
                # iframe 전환 시 복귀 필요
                # try: self.driver.switch_to.default_content() except: ...
                return False

            # 첫 번째 발행 버튼 클릭 (JavaScript 사용)
            time.sleep(3)
            try:
                print("- 첫 번째 발행 버튼 클릭 시도 (JavaScript)...")
                publish_script = """
                    var publishBtn = document.querySelector('button.publish_btn__m9KHH');
                    if (publishBtn) {
                        publishBtn.click();
                        return true;
                    } else {
                        console.error('Publish button not found!');
                        return false;
                    }
                """
                if self.driver.execute_script(publish_script):
                    print("- 첫 번째 발행 버튼 클릭 완료. 발행 설정 창 대기 (5초)...")
                    time.sleep(5)
                else:
                    print("✗ 첫 번째 발행 버튼을 JavaScript로 찾거나 클릭할 수 없습니다.")
                    # 실패 시 Selenium 클릭 시도 (Fallback)
                    try:
                         print("- Selenium 클릭으로 재시도...")
                         publish_button_selector = 'button.publish_btn__m9KHH'
                         publish_button = WebDriverWait(self.driver, 5).until(
                             EC.element_to_be_clickable((By.CSS_SELECTOR, publish_button_selector))
                         )
                         publish_button.click()
                         print("- 첫 번째 발행 버튼 클릭 완료 (Selenium). 발행 설정 창 대기 (5초)...")
                         time.sleep(5)
                    except Exception as e_fallback:
                         print(f"✗ 첫 번째 발행 버튼 클릭 최종 실패: {e_fallback}")
                         return False

            except Exception as e:
                print(f"✗ 첫 번째 발행 버튼 처리 중 오류: {e}")
                return False

            # --- 발행 설정 (카테고리, 태그 등, 기존 안정화 코드 유지) ---
            try:
                print("- 카테고리 선택 과정 시작...")
                # 카테고리 선택 시도 (이전 코드와 유사, 에러 시 무시)
                try:
                    category_button_selector = 'button.selectbox_button__jb1Dt'
                    category_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, category_button_selector))
                    )
                    self.driver.execute_script("arguments[0].click();", category_button)
                    time.sleep(2)
                    category_label_selector = 'label[for="11_종목 추천 및 분석"]' # 카테고리명 확인!
                    category_label = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, category_label_selector))
                    )
                    self.driver.execute_script("arguments[0].click();", category_label)
                    print("- 카테고리 선택 완료")
                    time.sleep(2)
                except Exception as cat_e:
                    print(f"- 카테고리 선택 실패 (무시): {cat_e}")
                
                # 태그 입력 시도 (이전 코드와 유사, 에러 시 무시)
                if tags:
                    try:
                        print("- 태그 입력 시작...")
                        tag_input_selector = 'input#tag-input.tag_input__rvUB5'
                        tag_input = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, tag_input_selector))
                        )
                        for tag in tags:
                            tag_input.clear()
                            tag_input.send_keys(tag)
                            time.sleep(0.7)
                            tag_input.send_keys(Keys.ENTER)
                            time.sleep(1.5)
                        print("- 모든 태그 입력 완료")
                        time.sleep(2)
                    except Exception as tag_e:
                        print(f"- 태그 입력 실패 (무시): {tag_e}")
                else:
                    print("- 입력할 태그 없음")

            except Exception as e_publish_settings:
                 print(f"- 발행 설정(카테고리/태그) 중 오류 발생 (무시하고 최종 발행 시도): {e_publish_settings}")
            
            # 최종 발행 버튼 클릭 (JavaScript 사용)
            try:
                print("- 최종 발행 버튼 클릭 시도 (JavaScript)...")
                final_publish_script = """
                    var finalBtn = document.querySelector('button.confirm_btn__WEaBq[data-testid="seOnePublishBtn"]');
                    if (finalBtn) {
                        finalBtn.click();
                        return true;
                    } else {
                         console.error('Final publish button not found!');
                         return false;
                    }
                """
                if self.driver.execute_script(final_publish_script):
                    print("- 최종 발행 버튼 클릭 완료. 포스팅 완료 대기 (7초)...")
                    time.sleep(7)
                else:
                    print("✗ 최종 발행 버튼을 JavaScript로 찾거나 클릭할 수 없습니다.")
                    # 실패 시 Selenium 클릭 시도 (Fallback)
                    try:
                         print("- Selenium 클릭으로 재시도...")
                         final_publish_button_selector = 'button.confirm_btn__WEaBq[data-testid="seOnePublishBtn"]'
                         final_publish_button = WebDriverWait(self.driver, 5).until(
                              EC.element_to_be_clickable((By.CSS_SELECTOR, final_publish_button_selector))
                         )
                         final_publish_button.click()
                         print("- 최종 발행 버튼 클릭 완료 (Selenium). 포스팅 완료 대기 (7초)...")
                         time.sleep(7)
                    except Exception as e_final_fallback:
                         print(f"✗ 최종 발행 버튼 클릭 최종 실패: {e_final_fallback}")
                         return False

                # 발행 후 URL 확인
                if "postwrite" not in self.driver.current_url:
                     print("\n✓ 블로그 포스팅 성공!")
                     return True
                else:
                     # 발행은 되었으나 페이지 전환 안된 경우도 있을 수 있음 (네트워크 등) - 로그 추가
                     print(f"✗ 포스팅 실패 또는 확인 불가: 현재 URL이 여전히 postwrite 페이지입니다 ({self.driver.current_url})")
                     return False

            except Exception as e:
                print(f"✗ 최종 발행 버튼 처리 중 오류: {e}")
                return False

        except (TimeoutException, NoSuchElementException, WebDriverException) as e:
            self.logger.error(f"포스팅 중 오류 발생: {e}", exc_info=True)
            print(f"✗ 포스팅 실패: {e}")
            # self.driver.save_screenshot(f"error_screenshot_{datetime.now():%Y%m%d_%H%M%S}.png")
            return False
        except Exception as e:
            self.logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
            print(f"✗ 예상치 못한 포스팅 오류: {e}")
            return False
        finally:
            # iframe 전환 시 복귀 로직 (필요시 활성화)
            try:
                self.driver.switch_to.default_content()
            except Exception: pass
            
    def manual_login(self) -> bool:
        """자동으로 로그인을 진행합니다."""
        try:
            # 로그인 시도
            return self.login()
        except Exception as e:
            self.logger.error(f"로그인 실패: {e}")
            return False

    def close(self):
        """WebDriver를 종료합니다."""
        if self.driver:
            try:
                self.driver.quit()
                print("- 웹드라이버 종료 완료")
            except WebDriverException as e:
                self.logger.warning(f"WebDriver close error: {e}")
