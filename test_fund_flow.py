import akshare as ak
import pandas as pd

print("Testing Fund Flow Interfaces...")

try:
    print("1. 概念板块资金流向 (stock_sector_fund_flow_rank)...")
    # indicator: "今日", "5日", "10日"
    # sector_type: "行业", "概念", "地域"
    df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念")
    print(f"✅ Success! Got {len(df)} rows")
    # Columns usually: 排名, 名称, 今日涨跌幅, 今日主力净流入...
    print(df.head(5))
    print(df.columns.tolist())
except Exception as e:
    print(f"❌ Failed: {e}")

try:
    print("\n2. 同花顺概念资金流 (stock_fund_flow_concept)...")
    df2 = ak.stock_fund_flow_concept(symbol="即时")
    print(f"✅ Success! Got {len(df2)} rows")
    print(df2.head(5))
    
    # NEW TEST: Get constituents for the top concept
    top_concept = df2.iloc[0]['行业']
    print(f"\n3. Testing constituents for: {top_concept}")
    try:
        # Note: akshare function for simplified THS concept cons might vary. 
        # stock_board_concept_cons_ths(symbol="xxx") usually takes name?
        df_cons = ak.stock_board_concept_cons_ths(symbol=top_concept)
        print(f"✅ Constituents Found: {len(df_cons)}")
        print(df_cons.head(3))
    except Exception as e:
        print(f"❌ Failed to get cons for {top_concept}: {e}")

except Exception as e:
    print(f"❌ Failed: {e}")
