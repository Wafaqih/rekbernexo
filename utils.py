import random
import datetime
import re
import time
from functools import lru_cache

# Cache untuk menghindari duplicate ID generation
_last_generated_time = 0
_sequence_counter = 0

def generate_deal_id():
    """
    Generate a unique, user-friendly transaction ID
    Format: RB-YYMMDD-HHMMSS-XXX
    Example: RB-250903-143022-A4B
    
    Components:
    - RB: Rekber Bot prefix
    - YYMMDD: Year/Month/Day (6 digits)
    - HHMMSS: Hour/Minute/Second (6 digits)  
    - XXX: Random 3-character alphanumeric (for uniqueness)
    """
    global _last_generated_time, _sequence_counter
    current_time = time.time()

    if current_time == _last_generated_time:
        _sequence_counter += 1
    else:
        _last_generated_time = current_time
        _sequence_counter = 0

    # Generate readable date and time parts
    now = datetime.datetime.now()
    date_part = now.strftime('%y%m%d')  # YYMMDD (6 chars)
    time_part = now.strftime('%H%M%S')  # HHMMSS (6 chars)
    
    # Generate 3-character random alphanumeric for uniqueness
    # Using combination of letters and numbers for better readability
    chars = 'ABCDEFGHIJKLMNPQRSTUVWXYZ123456789'  # Exclude O, 0 to avoid confusion
    random_part = ''.join(random.choice(chars) for _ in range(3))
    
    # Add sequence if multiple generated in same second
    if _sequence_counter > 0:
        # Increment last character for sequence
        last_char_idx = chars.index(random_part[-1])
        next_char_idx = (last_char_idx + _sequence_counter) % len(chars)
        random_part = random_part[:-1] + chars[next_char_idx]

    return f"RB-{date_part}-{time_part}-{random_part}"


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