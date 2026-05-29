import FinanceDataReader as fdr
import telegram
import asyncio
import os
import sys

# 깃허브 Secrets에서 설정값 읽기
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 감시할 종목 리스트 (이름: 종목코드)
STOCKS = {
    '삼성전자': '005930', 
    'SK하이닉스': '000660', 
    '롯데이노베이트': '286940',
    '한미반도체': '042700',
    '두산에너지빌리티': '034020',
    '이수페타시스': '007660',
    '레인보우로보틱스': '277810',
    '제룡전기': '033100',
    '기아': '000270',
    '현대모비스': '012330',
    '셀트리온': '068270',
    'LG에너지솔루션': '373220',
    '현대차': '005380',
    'LIG넥스원': '079550',
    '에스티아이': '039440',
    '리노공업': '058470',      # 우주항공/방산 실적 주도주
    '현대오토에버': '307950',      # AI 반도체 HBM 장비 숨은 수혜주
    '이오테크닉스': '039030',        # AI 반도체 글로벌 테스트 소켓 강자
    '한화에어로스페이스': '012450',    # 자율주행 핵심 소프트웨어 공급사
    '피에스케이': '319660',     # 반도체 레이저 공정 고성장주
    '텔레칩스': '054450',  # 우주항공/방산 대장주
    '해성디에스': '195870',         # AI 반도체 장비 글로벌 강자
    '한국항공우주': '047810',           # 자율주행 차량용 칩 국산화 선두
    '주성엔지니어링': '036930',          # 자율주행 반도체 핵심 기판 공급사
    '하나마이크론': '067310', 
    '엠씨넥스': '091120', 
    '모트렉스': '118990'
}

async def run_bot():
    # 1. 설정값 확인
    if not TOKEN or not CHAT_ID:
        print("에러: TELEGRAM_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        sys.exit(1)

    bot = telegram.Bot(token=TOKEN)
    report = "🤖 [오늘의 종가 분석 리포트]\n\n"
    has_signal = False
    
    for name, code in STOCKS.items():
        try:
            # 2. 데이터 수집 (최근 50일)
            df = fdr.DataReader(code).tail(50)
            
            # 3. 지표 계산 (5일선, 20일선, 이격도)
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['Disparity'] = (df['Close'] / df['MA20']) * 100
            
            curr = df.iloc[-1]  # 오늘 데이터
            prev = df.iloc[-2]  # 어제 데이터
            
            # 4. 로직 판정
            signal = ""
            if curr['Disparity'] > 125:
                signal = "⚠️ 과열! 일부 익절 검토"
            elif curr['Disparity'] < 90:
                signal = "🧡 저가보충 기회! 매수 검토"
            elif curr['MA5'] > curr['MA20'] and prev['MA5'] <= prev['MA20']:
                signal = "🚀 골든크로스! 상승 추세 진입"
                
            if signal:
                report += f"📍 {name} ({curr['Close']:,.0f}원)\n👉 {signal}\n\n"
                has_signal = True
                
        except Exception as e:
            print(f"{name} 분석 중 오류: {e}")

    if not has_signal:
        report += "📢 오늘은 모든 종목이 안정권이며 특이 신호가 없습니다."

    # 5. 텔레그램 메시지 전송 (최신 라이브러리 방식)
    try:
        async with bot:
            await bot.send_message(chat_id=CHAT_ID, text=report)
        print("전송 완료!")
    except Exception as e:
        print(f"텔레그램 전송 에러: {e}")
        sys.exit(1)

# 에러가 났던 'await run_bot()' 대신 아래 표준 방식을 사용합니다.
if __name__ == "__main__":
    asyncio.run(run_bot())
