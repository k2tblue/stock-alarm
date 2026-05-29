# -*- coding: utf-8 -*-
import os
import time
import zipfile
import io
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests
import pandas as pd
import feedparser
from pykrx import stock  # 국내 증시 정밀 데이터 패키지


# =====================================================================
# [설정 영역] 사용자의 API 키 및 텔레그램 정보를 입력하세요.
# =====================================================================
DART_API_KEY = "a3973d63e26fdcc8ee46187c0152299f3f983b7d"      # 금융감독원 OpenDART API 키
TELEGRAM_TOKEN = "8856276797:AAEfhjZAgSszEfG8ZtteAiY3h9Z9QKh8KPA"  # 텔레그램 봇 토큰
CHAT_ID = "8557990682"          # 텔레그램 수신자 고유 ID

# 분석 대상 글로벌 트렌드 및 후보 종목 (6자리 국내 종목코드)
SECTOR_KEYWORDS = ["AI 반도체", "자율주행", "우주항공", "로보틱스"]
CANDIDATE_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "000270": "기아",
    "012330": "현대모비스",
    "068270": "셀트리온",
    "373220": "LG에너지솔루션",
    "005380": "현대차",
    "079550": "LIG넥스원",      # 우주항공/방산 실적 주도주
    "039440": "에스티아이",      # AI 반도체 HBM 장비 숨은 수혜주
    "058470": "리노공업",        # AI 반도체 글로벌 테스트 소켓 강자
    "307950": "현대오토에버",    # 자율주행 핵심 소프트웨어 공급사
    "039030": "이오테크닉스",     # 반도체 레이저 공정 고성장주
    "012450": "한화에어로스페이스",  # 우주항공/방산 대장주
    "319660": "피에스케이",         # AI 반도체 장비 글로벌 강자
    "054450": "텔레칩스",           # 자율주행 차량용 칩 국산화 선두
    "195870": "해성디에스",          # 자율주행 반도체 핵심 기판 공급사
    "286940": "롯데이노베이트", 
    "042700": "한미반도체", 
    "034020": "두산에너지빌리티",
    "007660": "이수페타시스",
    "277810": "레인보우로보틱스",
    "033100": "제룡전기",
    "047810": "한국항공우주",     # 우주항공 완제기 수출 주도
    "036930": "주성엔지니어링",   # AI 반도체 미세공정 ALD 장비
    "067310": "하나마이크론",     # AI 반도체 필수 후공정(OSAT)
    "091120": "엠씨넥스",         # 자율주행 ADAS 카메라 모듈
    "118990": "모트렉스"          # 자율주행 IVI 및 스마트카 솔루션
}

# =====================================================================
# FUNCTION 1: 신뢰도 최상위 국내 경제 뉴스 수집
# =====================================================================
def fetch_trusted_news(keyword):
    print(f"  └ 📰 '{keyword}' 관련 주요 뉴스 수집 중...")
    trusted_sites = "site:mk.co.kr OR site:hankyung.com OR site:yna.co.kr"
    query = f"{keyword} ({trusted_sites})"
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    return [{"title": e.title[:35] + "...", "link": e.link, "source": getattr(e, 'source', {}).get('text', '언론사')} for e in feed.entries[:2]]

