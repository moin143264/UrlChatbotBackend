#!/usr/bin/env python3
"""
AskMaven Search Diagnostic Tool
Diagnoses and fixes search issues with chunk-based search system
"""

import os
import sys
import pymysql
from dotenv import load_dotenv
from database import DatabaseManager

def main():
    print("🔍 AskMaven Search Diagnostic Tool")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Database connection
    try:
        connection = pymysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'hybrid_chatbot'),
            charset='utf8mb4'
        )
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    cursor = connection.cursor()
    
    # 1. Check scraped_pages table
    print("\n📊 Checking scraped_pages table...")
    cursor.execute("SELECT COUNT(*) FROM scraped_pages WHERE status='scraped'")
    scraped_count = cursor.fetchone()[0]
    print(f"   Total scraped pages: {scraped_count}")
    
    if scraped_count > 0:
        cursor.execute("SELECT url, title FROM scraped_pages WHERE status='scraped' LIMIT 3")
        sample_pages = cursor.fetchall()
        print("   Sample pages:")
        for url, title in sample_pages:
            print(f"   - {title[:50]}... ({url})")
    
    # 2. Check content_chunks table
    print("\n🧩 Checking content_chunks table...")
    try:
        cursor.execute("SELECT COUNT(*) FROM content_chunks")
        chunk_count = cursor.fetchone()[0]
        print(f"   Total content chunks: {chunk_count}")
        
        if chunk_count > 0:
            cursor.execute("""
                SELECT chunk_type, COUNT(*) as count 
                FROM content_chunks 
                GROUP BY chunk_type
            """)
            chunk_types = cursor.fetchall()
            print("   Chunk distribution:")
            for chunk_type, count in chunk_types:
                print(f"   - {chunk_type}: {count}")
            
            # Sample chunks
            cursor.execute("SELECT chunk_text FROM content_chunks LIMIT 5")
            sample_chunks = cursor.fetchall()
            print("\n   Sample chunks:")
            for i, (chunk_text,) in enumerate(sample_chunks, 1):
                print(f"   {i}. {chunk_text[:80]}...")
        else:
            print("   ⚠️  No content chunks found! This is the problem.")
            
    except Exception as e:
        print(f"   ❌ content_chunks table error: {e}")
        print("   This table might not exist or have issues.")
    
    # 3. Test DatabaseManager search
    print("\n🔍 Testing DatabaseManager search...")
    try:
        # Create database URL
        database_url = f"mysql+pymysql://{os.getenv('DB_USER', 'root')}:{os.getenv('DB_PASSWORD', '')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'hybrid_chatbot')}?charset=utf8mb4"
        db_manager = DatabaseManager(database_url)
        
        test_queries = [
            "Troika Tech Services",
            "Godwin Pinto", 
            "company",
            "director"
        ]
        
        for query in test_queries:
            print(f"\n   Testing query: '{query}'")
            results = db_manager.search_content(query, limit=3)
            print(f"   Results found: {len(results)}")
            
            for i, result in enumerate(results[:2], 1):
                title = result.get('title', 'No title')[:40]
                relevance = result.get('relevance_score', 0)
                print(f"   {i}. {title}... (relevance: {relevance})")
                
    except Exception as e:
        print(f"   ❌ DatabaseManager search failed: {e}")
    
    # 4. Check full-text indexes
    print("\n📇 Checking full-text indexes...")
    try:
        cursor.execute("SHOW INDEX FROM scraped_pages WHERE Index_type = 'FULLTEXT'")
        indexes = cursor.fetchall()
        if indexes:
            print("   ✅ Full-text indexes found:")
            for index in indexes:
                print(f"   - {index[2]} on {index[4]}")
        else:
            print("   ⚠️  No full-text indexes found")
            
        cursor.execute("SHOW INDEX FROM content_chunks WHERE Index_type = 'FULLTEXT'")
        chunk_indexes = cursor.fetchall()
        if chunk_indexes:
            print("   ✅ Chunk full-text indexes found:")
            for index in chunk_indexes:
                print(f"   - {index[2]} on {index[4]}")
        else:
            print("   ⚠️  No chunk full-text indexes found")
            
    except Exception as e:
        print(f"   ❌ Index check failed: {e}")
    
    # 5. Recommendations
    print("\n💡 Recommendations:")
    if chunk_count == 0:
        print("   🔧 CRITICAL: Re-scrape all pages to populate content_chunks")
        print("   🔧 Run: python rescrape_all.py")
    elif chunk_count < scraped_count * 3:
        print("   🔧 WARNING: Low chunk count, consider re-scraping")
    
    print("   🔧 Ensure full-text indexes are properly created")
    print("   🔧 Test individual search components")
    
    cursor.close()
    connection.close()
    print("\n✅ Diagnostic complete!")

if __name__ == "__main__":
    main()
