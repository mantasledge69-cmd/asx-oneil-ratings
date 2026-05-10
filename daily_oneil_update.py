import os
import sys
import logging
import subprocess
import time
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    filename='daily_oneil_update.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_script(script_name, description):
    print(f"\n→ {description}")
    logging.info(f"Starting: {description}")

    cmd = [sys.executable, script_name]

    try:
        time.sleep(1.0)
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=7200)
        
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print("Warnings:", result.stderr.strip())
            
        logging.info(f"Completed: {description}")
        return True
        
    except Exception as e:
        print(f"❌ Failed {description}: {e}")
        logging.error(f"Failed {description}: {e}")
        return False

def main():
    print("="*80)
    print("🚀 DAILY O'NEIL ASX UPDATE STARTED")
    print("="*80)
    logging.info("=== Daily Update Cycle Started ===")
    start_time = datetime.now()

    steps = [
        ("update_asx_company_list.py",      "1. Update ASX Company Master List"),
        ("daily_price_update_smart.py",     "2. Update Latest Prices"),
        ("calculate_rs_ratings.py",         "3. Calculate Stock RS Ratings"),
        ("calculate_sector_rs.py",          "4. Calculate Sector RS Ratings"),
        ("calculate_sector_emas.py",        "5. Calculate Sector EMAs"),
        ("build_combined_view.py",          "6. Build Combined Dashboard View")
    ]

    success = 0
    for script, desc in steps:
        if run_script(script, desc):
            success += 1

    duration = datetime.now() - start_time
    print(f"\n✅ Update finished in {duration}")
    print(f"Successful steps: {success}/6")

    if success >= 5:
        print("🎉 Core daily update completed successfully!")
    else:
        print("⚠️ Some steps had issues - check daily_oneil_update.log")

if __name__ == "__main__":
    main()