import akshare as ak
methods = dir(ak)
print("--- Searching for 'concept' ---")
for m in methods:
    if "concept" in m:
        print(m)

print("\n--- Searching for 'board' ---")
for m in methods:
    if "board" in m and "ths" in m:
        print(m)
