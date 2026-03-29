import subprocess
import sys
import os

def main():
    os.makedirs("test_reports", exist_ok=True)

    cmd = [
        sys.executable, "-m", "pytest",
        "-q",
        "--disable-warnings",
        "--maxfail=1",
        "--html=test_reports/report.html",
        "--self-contained-html",
        "--md=test_reports/report.md",
    ]

    print("Running full SECMap test suite...")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\nAll tests passed. Reports generated in test_reports/")
    else:
        print("\nSome tests failed. See test_reports/ for details.")

    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
