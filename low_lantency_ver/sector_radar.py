import akshare as ak
import json
import os
import logging
from typing import List, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def format_stock_code(code: str) -> str:
    """
    格式化股票代码，添加 sh/sz/bj 前缀 (沪深京)
    """
    code = str(code).strip()
    if len(code) != 6:
         # 可能已经带有前缀或不是标准股票代码
         return code
        
    if code.startswith(('60', '68')):
        return f"sh{code}"
    elif code.startswith(('00', '30')):
        return f"sz{code}"
    elif code.startswith(('4', '8', '9')):
        return f"bj{code}"
    else:
        return code

def read_my_stocks(filepath: str) -> List[str]:
    """
    读取个人持仓/自选股列表
    """
    result = []
    if not os.path.exists(filepath):
        logging.warning(f"自选股文件不存在: {filepath}")
        return result
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                code = line.strip()
                if code and not code.startswith('#'):
                    # 尝试清理可能存在的部分非数字字符，然后格式化
                    # 如果原文本就是 sh600000 这种，可以直接加入
                    if code.lower().startswith(('sh', 'sz', 'bj')):
                        result.append(code.lower())
                    else:
                        result.append(format_stock_code(code))
    except Exception as e:
        logging.error(f"读取持仓文件失败: {e}")
        
    return result

def get_top_sectors(top_n: int = 5) -> List[str]:
    """
    获取东方财富行业板块实时行情，筛选涨幅居前的板块
    """
    try:
        logging.info("开始获取行业板块数据...")
        df_sectors = ak.stock_board_industry_name_em()
        
        # 按“涨跌幅”降序排列，取前 top_n 个
        if '涨跌幅' in df_sectors.columns:
            df_sorted = df_sectors.sort_values(by="涨跌幅", ascending=False)
        else:
            logging.error("未找到‘涨跌幅’字段，数据结构可能变化")
            return []
            
        # 提取板块名称
        top_sector_names = df_sorted.head(top_n)['板块名称'].tolist()
        logging.info(f"成功获取前 {top_n} 个强势板块: {top_sector_names}")
        return top_sector_names
        
    except Exception as e:
        logging.error(f"获取强势板块异常（可能网络超时或接口变动）: {e}")
        return []

def get_sector_constituents(sector_name: str, top_n: int = 8) -> List[str]:
    """
    获取指定板块内的核心成分股（涨幅靠前）
    """
    try:
        logging.info(f"正在获取板块成份股: {sector_name}")
        df_cons = ak.stock_board_industry_cons_em(symbol=sector_name)
        
        if '涨跌幅' in df_cons.columns:
            df_sorted = df_cons.sort_values(by="涨跌幅", ascending=False)
        else:
            df_sorted = df_cons
            
        # 提取股票代码
        raw_codes = df_sorted.head(top_n)['代码'].tolist()
        # 格式化代码带上 sh/sz 后缀
        formatted_codes = [format_stock_code(code) for code in raw_codes]
        
        return formatted_codes
    except Exception as e:
        logging.error(f"获取板块 {sector_name} 的成份股异常: {e}")
        return []

def main():
    # 路径配置
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    my_stocks_path = os.path.join(data_dir, "my_stocks.txt")
    output_json_path = os.path.join(data_dir, "sector_radar.json")
    
    # 确保 data 目录存在
    os.makedirs(data_dir, exist_ok=True)
    
    # 结果字典
    radar_data: Dict[str, Any] = {
        "strong_sectors": [],
        "candidate_stocks": []
    }
    
    # 1. 获取强势板块 (题干要求提取 3 个板块，最终组装 5 个名称，这里我们直接抓取排名前 5 的以防数据不够)
    # 此处取前 3 名进入深度成分股提取，但把前5名存入 sectors
    top_5_sectors = get_top_sectors(top_n=5)
    radar_data["strong_sectors"] = top_5_sectors
    
    all_candidates_set = set()
    
    # 2. 提取核心成分股 (取排名前3的板块，每个板块 8 只，总计不超过 30只)
    if len(top_5_sectors) >= 3:
        core_sectors = top_5_sectors[:3]
    else:
        core_sectors = top_5_sectors
        
    for sector in core_sectors:
        cons = get_sector_constituents(sector, top_n=8)
        all_candidates_set.update(cons)
        
    # 3. 读取个人持仓并加入观测池
    my_stocks = read_my_stocks(my_stocks_path)
    all_candidates_set.update(my_stocks)
    
    # 将汇总后的候选股列表存入结果字典，转存为 list 并排序保证一致性
    radar_data["candidate_stocks"] = sorted(list(all_candidates_set))
    
    # 4. JSON 格式静默写入
    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(radar_data, f, ensure_ascii=False, indent=4)
        logging.info(f"雷达扫描数据已成功写入: {output_json_path}")
    except Exception as e:
        logging.error(f"写入 JSON 数据至 {output_json_path} 时发生错误: {e}")

if __name__ == "__main__":
    main()
