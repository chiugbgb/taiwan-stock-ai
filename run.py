import os
import datetime
import requests
import json

def get_twse_data(today_str):
    """下載上市法人買賣超大包檔 (僅消耗 1 次連線)"""
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={today_str}&selectType=ALLBUT0999"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        return res.json().get('data', [])
    except: return []

def get_tpex_data(today_str):
    """下載上櫃法人買賣超大包檔 (僅消耗 1 次連線)"""
    year = str(int(today_str[:4]) - 1911)
    roc_date = f"{year}/{today_str[4:6]}/{today_str[6:]}"
    url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={roc_date}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        return res.json().get('aaData', [])
    except: return []

def main():
    today = datetime.datetime.now().strftime("%Y%m%d")
    print(f"⏰ 開始執行全台股籌碼篩選，今日日期: {today}")
    all_filtered_stocks = []
    
    # 1. 抓取上市股票
    twse_rows = get_twse_data(today)
    for r in twse_rows:
        try:
            net_buy_shares = int(r[4].replace(',', ''))
            if net_buy_shares > 0:
                all_filtered_stocks.append({
                    "代號": r[0].strip(), "名稱": r[1].strip(), "市場": "上市", "外資買超張數": net_buy_shares // 1000
                })
        except: continue
        
    # 2. 抓取上櫃股票
    tpex_rows = get_tpex_data(today)
    for r in tpex_rows:
        try:
            net_buy_shares = int(r[7].replace(',', ''))
            if net_buy_shares > 0:
                all_filtered_stocks.append({
                    "代號": r[0].strip(), "名稱": r[1].strip(), "市場": "上櫃", "外資買超張數": net_buy_shares // 1000
                })
        except: continue

    if not all_filtered_stocks:
        print("🚨 今日無交易數據、非交易日或交易所尚未釋出盤後資料。")
        return

    # 3. 程式記憶體硬篩選：依買超張數由大到小排序，精準切出前 30 名 (0 Token消耗)
    all_filtered_stocks.sort(key=lambda x: x['外資買超張數'], reverse=True)
    top_30 = all_filtered_stocks[:30]

    # 4. 打包數據發送給 Gemini (精準 1 次 Request)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    sheet_webhook = os.environ.get("WECHAT_WEBHOOK_URL")
    
    prompt = (
        f"你是頂尖台股量化籌碼專家。請針對以下今日「全台股上市+上櫃外資買超前30名」的精選清單進行深度交叉比對。"
        f"請從中挑選出3檔最值得注意的核心個股，並用繁體中文給出極簡的核心摘要與理由。\n\n"
        f"全市場前 30 名籌碼排行數據：\n{json.dumps(top_30, ensure_ascii=False)}"
    )
    
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    try:
        gemini_res = requests.post(gemini_url, json={"contents": [{"parts": [{"text": prompt}]}]})
        ai_text = gemini_res.json()['contents'][0]['parts'][0]['text']
    except Exception as e:
        ai_text = f"❌ Gemini AI 分析失敗: {str(e)}"

    # 5. 直射送回 Google 試算表指定工作表
    if sheet_webhook:
        requests.post(sheet_webhook, json={"text": ai_text})
        print("✅ 成功！報告已寫入你的既有選股池指定工作表。")

if __name__ == "__main__":
    main()
