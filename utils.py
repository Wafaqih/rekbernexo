import random
import datetime
import re
import time
from functools import lru_cache

# Cache untuk menghindari duplicate ID generation
_last_generated_time = 0
_sequence_counter = 0

def generate_deal_id():
    global _last_generated_time, _sequence_counter
    current_time = time.time()

    if current_time == _last_generated_time:
        _sequence_counter += 1
    else:
        _last_generated_time = current_time
        _sequence_counter = 0

    # Menggunakan sequence counter untuk memastikan keunikan dalam milidetik
    timestamp_part = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3] # Milliseconds
    random_part = random.randint(1000, 9999)
    sequence_part = f"{_sequence_counter:03d}" # 3 digit sequence number

    return f"RB-{timestamp_part}-{random_part}-{sequence_part}"


def format_rupiah(n) -> str:
    # Ensure n is an integer
    try:
        amount = int(n) if n is not None else 0
    except (ValueError, TypeError):
        amount = 0

    # Format number with comma separator, then replace with dot
    formatted = f"Rp {amount:,}"
    return formatted.replace(",", ".")

def calculate_admin_fee(amount: int) -> int:
    if amount <= 100_000:
        return 2000
    elif amount <= 500_000:
        return 5000
    elif amount <= 1_000_000:
        return int(amount * 0.01)  # 1%
    else:
        return int(amount * 0.005)  # 0.5%