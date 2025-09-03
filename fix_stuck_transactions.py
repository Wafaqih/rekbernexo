
import asyncio
from db_sqlite import get_connection
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fix_stuck_transaction(deal_id):
    """Fix transaksi yang stuck di WAITING_VERIFICATION"""
    conn = get_connection()
    cur = conn.cursor()
    
    print(f"Fixing transaction {deal_id}...")
    
    # Get current transaction status
    cur.execute("""
        SELECT id, title, amount, buyer_id, seller_id, status, created_at
        FROM deals 
        WHERE id = ?
    """, (deal_id,))
    
    tx = cur.fetchone()
    if not tx:
        print(f"Transaction {deal_id} not found!")
        conn.close()
        return
    
    print("Current transaction state:")
    print(f"  Title: {tx['title']}")
    print(f"  Amount: {tx['amount']}")
    print(f"  Buyer ID: {tx['buyer_id']}")
    print(f"  Seller ID: {tx['seller_id']}")
    print(f"  Status: {tx['status']}")
    print(f"  Created: {tx['created_at']}")
    
    # If status is WAITING_VERIFICATION, reset it to FUNDED for testing
    if tx['status'] == 'WAITING_VERIFICATION':
        print("\n🔧 Fixing stuck WAITING_VERIFICATION status...")
        cur.execute("UPDATE deals SET status = ? WHERE id = ?", ("FUNDED", deal_id))
        conn.commit()
        print("✅ Status updated to FUNDED")
        
        # Log the fix
        from db_sqlite import log_action
        log_action(deal_id, 1, "ADMIN", "STATUS_FIX", "Fixed stuck WAITING_VERIFICATION status")
        
    elif tx['status'] == 'PENDING_FUNDING':
        print("\n🔧 Transaction ready for funding...")
        print("Buyer should now make payment")
        
    elif tx['status'] == 'FUNDED':
        print("\n✅ Transaction is properly funded and ready for shipping")
        
    else:
        print(f"\n⚠️ Transaction status is {tx['status']} - no fix needed")
    
    conn.close()
    print("\nDone!")

def list_stuck_transactions():
    """List all potentially stuck transactions"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, status, buyer_id, seller_id, created_at
        FROM deals 
        WHERE status IN ('WAITING_VERIFICATION', 'PENDING_FUNDING', 'FUNDED')
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    transactions = cur.fetchall()
    conn.close()
    
    print("="*60)
    print("POTENTIALLY STUCK TRANSACTIONS")
    print("="*60)
    
    for tx in transactions:
        print(f"ID: {tx['id']}")
        print(f"Title: {tx['title']}")
        print(f"Status: {tx['status']}")
        print(f"Buyer: {tx['buyer_id']}")
        print(f"Seller: {tx['seller_id']}")
        print(f"Created: {tx['created_at']}")
        print("-" * 40)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_stuck_transactions()
        else:
            fix_stuck_transaction(sys.argv[1])
    else:
        list_stuck_transactions()
import asyncio
from db_sqlite import get_connection
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fix_stuck_transaction(deal_id):
    """Fix transaksi yang stuck di WAITING_VERIFICATION"""
    conn = get_connection()
    cur = conn.cursor()
    
    print(f"Fixing transaction {deal_id}...")
    
    # Get current transaction status
    cur.execute("""
        SELECT id, title, amount, buyer_id, seller_id, status, created_at
        FROM deals 
        WHERE id = ?
    """, (deal_id,))
    
    tx = cur.fetchone()
    if not tx:
        print(f"Transaction {deal_id} not found!")
        conn.close()
        return
    
    print("Current transaction state:")
    print(f"  Title: {tx['title']}")
    print(f"  Amount: {tx['amount']}")
    print(f"  Buyer ID: {tx['buyer_id']}")
    print(f"  Seller ID: {tx['seller_id']}")
    print(f"  Status: {tx['status']}")
    print(f"  Created: {tx['created_at']}")
    
    # If status is WAITING_VERIFICATION, reset it to FUNDED for testing
    if tx['status'] == 'WAITING_VERIFICATION':
        print("\n🔧 Fixing stuck WAITING_VERIFICATION status...")
        cur.execute("UPDATE deals SET status = ? WHERE id = ?", ("FUNDED", deal_id))
        conn.commit()
        print("✅ Status updated to FUNDED")
        
        # Log the fix
        from db_sqlite import log_action
        log_action(deal_id, 1, "ADMIN", "STATUS_FIX", "Fixed stuck WAITING_VERIFICATION status")
        
    elif tx['status'] == 'PENDING_FUNDING':
        print("\n🔧 Transaction ready for funding...")
        print("Buyer should now make payment")
        
    elif tx['status'] == 'FUNDED':
        print("\n✅ Transaction is properly funded and ready for shipping")
        
    else:
        print(f"\n⚠️ Transaction status is {tx['status']} - no fix needed")
    
    conn.close()
    print("\nDone!")

def list_stuck_transactions():
    """List all potentially stuck transactions"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, status, buyer_id, seller_id, created_at
        FROM deals 
        WHERE status IN ('WAITING_VERIFICATION', 'PENDING_FUNDING', 'FUNDED')
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    transactions = cur.fetchall()
    conn.close()
    
    print("="*60)
    print("POTENTIALLY STUCK TRANSACTIONS")
    print("="*60)
    
    for tx in transactions:
        print(f"ID: {tx['id']}")
        print(f"Title: {tx['title']}")
        print(f"Status: {tx['status']}")
        print(f"Buyer: {tx['buyer_id']}")
        print(f"Seller: {tx['seller_id']}")
        print(f"Created: {tx['created_at']}")
        print("-" * 40)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_stuck_transactions()
        else:
            fix_stuck_transaction(sys.argv[1])
    else:
        list_stuck_transactions()
