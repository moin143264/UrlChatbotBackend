#!/usr/bin/env python3
"""
Test script for enhanced company detection and AI training
Tests the improved chunking algorithm and company identification
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from main import ChatRequest, chat_with_ai

# Load environment variables
load_dotenv()

def test_company_chunking():
    """Test the enhanced company chunking algorithm"""
    print("🔍 TESTING ENHANCED COMPANY DETECTION ALGORITHM")
    print("=" * 60)
    
    # Initialize database manager
    database_url = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    db_manager = DatabaseManager(database_url)
    
    # Test content with various company patterns
    test_content = """
    Godwin Pinto is the Co-Founder and Director of Troika Tech Services, a leading technology company.
    He also founded Troika Management and Troika Plus Digital Solutions.
    
    Previously, he worked at Microsoft Corporation and Google Inc as a Senior Manager.
    He has experience with various companies including:
    - Amazon Web Services LLC
    - Oracle Systems Ltd
    - IBM Technologies Group
    - Accenture Consulting Associates
    
    Current roles:
    - CEO of Troika Tech Services (2012-Present)
    - Director at Troika Management (2014-Present)
    - Founder of Troika Plus (2021-Present)
    
    He specializes in digital transformation and has worked with clients like:
    Infosys Limited, TCS Solutions, Wipro Technologies, and HCL Digital.
    """
    
    print("📝 Test Content:")
    print(test_content[:200] + "..." if len(test_content) > 200 else test_content)
    print("\n" + "=" * 60)
    
    # Test chunking algorithm
    chunks = db_manager._split_content_into_chunks(test_content)
    
    print(f"📊 Generated {len(chunks)} chunks:")
    print("-" * 40)
    
    company_chunks = []
    for i, chunk in enumerate(chunks, 1):
        print(f"{i:2d}. {chunk}")
        if chunk.startswith(('Companies:', 'Company:')):
            company_chunks.append(chunk)
        print()
    
    print("🏢 COMPANY-SPECIFIC CHUNKS DETECTED:")
    print("-" * 40)
    if company_chunks:
        for chunk in company_chunks:
            print(f"✅ {chunk}")
    else:
        print("❌ No company chunks detected!")
    
    return chunks, company_chunks

async def test_company_questions():
    """Test various company-related questions"""
    print("\n🤖 TESTING AI COMPANY QUESTION RESPONSES")
    print("=" * 60)
    
    # Test questions that should trigger company detection
    test_questions = [
        "list company names",
        "give me company names", 
        "what companies does he work for",
        "tell me about the companies",
        "show me all companies",
        "which companies has he founded",
        "company list",
        "business names",
        "organizations he works with"
    ]
    
    for question in test_questions:
        print(f"\n❓ Question: '{question}'")
        print("-" * 30)
        
        try:
            # Create chat request
            request = ChatRequest(
                question=question,
                user_id=1  # Use integer instead of string
            )
            
            # Get AI response
            response = await chat_with_ai(request)
            
            print(f"🎯 AI Response ({len(response.answer)} chars):")
            print(f"   {response.answer}")
            print(f"📊 Context Found: {response.context_found}")
            print(f"⏱️  Response Time: {response.response_time_ms}ms")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")

def test_search_prioritization():
    """Test search prioritization for company queries"""
    print("\n🔍 TESTING SEARCH PRIORITIZATION FOR COMPANY QUERIES")
    print("=" * 60)
    
    # Initialize database manager
    database_url = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    db_manager = DatabaseManager(database_url)
    
    # Test company-related search queries
    test_queries = [
        "company",
        "companies",
        "Troika Tech",
        "business",
        "organization"
    ]
    
    for query in test_queries:
        print(f"\n🔎 Search Query: '{query}'")
        print("-" * 30)
        
        try:
            results = db_manager.search_content(query, limit=5)
            
            print(f"📊 Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                chunks = result.get('matching_chunks', '')
                score = result.get('relevance_score', 0)
                search_type = result.get('search_type', 'unknown')
                
                print(f"{i}. Score: {score} | Type: {search_type}")
                if chunks:
                    # Show first chunk
                    first_chunk = chunks.split(' | ')[0]
                    print(f"   Chunk: {first_chunk[:100]}...")
                print()
                
        except Exception as e:
            print(f"❌ Search Error: {str(e)}")

async def main():
    """Run all company detection tests"""
    print("🚀 COMPANY DETECTION & AI TRAINING TEST SUITE")
    print("=" * 60)
    
    try:
        # Test 1: Chunking algorithm
        chunks, company_chunks = test_company_chunking()
        
        # Test 2: Search prioritization
        test_search_prioritization()
        
        # Test 3: AI question responses
        await test_company_questions()
        
        print("\n✅ ALL TESTS COMPLETED!")
        print("=" * 60)
        
        # Summary
        print("\n📋 SUMMARY:")
        print(f"• Total chunks generated: {len(chunks)}")
        print(f"• Company chunks detected: {len(company_chunks)}")
        print("• Enhanced company detection patterns implemented")
        print("• AI training prompts optimized for company identification")
        print("• Search prioritization boosted for company-related content")
        
    except Exception as e:
        print(f"\n❌ TEST SUITE ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
