#!/usr/bin/env python3
"""
Test script for AskMaven Backend
Tests basic functionality before Vercel deployment
"""

import requests
import json
import time

# Test configuration
BASE_URL = "http://localhost:8000"  # Change to your Vercel URL after deployment

def test_health_check():
    """Test the health check endpoint"""
    print("🔍 Testing health check endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Health check passed!")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_docs_endpoint():
    """Test the API documentation endpoint"""
    print("\n🔍 Testing API docs endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ API docs accessible!")
            return True
        else:
            print(f"❌ API docs failed with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API docs error: {e}")
        return False

def test_chat_endpoint():
    """Test the chat endpoint with a simple message"""
    print("\n🔍 Testing chat endpoint...")
    try:
        chat_data = {
            "question": "Hello, can you help me?",
            "user_id": 1,
            "context_limit": 5
        }
        
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=chat_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Chat endpoint working!")
            result = response.json()
            print(f"AI Response: {result.get('response', 'No response')[:100]}...")
            return True
        else:
            print(f"❌ Chat endpoint failed with status: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Chat endpoint error: {e}")
        return False

def test_scraping_endpoint():
    """Test the scraping endpoint"""
    print("\n🔍 Testing scraping endpoint...")
    try:
        scrape_data = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "user_id": 1
        }
        
        response = requests.post(
            f"{BASE_URL}/api/scrape-sitemap",
            json=scrape_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Scraping endpoint working!")
            result = response.json()
            print(f"Scraping started: {result}")
            return True
        else:
            print(f"❌ Scraping endpoint failed with status: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Scraping endpoint error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 AskMaven Backend Test Suite")
    print("=" * 50)
    
    tests = [
        test_health_check,
        test_docs_endpoint,
        test_chat_endpoint,
        test_scraping_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        time.sleep(1)  # Small delay between tests
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend is ready for deployment.")
    else:
        print("⚠️  Some tests failed. Check your configuration.")
    
    return passed == total

if __name__ == "__main__":
    main()
