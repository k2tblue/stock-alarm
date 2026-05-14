import FinanceDataReader as fdr
import telegram
import asyncio
import os
import sys

# 깃허브 Secrets 설정값 읽기
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
STOCKS = {'삼성전자':'005930', 'SK하이닉스':'000660', '롯데이노베이트':'022220'}

async def main():
    if not TOKEN or not CHAT_ID:
        print("에러: TOKEN 또는 CHAT_ID가 설정되지 않았습니다.")
        sys.exit(1)

    bot = telegram.Bot(token=TOKEN)
    report = "🤖 [오늘의 종가 분석 리포트]\n\n"
    
    for name, code in STOCKS.items():
        try:
            # 데이터 수집 및 지표 계산
            df = fdr.DataReader(code).tail(50)
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['Disparity'] = (df['Close'] / df['MA20']) * 100
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            signal = ""
            if curr['Disparity'] > 125:
                signal = "⚠️ 과열! 일부 익절 검토"
            elif curr['Disparity'] < 90:
                signal = "🧡 저가보충 기회! 매수 검토"
            elif curr['MA5'] > curr['MA20'] and prev['MA5'] <= prev['MA20']:
                signal = "🚀 골든크로스! 상승 추세 진입"
                
            if signal:
                report += f"📍 {name} ({curr['Close']:,.0f}원)\n👉 {signal}\n\n"
        except Exception as e:
            print(f"{name} 분석 중 오류 발생: {e}")

    if report == "🤖 [오늘의 종가 분석 리포트]\n\n":
        report += "📢 현재 모든 종목이 안정권이며 특이 신호가 없습니다."

    # 메시지 전송 (최신 라이브러리 표준 방식)
    try:
        async with bot:
            await bot.send_message(chat_id=CHAT_ID, text=report)
        print("텔레그램 메시지 전송 성공!")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
