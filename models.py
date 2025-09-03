from dataclasses import dataclass
from typing import Optional

@dataclass
class Deal:
    id: str
    title: str
    amount: int
    buyer_id: int
    seller_id: Optional[int]
    status: str
