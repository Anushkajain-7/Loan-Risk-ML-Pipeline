"""Daily retention with private, value-free error output."""
import time
from scripts.retention import main
if __name__=='__main__':
    while True:
        try:main();time.sleep(86400)
        except Exception:print('Retention unavailable; retrying.');time.sleep(60)
