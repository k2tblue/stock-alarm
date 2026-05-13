import FinanceDataReader as fdr
import telegram
import asyncio
import os
TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']


# 감시할 종목 리스트 (삼성전자, 하이닉스, 롯데이노베이트 등)
STOCKS = {'삼성전자':'005930', 'SK하이닉스':'000660', '롯데이노베이트':'022220'}

async def run_bot():
    bot = telegram.Bot(token=TOKEN)
    report = "🤖 [오늘의 종가 분석 리포트]\n\n"
    
    for name, code in STOCKS.items():
        # 데이터 수집 (최근 50일)
        df = fdr.DataReader(code).tail(50)
        
        # 지표 계산 (5일선, 20일선, 이격도)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Disparity'] = (df['Close'] / df['MA20']) * 100
        
        curr = df.iloc[-1]  # 오늘 데이터
        prev = df.iloc[-2]  # 어제 데이터
        
        # --- 우리가 만든 로직 판정 ---
        signal = ""
        if curr['Disparity'] > 125:
            signal = "⚠️ 과열! 일부 익절 검토"
        elif curr['Disparity'] < 90:
            signal = "🧡 저가보충 기회! 매수 검토"
        elif curr['MA5'] > curr['MA20'] and prev['MA5'] <= prev['MA20']:
            signal = "🚀 골든크로스! 상승 추세 진입"
            
        if signal:
            report += f"📍 {name} ({curr['Close']:,.0f}원)\n👉 {signal}\n\n"

    # 메시지 전송
    if report != "🤖 [오늘의 종가 분석 리포트]\n\n":
        await bot.send_message(chat_id=CHAT_ID, text=report)
    else:
        await bot.send_message(chat_id=CHAT_ID, text="📢 오늘은 특이 신호가 있는 종목이 없습니다.")

# 실행 버튼
await run_bot()
