import baostock as bs
import pandas as pd
import datetime
import os

# Configuration
OUTPUT_SQL_FILE = "update.sql"

def get_today_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def get_constituents():
    print("Fetching constituents from Baostock...")
    bs.login()
    
    # HS300
    rs_hs300 = bs.query_hs300_stocks()
    hs300_stocks = []
    while (rs_hs300.error_code == '0') & rs_hs300.next():
        hs300_stocks.append(rs_hs300.get_row_data())
    df_hs300 = pd.DataFrame(hs300_stocks, columns=rs_hs300.fields)
    
    # ZZ500
    rs_zz500 = bs.query_zz500_stocks()
    zz500_stocks = []
    while (rs_zz500.error_code == '0') & rs_zz500.next():
        zz500_stocks.append(rs_zz500.get_row_data())
    df_zz500 = pd.DataFrame(zz500_stocks, columns=rs_zz500.fields)
    
    # Combine unique codes
    all_codes = set(df_hs300['code'].tolist() + df_zz500['code'].tolist())
    print(f"Total stocks to update: {len(all_codes)}")
    
    return list(all_codes)

def fetch_daily_data(codes, date):
    print(f"Fetching data for {date}...")
    # Note: bs.login() is already called in get_constituents, but safe to call again or check status
    # Baostock session might timeout, so re-login is safer if long time passed, but here it's fast.
    
    all_data = []
    total = len(codes)
    
    for i, code in enumerate(codes):
        if i % 100 == 0:
            print(f"Progress: {i}/{total}")
            
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount,adjustflag",
            start_date=date,
            end_date=date,
            frequency="d",
            adjustflag="3" 
        )
        
        while (rs.error_code == '0') & rs.next():
            all_data.append(rs.get_row_data())
            
    if not all_data:
        print("No data found for today.")
        return pd.DataFrame()
        
    return pd.DataFrame(all_data, columns=["date", "code", "open", "high", "low", "close", "volume", "amount", "adjustflag"])

def generate_sql(df):
    print(f"Generating SQL for {len(df)} rows...")
    with open(OUTPUT_SQL_FILE, "w") as f:
        for _, row in df.iterrows():
            # Handle potential empty values or types
            try:
                open_val = float(row['open'])
                high_val = float(row['high'])
                low_val = float(row['low'])
                close_val = float(row['close'])
                volume_val = float(row['volume'])
                amount_val = float(row['amount'])
                adjustflag_val = int(row['adjustflag'])
            except ValueError:
                continue # Skip invalid rows
                
            sql = f"INSERT OR REPLACE INTO stock_kline (date, code, open, high, low, close, volume, amount, adjustflag) VALUES ('{row['date']}', '{row['code']}', {open_val}, {high_val}, {low_val}, {close_val}, {volume_val}, {amount_val}, {adjustflag_val});\n"
            f.write(sql)
            
    print(f"SQL saved to {OUTPUT_SQL_FILE}")

if __name__ == "__main__":
    # For testing, you can set a specific date like "2024-11-26" if today is weekend
    # target_date = "2024-11-26" 
    target_date = get_today_date()
    
    codes = get_constituents()
    df = fetch_daily_data(codes, target_date)
    
    if not df.empty:
        generate_sql(df)
    else:
        print("No data to update.")
        # Create empty file to avoid errors in CI if it expects a file
        open(OUTPUT_SQL_FILE, 'w').close()
    
    bs.logout()
