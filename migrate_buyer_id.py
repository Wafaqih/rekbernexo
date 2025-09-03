
#!/usr/bin/env python3
import os
import psycopg2
import psycopg2.extras

def migrate_buyer_id():
    """Migrate database to allow NULL buyer_id"""
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    cur = conn.cursor()
    
    try:
        print("Starting migration: Allow NULL buyer_id...")
        
        # Drop the NOT NULL constraint on buyer_id
        cur.execute("ALTER TABLE deals ALTER COLUMN buyer_id DROP NOT NULL")
        
        # Add constraint to ensure at least one participant exists
        cur.execute("""
        ALTER TABLE deals ADD CONSTRAINT deals_participants_check 
        CHECK (buyer_id IS NOT NULL OR seller_id IS NOT NULL)
        """)
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate_buyer_id()
