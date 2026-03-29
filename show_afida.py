with open(r"output\run_20260329_012759_6e772da2\reports_v3\CRITICAL_cik_1123661_report.md", "r", encoding="utf-8") as f:
    lines = f.readlines()
printing = False
for line in lines:
    if "## AFIDA" in line:
        printing = True
    elif printing and line.startswith("## ") and "AFIDA" not in line:
        break
    if printing:
        print(line.rstrip())
