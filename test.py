import asyncio
import os
from datetime import datetime

import pandas as pd

from spider import scrape_xianyu


def save_to_excel(data_list, filename="商品数据.xlsx"):
    if not data_list:
        print("没有需要保存的数据")
        return

    df = pd.DataFrame(data_list).drop_duplicates(subset=["商品链接"], keep="first")
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    out_dir = desktop if os.path.isdir(desktop) else os.getcwd()
    filepath = os.path.join(out_dir, filename)

    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="商品列表")
        workbook = writer.book
        worksheet = writer.sheets["商品列表"]
        header_format = workbook.add_format(
            {
                "bold": True,
                "text_wrap": True,
                "valign": "top",
                "fg_color": "#4F81BD",
                "font_color": "white",
                "border": 1,
            }
        )
        col_widths = {
            "商品标题": 50,
            "当前售价": 15,
            "发货地区": 15,
            "卖家昵称": 20,
            "商品链接": 60,
            "商品图片链接": 60,
            "发布时间": 20,
        }
        for col_num, (col_name, width) in enumerate(col_widths.items()):
            worksheet.set_column(col_num, col_num, width)
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

    print(f"数据已保存到：{filepath}")


if __name__ == "__main__":
    keyword = os.environ.get("XIANYU_KEYWORD") or input("请输入要搜索的商品关键词：").strip()
    pages_raw = os.environ.get("XIANYU_PAGES") or input("请输入要爬取的最大页数：").strip() or "1"
    pages = int(pages_raw)
    print(f"开始爬取 {keyword} 的前 {pages} 页数据...")
    data_list = asyncio.run(scrape_xianyu(keyword, max_pages=pages))
    if data_list:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_keyword = "".join(e for e in keyword if e.isalnum())
        filename = f"闲鱼爬取结果_{safe_keyword}_共{pages}页_{timestamp}.xlsx"
        save_to_excel(data_list, filename)
    else:
        print("没有采集到任何商品数据")
    print("爬取任务结束")
