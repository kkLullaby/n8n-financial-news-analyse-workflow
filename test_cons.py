import akshare as ak

print("Testing Concept Constituents...")

name = "黄金概念"

try:
    print(f"1. EM Constituents for {name}")
    df = ak.stock_board_concept_cons_em(symbol=name)
    print(df.head(3))
except Exception as e:
    print(f"❌ EM Failed: {e}")

try:
    print(f"\n2. THS Info for {name}")
    # symbol might need to be url or code from the name_ths list?
    # but let's try name first
    df2 = ak.stock_board_concept_info_ths(symbol=name)
    print(df2)
except Exception as e:
    print(f"❌ THS Info Failed: {e}")
