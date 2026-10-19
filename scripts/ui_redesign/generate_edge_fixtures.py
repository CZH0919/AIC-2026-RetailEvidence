"""Create only synthetic parsing edge fixtures inside an explicit test root."""
import argparse
from pathlib import Path
from openpyxl import Workbook

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, required=True)
args = parser.parse_args()
folder = args.root.resolve() / "edge-fixtures"
folder.mkdir(parents=True, exist_ok=True)
(folder / "gbk.csv").write_text("商品编号,数量,行金额,交易时间\nP001,3,12.00,2026-09-01\n", encoding="gb18030")
book = Workbook()
sheet = book.active
sheet.title = "Sales"
sheet.append(["商品编号", "数量", "行金额", "交易时间"])
sheet.append(["P001", 3, 12, "2026-09-01"])
notes = book.create_sheet("Notes")
notes.append(["备注"])
notes.append(["模拟说明"])
book.save(folder / "two-sheets.xlsx")
