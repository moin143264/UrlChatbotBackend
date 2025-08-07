"""
Test script for Smart Entity Extraction System
Tests the enhanced AI's ability to identify companies, people, roles, timeline, etc.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from smart_extractor import SmartContentAnalyzer
import json

def test_company_extraction():
    """Test company name extraction from sample content"""
    analyzer = SmartContentAnalyzer()
    
    # Sample content similar to what's shown in the user's images
    sample_content = """
    My Experience As an AI Entrepreneur
    
    2012 - PRESENT: Co-Founder & Director - AI-Driven Promotions & Growth Hacking
    TROIKA MANAGEMENT
    
    2014 - PRESENT: Co-Founder, AI Strategy & Growth
    TROIKA TECH
    
    2021 - PRESENT: Business Innovation, Political Outreach & Digital PR
    TROIKA PLUS
    
    2022 - PRESENT: Director - Business Strategy & Digital Transformation
    TTS DIGITAL
    
    2023 - PRESENT: Co-Founder & Strategic Head
    TROIKA ONE
    
    Godwin is an AI Evangelist, Entrepreneur, and 4-Hour AI Website Specialist.
    He founded Troika Tech Services, Troika Management, and TTS Digital.
    
    Timeline:
    • 2012: Founded Troika Management
    • 2014: Co-founded Troika Tech Services  
    • 2021: Launched Troika Plus
    • 2022: Established TTS Digital
    • 2023: Created Troika One
    
    Skills: AI, Machine Learning, Digital Marketing, Business Strategy, Python, JavaScript
    """
    
    print("🧪 TESTING SMART ENTITY EXTRACTION")
    print("=" * 50)
    
    # Test comprehensive analysis
    analysis = analyzer.analyze_content(sample_content, "what companies does he work for?")
    
    print("\n📊 ANALYSIS RESULTS:")
    print(f"Confidence Score: {analysis['confidence_score']:.2f}")
    
    print(f"\n🏢 COMPANIES FOUND ({len(analysis['companies'])}):")
    for company in analysis['companies']:
        print(f"  • {company['name']} (confidence: {company['confidence']:.2f}) - {company.get('context', 'N/A')}")
    
    print(f"\n👤 PEOPLE FOUND ({len(analysis['people'])}):")
    for person in analysis['people']:
        print(f"  • {person['name']} (confidence: {person['confidence']:.2f}) - {person.get('context', 'N/A')}")
    
    print(f"\n💼 ROLES FOUND ({len(analysis['roles'])}):")
    for role in analysis['roles']:
        print(f"  • {role['title']} (confidence: {role['confidence']:.2f}) - {role.get('context', 'N/A')}")
    
    print(f"\n📅 TIMELINE FOUND ({len(analysis['timeline'])}):")
    for timeline in analysis['timeline']:
        if timeline['type'] == 'year_range':
            print(f"  • {timeline['start']}-{timeline['end']} (confidence: {timeline['confidence']:.2f})")
        elif timeline['type'] == 'single_year':
            print(f"  • {timeline['year']} (confidence: {timeline['confidence']:.2f})")
    
    print(f"\n🛠️ SKILLS FOUND ({len(analysis['skills'])}):")
    for skill in analysis['skills']:
        print(f"  • {skill['name']} (confidence: {skill['confidence']:.2f})")
    
    # Test smart context generation
    smart_context = analyzer.generate_smart_context(analysis, "what companies does he work for?")
    print(f"\n🎯 SMART CONTEXT GENERATED:")
    print(f"  {smart_context}")
    
    print("\n" + "=" * 50)
    return analysis

def test_different_questions():
    """Test how the analyzer responds to different types of questions"""
    analyzer = SmartContentAnalyzer()
    
    sample_content = """
    Godwin Pinto is a Co-Founder & Director at TTS Digital (2022-PRESENT).
    He also founded Troika Management in 2012 and Troika Tech Services in 2014.
    His expertise includes AI, Python, JavaScript, Digital Marketing, and Business Strategy.
    He has over 10 years of experience in technology and business development.
    """
    
    questions = [
        "what companies does he work for?",
        "who is Godwin?", 
        "what is his timeline?",
        "what skills does he have?",
        "tell me about TTS Digital",
        "list all companies"
    ]
    
    print("\n🔍 TESTING DIFFERENT QUESTION TYPES")
    print("=" * 50)
    
    for question in questions:
        print(f"\n❓ QUESTION: {question}")
        analysis = analyzer.analyze_content(sample_content, question)
        context = analyzer.generate_smart_context(analysis, question)
        print(f"📝 SMART CONTEXT: {context}")
        print(f"🏢 Companies: {len(analysis['companies'])}, 👤 People: {len(analysis['people'])}, 💼 Roles: {len(analysis['roles'])}")

if __name__ == "__main__":
    print("🚀 STARTING SMART ENTITY EXTRACTION TESTS")
    
    # Test 1: Company extraction
    analysis = test_company_extraction()
    
    # Test 2: Different question types
    test_different_questions()
    
    print("\n✅ ALL TESTS COMPLETED!")
    print("\nThe Smart Entity Extraction System should now be able to:")
    print("• Identify specific company names like 'TTS Digital', 'Troika Management', etc.")
    print("• Extract people names, roles, and timeline information")
    print("• Generate intelligent context based on the question asked")
    print("• Provide much more accurate and specific responses")
