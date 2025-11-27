import tushare as ts
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TUSHARE_TOKEN")
if not token:
    raise ValueError("TUSHARE_TOKEN 未设置，请检查 .env 文件")

pro = ts.pro_api()

df = pro.user(token=token)

print(df)