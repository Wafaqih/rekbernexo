
import asyncio
from db_sqlite import get_connection
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_all_transactions():
    """Debug semua transaksi aktif"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, amount, buyer_id, seller_id, status, created_at
        FROM deals 
        WHERE status NOT IN ('COMPLETED', 'CANCELLED', 'REFUNDED')
        ORDER BY created_at DESC
        LIMIT 20
    """)
    
    transactions = cur.fetchall()
    conn.close()
    
    print("="*60)
    print("DEBUG: ACTIVE TRANSACTIONS")
    print("="*60)
    
    for tx in transactions:
        print(f"ID: {tx['id']}")
        print(f"Title: {tx['title']}")
        print(f"Amount: {tx['amount']}")
        print(f"Buyer ID: {tx['buyer_id']}")
        print(f"Seller ID: {tx['seller_id']}")
        print(f"Status: {tx['status']}")
        print(f"Created: {tx['created_at']}")
        print("-" * 40)

def debug_specific_transaction(deal_id):
    """Debug transaksi spesifik"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, amount, admin_fee, admin_fee_payer, buyer_id, seller_id, status, created_at
        FROM deals 
        WHERE id = %s
    """, (deal_id,))
    
    tx = cur.fetchone()
    conn.close()
    
    if not tx:
        print(f"Transaction {deal_id} not found!")
        return
        
    print("="*60)
    print(f"DEBUG: TRANSACTION {deal_id}")
    print("="*60)
    print(f"Title: {tx['title']}")
    print(f"Amount: {tx['amount']}")
    print(f"Admin Fee: {tx['admin_fee']}")
    print(f"Fee Payer: {tx['admin_fee_payer']}")
    print(f"Buyer ID: {tx['buyer_id']}")
    print(f"Seller ID: {tx['seller_id']}")
    print(f"Status: {tx['status']}")
    print(f"Created: {tx['created_at']}")
    
    # Check if both roles filled
    if tx['buyer_id'] and tx['seller_id']:
        print("✅ Both buyer and seller assigned")
    elif tx['buyer_id']:
        print("⚠️ Only buyer assigned, waiting for seller")
    elif tx['seller_id']:
        print("⚠️ Only seller assigned, waiting for buyer")
    else:
        print("❌ No parties assigned yet")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        debug_specific_transaction(sys.argv[1])
    else:
        debug_all_transactions()