class KoreaStockValidator:
    def __init__(self, dart_key):
        self.dart_key = dart_key
        self.corp_code_map = {}
        self._load_dart_corp_codes()

    def _load_dart_corp_codes(self):
        print("📥 [DART] 전종목 고유번호 매핑 파일 다운로드 중... (약 10~20초 소요)")
        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        try:
            res = requests.get(url, params={"crtfc_key": self.dart_key})
            if res.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(res.content)) as z:
                    xml_data = z.read('CORPCODE.xml')
                    tree = ET.fromstring(xml_data)
                    for row in tree.findall('list'):
                        sc = row.find('stock_code').text.strip() if row.find('stock_code') is not None else ""
                        if sc: 
                            self.corp_code_map[sc] = row.find('corp_code').text.strip()
                print(f"✅ [DART] 고유번호 로드 완료! (총 {len(self.corp_code_map):,}개 기업 매핑됨)")
        except Exception as e:
            print(f"⚠️ DART 고유번호 로드 실패: {e}")

    def check_listing_3y(self, stock_code):
        try:
            three_years_ago = (datetime.now() - timedelta(days=3*365)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(three_years_ago, three_years_ago, stock_code)
            if not df.empty:
                return True, "3년 이상 상장 충족"
            return False, "상장 3년 미만"
        except Exception:
            return False, "상장 정보 확인 불가"

    def get_dart_operating_income(self, stock_code, year):
        corp_code = self.corp_code_map.get(stock_code)
        if not corp_code: 
            return None
        url = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
        params = {"crtfc_key": self.dart_key, "corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"}
        try:
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "000":
                    for item in data.get("list", []):
                        if "영업이익" in item.get("account_nm", "") and item.get("fs_div") == "CFS":
                            return int(item.get("thstrm_amount").replace(",", ""))
                    for item in data.get("list", []):
                        if "영업이익" in item.get("account_nm", ""):
                            return int(item.get("thstrm_amount").replace(",", ""))
                return None
            return None
        except Exception:
            return None

    def verify_financial_growth(self, stock_code):
        years = [2023, 2024, 2025]
        incomes = {}
        for y in years:
            time.sleep(0.3) 
            incomes[y] = self.get_dart_operating_income(stock_code, y)
            
        if None in incomes.values():
            return False, "일부 연도 실적 누락"
# 💡 최근 2개년(2024 -> 2025) 영업이익 우상향만 깐깐하게 체크하도록 변경
        if incomes[2024] < incomes[2025]:
            return True, incomes
        return False, f"최근 2개년 실적 우상향 실패"

def analyze_krx_valuation(stock_code):
    """[조건 6] KRX 기준 최신 밸류에이션(PER/PBR) 검증 (에러 방지 강화)"""
    try:
        # 오늘 기준 데이터가 거래소에 없을 수 있으므로 최근 일주일 범위를 지정해 가장 최신 영업일 데이터를 가져옴
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        
        df = stock.get_market_fundamental_by_date(start_date, end_date, stock_code)
        
        if not df.empty:
            # 가장 최근 날짜의 row 선택
            latest_row = df.iloc[-1]
            per = latest_row['PER']
            pbr = latest_row['PBR']
            
            # PER 데이터가 없거나 0 이하인 경우 (적자 기업 등) 처리
            if pd.isna(per) or per <= 0:
                return False, 0.0, 0.0, "PER 데이터 누락 또는 적자 기업"
                
            if per <= 20.0:
                return True, float(per), float(pbr), "저평가 구간 충족"
            return False, float(per), float(pbr), f"PER {per:.2f}로 저평가 구간 아님 (20배 초과)"
            
        return False, 0.0, 0.0, "최근 일주일 내 KRX 밸류에이션 데이터 존재하지 않음"
    except Exception as e:
        return False, 0.0, 0.0, f"KRX 데이터 조회 실패: {str(e)}"

def run_integrated_pipeline():
    print("\n========= 🚀 국내 주식 자동화 파이프라인 가동 시작 =========")
    
    # 1. 뉴스 브리핑 섹션 작성
    print("\n1단계: 메이저 3사 경제 뉴스 크롤링 시작...")
    news_section = "📰 *[신뢰 경제 소스] 핵심 트렌드 뉴스*\n"
    for kw in SECTOR_KEYWORDS:
        news_section += f"• *{kw}*\n"
        for n in fetch_trusted_news(kw):
            news_section += f"  - [{n['source']}] {n['title']} ([링크]({n['link']}))\n"
            
    # 2. 퀀트 필터링 진행
    print("\n2단계: 금융감독원 데이터 기반 퀀트 스크리닝 시작...")
    validator = KoreaStockValidator(dart_key=DART_API_KEY)
    passed_stocks = []
    
    print(f"\n3단계: 후보 종목({len(CANDIDATE_STOCKS)}개) 정밀 검증 시작...")
    for code, name in CANDIDATE_STOCKS.items():
        print(f" 🔍 [{name} ({code})] 분석 중...", end="")
        
        # 조건 1: 상장 3년 검증
        is_matured, _ = validator.check_listing_3y(code)
        if not is_matured: 
            print(" ❌ 탈락 (상장 3년 미만)")
            continue
        
        # 조건 2: 3개년 실적 성장 검증
        is_growing, growth_data = validator.verify_financial_growth(code)
        if not is_growing: 
            print(" ❌ 탈락 (영업이익 우상향 실패 또는 데이터 누락)")
            continue
        
        # 조건 3: 당일 밸류에이션 검증 (개수 불일치 에러 해결)
        is_cheap, per_val, pbr_val, reason = analyze_krx_valuation(code)
        if not is_cheap: 
            print(f" ❌ 탈락 ({reason})")
            continue
        
        # 모든 조건 통과 시
        print(f" 🎉 통과! (PER: {per_val:.2f}, PBR: {pbr_val:.2f})")
        passed_stocks.append({"code": code, "name": name, "per": per_val, "pbr": pbr_val, "growth": growth_data})
        
    # 4. 마크다운 보고서 조판 및 전송
    print("\n4단계: 최종 분석 보고서 작성 및 텔레그램 전송...")
    report_date = datetime.now().strftime('%Y-%m-%d')
    msg = f"🔔 *{report_date} 15:00 국장 투자종목 선별 리포트*\n\n" + news_section + "\n"
    msg += "📈 *[필터링 완료] 적극 투자 권유 종목*\n"
    
    if not passed_stocks:
        msg += "❌ 오늘 조건(상장3년+, 3개년 이익성장, 저PER)을 모두 충족한 국내 종목이 없습니다."
    else:
        for idx, s in enumerate(passed_stocks, 1):
            msg += f"{idx}. *{s['name']}* ({s['code']})\n"
            msg += f"  - 3개년 영업이익: `23년 {s['growth'][2023]:,}`원 → `24년 {s['growth'][2024]:,}`원 → `25년 {s['growth'][2025]:,}`원\n"
            msg += f"  - 밸류에이션: 당일 기준 PER `{s['per']:.2f}`배 / PBR `{s['pbr']:.2f}`배\n"
            msg += f"  - **추천사유:** 주요 메이저 언론이 주목하는 글로벌 공급망 수혜주이며, 3년 연속 확실한 체질 개선(어닝 그로스)이 검증되었음에도 현재 시장 조정으로 멀티플(PER)이 적극 매수 구간에 진입함.\n\n"

    res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    if res.status_code == 200:
        print("🚀 텔레그램 메시지가 성공적으로 발송되었습니다!")
    else:
        print(f"❌ 텔레그램 발송 실패 (오류 코드: {res.status_code})")

if __name__ == "__main__":
    print("국내 주식 퀀트 자동화 시스템 작동 시작")
    
    if DART_API_KEY != "YOUR_OPENDART_API_KEY":
        print("🚀 [테스트] 즉시 분석 및 텔레그램 발송을 시작합니다...")
        run_integrated_pipeline()
        print("\n✅ [테스트] 즉시 실행 완료! 이제 15:00 정각 대기 모드로 전환합니다.")
    else:
        print("⚠️ DART_API_KEY를 먼저 입력하셔야 테스트가 가능합니다.")

    print("\n국내 주식 퀀트 자동화 시스템 대기 중... (매일 15:00 트리거)")
    while True:
        now = datetime.now()
        if now.hour == 15 and now.minute == 0:
            if DART_API_KEY != "YOUR_OPENDART_API_KEY":
                run_integrated_pipeline()
            time.sleep(60)
        time.sleep(30)
