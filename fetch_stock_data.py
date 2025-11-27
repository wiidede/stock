import baostock as bs
import pandas as pd
import sqlite3
import os

# Configuration
DB_PATH = "stock_data.db"
TUSHARE_CSV_PATH = "data/tushare_stock_basic_20251126200151.csv"
START_DATE = "2024-07-24"
END_DATE = "2025-11-26"

def init_db():
    print(f"Initializing database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # stock_basic table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_basic (
        code TEXT PRIMARY KEY,
        symbol TEXT,
        name TEXT,
        area TEXT,
        industry TEXT,
        list_date TEXT,
        is_hs300 INTEGER,
        is_zz500 INTEGER
    )
    """)
    
    # stock_kline table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_kline (
        date TEXT,
        code TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        amount REAL,
        adjustflag INTEGER,
        PRIMARY KEY (date, code)
    )
    """)
    
    conn.commit()
    conn.close()

def get_baostock_constituents():
    print("Fetching constituents from Baostock...")
    bs.login()
    
    # HS300
    print("Fetching HS300 stocks...")
    rs_hs300 = bs.query_hs300_stocks()
    hs300_stocks = []
    while (rs_hs300.error_code == '0') & rs_hs300.next():
        hs300_stocks.append(rs_hs300.get_row_data())
    df_hs300 = pd.DataFrame(hs300_stocks, columns=rs_hs300.fields)
    print(f"HS300 count: {len(df_hs300)}")
    
    # ZZ500
    print("Fetching ZZ500 stocks...")
    rs_zz500 = bs.query_zz500_stocks()
    zz500_stocks = []
    while (rs_zz500.error_code == '0') & rs_zz500.next():
        zz500_stocks.append(rs_zz500.get_row_data())
    df_zz500 = pd.DataFrame(zz500_stocks, columns=rs_zz500.fields)
    print(f"ZZ500 count: {len(df_zz500)}")
    
    bs.logout()
    
    return df_hs300, df_zz500

def process_stocks(df_hs300, df_zz500):
    print("Processing stock lists...")
    # Read Tushare data
    if not os.path.exists(TUSHARE_CSV_PATH):
        print(f"Error: {TUSHARE_CSV_PATH} not found.")
        return None

    # Ensure symbol is read as string to match Baostock parsed symbol
    df_tushare = pd.read_csv(TUSHARE_CSV_PATH, dtype={'symbol': str})
    
    stock_map = {}
    
    # Helper to add stocks
    def add_stocks(df, is_hs300, is_zz500):
        for _, row in df.iterrows():
            bs_code = row['code'] # e.g., sh.600000
            bs_name = row['code_name']
            
            # Extract symbol: sh.600000 -> 600000
            if '.' in bs_code:
                symbol = bs_code.split('.')[1]
            else:
                symbol = bs_code # Should not happen with Baostock format but safe fallback
            
            if bs_code not in stock_map:
                stock_map[bs_code] = {
                    'code': bs_code,
                    'symbol': symbol,
                    'name': bs_name,
                    'is_hs300': 0,
                    'is_zz500': 0,
                    'area': '',
                    'industry': '',
                    'list_date': ''
                }
            
            if is_hs300:
                stock_map[bs_code]['is_hs300'] = 1
            if is_zz500:
                stock_map[bs_code]['is_zz500'] = 1

    add_stocks(df_hs300, is_hs300=True, is_zz500=False)
    add_stocks(df_zz500, is_hs300=False, is_zz500=True)
    
    # Enrich with Tushare data
    tushare_map = df_tushare.set_index('symbol').to_dict('index')
    
    final_stocks = []
    for bs_code, info in stock_map.items():
        symbol = info['symbol']
        
        if symbol in tushare_map:
            ts_data = tushare_map[symbol]
            info['area'] = ts_data.get('area', '')
            info['industry'] = ts_data.get('industry', '')
            info['list_date'] = str(ts_data.get('list_date', ''))
        
        final_stocks.append(info)
        
    return pd.DataFrame(final_stocks)

def save_stocks_to_db(df_stocks):
    print(f"Saving {len(df_stocks)} stocks to database...")
    conn = sqlite3.connect(DB_PATH)
    df_stocks.to_sql('stock_basic', conn, if_exists='replace', index=False)
    conn.close()

def fetch_and_save_kline(df_stocks):
    print("Fetching K-line data...")
    bs.login()
    
    conn = sqlite3.connect(DB_PATH)
    
    codes = df_stocks['code'].tolist()
    total = len(codes)
    
    for i, code in enumerate(codes):
        print(f"[{i+1}/{total}] Fetching {code}...")
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount,adjustflag",
            start_date=START_DATE,
            end_date=END_DATE,
            frequency="d",
            adjustflag="3" # 3: 不复权 (Unadjusted)
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
            
        if data_list:
            df_kline = pd.DataFrame(data_list, columns=rs.fields)
            # Convert numeric columns
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_cols:
                df_kline[col] = pd.to_numeric(df_kline[col])
            
            # Insert to DB
            df_kline.to_sql('stock_kline', conn, if_exists='append', index=False)
        else:
            print(f"  -> No data for {code}")
            
    bs.logout()
    conn.close()

if __name__ == "__main__":
    init_db()
    df_hs300, df_zz500 = get_baostock_constituents()
    df_stocks = process_stocks(df_hs300, df_zz500)
    
    if df_stocks is not None and not df_stocks.empty:
        save_stocks_to_db(df_stocks)
        fetch_and_save_kline(df_stocks)
        print("Done.")
    else:
        print("No stocks found or error in processing.")
