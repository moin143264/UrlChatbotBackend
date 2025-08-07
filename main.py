"""
Hybrid Chatbot System - Python FastAPI Backend
Handles web scraping, Gemini AI integration, and API endpoints
Compatible with Python 3.13
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import google.generativeai as genai
import pymysql
from dotenv import load_dotenv

from scraper import WebScraper
from models import ScrapingRequest, ChatRequest, ChatResponse, ScrapingStatus
from database import DatabaseManager
from smart_extractor import SmartContentAnalyzer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Debug: Check if Gemini API key is loaded
gemini_key = os.getenv('GEMINI_API_KEY')
if gemini_key:
    logger.info(f"Gemini API key loaded: {gemini_key[:10]}...")
else:
    logger.error("Gemini API key not found in environment variables!")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'hybrid_chatbot'),
    'charset': 'utf8mb4'
}

# Initialize Gemini AI
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')  # Using Flash for higher rate limits

# Global instances
web_scraper = WebScraper()
smart_analyzer = SmartContentAnalyzer()

# Initialize DatabaseManager with chunking support
database_url = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
db_manager = DatabaseManager(database_url)

def get_db_connection():
    """Get database connection"""
    return pymysql.connect(**DB_CONFIG)

def execute_query(query, params=None, fetch=None):
    """Execute database query with PyMySQL"""
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, params or ())
            
            if fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'all':
                return cursor.fetchall()
            else:
                # For INSERT/UPDATE/DELETE operations
                connection.commit()
                return cursor.lastrowid if cursor.lastrowid else True
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        connection.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting Hybrid Chatbot Python Backend...")
    yield
    logger.info("Shutting down Hybrid Chatbot Python Backend...")

# Initialize FastAPI app
app = FastAPI(
    title="Hybrid Chatbot API",
    description="Python backend for hybrid chatbot system with web scraping and Gemini AI",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for PHP frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Hybrid Chatbot Python Backend is running",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/scrape-sitemap")
async def scrape_sitemap(
    request: ScrapingRequest,
    background_tasks: BackgroundTasks
):
    """
    Start scraping a website from sitemap URL
    """
    try:
        # Validate sitemap URL
        sitemap_url = str(request.sitemap_url)
        domain = request.sitemap_url.host
        
        logger.info(f"Starting scraping for sitemap: {sitemap_url}")
        
        # Check if sitemap already exists and its current status
        existing = execute_query(
            "SELECT id, status, scraped_pages, total_pages FROM sitemap_sources WHERE sitemap_url = %s",
            (sitemap_url,),
            fetch='one'
        )
        
        if existing:
            # Check if scraping is already in progress or completed
            if existing['status'] == 'scraping':
                return {
                    "message": "Scraping is already in progress for this sitemap",
                    "sitemap_id": existing['id'],
                    "status": "scraping"
                }
            elif existing['status'] == 'completed' and existing['scraped_pages'] > 0:
                return {
                    "message": "Sitemap has already been scraped successfully",
                    "sitemap_id": existing['id'],
                    "status": "completed",
                    "scraped_pages": existing['scraped_pages'],
                    "total_pages": existing['total_pages']
                }
            else:
                # Only re-scrape if status is 'failed' or 'pending' with no successful pages
                execute_query(
                    "UPDATE sitemap_sources SET status = 'pending', updated_at = NOW() WHERE sitemap_url = %s",
                    (sitemap_url,)
                )
                sitemap_id = existing['id']
        else:
            # Create new entry
            sitemap_id = execute_query(
                "INSERT INTO sitemap_sources (sitemap_url, domain, created_by, status) VALUES (%s, %s, %s, 'pending')",
                (sitemap_url, domain, request.user_id)
            )
        
        # Start background scraping task
        background_tasks.add_task(
            scrape_website_background,
            sitemap_url,
            sitemap_id,
            request.user_id
        )
        
        return {
            "message": "Scraping started successfully",
            "sitemap_id": sitemap_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"Error starting scraping: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start scraping: {str(e)}")

async def scrape_website_background(sitemap_url: str, sitemap_id: int, user_id: int):
    """Background task for scraping website"""
    try:
        # Update status to scraping
        execute_query(
            "UPDATE sitemap_sources SET status = 'scraping' WHERE id = %s",
            (sitemap_id,)
        )
        
        # Perform scraping
        scraped_data = await web_scraper.scrape_from_sitemap(sitemap_url)
        
        total_pages = len(scraped_data)
        scraped_count = 0
        failed_count = 0
        
        # Store scraped data
        for page_data in scraped_data:
            try:
                # Insert or update scraped page with chunking support
                page_id = db_manager.insert_scraped_page(page_data)
                if page_id:
                    scraped_count += 1
                    logger.info(f"Successfully stored page with chunks: {page_data.get('url', 'unknown')}")
                else:
                    failed_count += 1
                    logger.error(f"Failed to store page: {page_data.get('url', 'unknown')}")
            except Exception as e:
                logger.error(f"Error storing page {page_data.get('url', 'unknown')}: {str(e)}")
                failed_count += 1
        
        # Update sitemap source with final counts
        execute_query(
            """
            UPDATE sitemap_sources 
            SET total_pages = %s, scraped_pages = %s, failed_pages = %s,
                status = 'completed', last_scraped = NOW()
            WHERE id = %s
            """,
            (total_pages, scraped_count, failed_count, sitemap_id)
        )
        
        logger.info(f"Scraping completed: {scraped_count}/{total_pages} pages successful")
        
    except Exception as e:
        logger.error(f"Background scraping failed: {str(e)}")
        # Update status to failed
        execute_query(
            "UPDATE sitemap_sources SET status = 'failed' WHERE id = %s",
            (sitemap_id,)
        )

@app.get("/api/scraping-status/{sitemap_id}")
async def get_scraping_status(sitemap_id: int):
    """Get scraping status for a sitemap"""
    try:
        result = execute_query(
            """
            SELECT sitemap_url, domain, total_pages, scraped_pages, failed_pages, 
                   status, last_scraped, created_at
            FROM sitemap_sources 
            WHERE id = %s
            """,
            (sitemap_id,),
            fetch='one'
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Sitemap not found")
        
        return {
            "sitemap_id": sitemap_id,
            "sitemap_url": result['sitemap_url'],
            "domain": result['domain'],
            "total_pages": result['total_pages'] or 0,
            "scraped_pages": result['scraped_pages'] or 0,
            "failed_pages": result['failed_pages'] or 0,
            "status": result['status'],
            "last_scraped": result['last_scraped'].isoformat() if result['last_scraped'] else None,
            "created_at": result['created_at'].isoformat() if result['created_at'] else None
        }
        
    except Exception as e:
        logger.error(f"Error getting scraping status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """
    Process chat request using Gemini AI with scraped content
    """
    start_time = datetime.now()
    
    # Initialize entity extraction structure at function start (proper scope)
    all_extracted_entities = {
        'people': [],
        'companies': [],
        'roles': [],
        'timeline': [],
        'skills': [],
        'locations': [],
        'projects': [],
        'achievements': [],
        'contact_info': [],
        'other_entities': []
    }

    def _filter_and_format_response(raw_answer: str, question: str, is_timeline: bool, is_job_title: bool, is_company: bool, is_skill: bool) -> str:
        """Smart response filtering with strict 300-500 character limit and enhanced formatting"""
        import re

        if not raw_answer:
            return f"I don't have specific information about '{question}' in the available content. Ask me about other topics from the website."

        # --- SMART CLEANING: Remove markdown and formatting while preserving content ---
        cleaned_answer = raw_answer.strip()
        
        # Remove markdown formatting but keep content
        cleaned_answer = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned_answer)  # **bold**
        cleaned_answer = re.sub(r'\*([^*]+)\*', r'\1', cleaned_answer)  # *italic*
        cleaned_answer = re.sub(r'_([^_]+)_', r'\1', cleaned_answer)  # _italic_
        cleaned_answer = re.sub(r'~~([^~]+)~~', r'\1', cleaned_answer)  # ~~strikethrough~~
        
        # Remove code blocks and inline code
        cleaned_answer = re.sub(r'```[\s\S]*?```', '', cleaned_answer)
        cleaned_answer = re.sub(r'`([^`]+)`', r'\1', cleaned_answer)

        # Remove headings but keep the text
        cleaned_answer = re.sub(r'^\s*#+\s*', '', cleaned_answer, flags=re.MULTILINE)

        # Remove horizontal rules
        cleaned_answer = re.sub(r'^\s*[-*_]{3,}\s*$', '', cleaned_answer, flags=re.MULTILINE)

        # Remove blockquotes but keep content
        cleaned_answer = re.sub(r'^\s*>\s*', '', cleaned_answer, flags=re.MULTILINE)

        # Convert list markers to bullet points for better readability
        cleaned_answer = re.sub(r'^\s*[\*\-+]\s+', '• ', cleaned_answer, flags=re.MULTILINE)
        cleaned_answer = re.sub(r'^\s*\d+\.\s+', '• ', cleaned_answer, flags=re.MULTILINE)

        # Clean up spacing
        cleaned_answer = re.sub(r'\n{2,}', ' ', cleaned_answer)  # Replace multiple newlines with space
        cleaned_answer = re.sub(r' {2,}', ' ', cleaned_answer)  # Replace multiple spaces
        cleaned_answer = cleaned_answer.strip()
        
        raw_answer = cleaned_answer
        # ----------------------------------------------------------------

        # SMART LENGTH ENFORCEMENT: Strict 300-500 character limit
        current_length = len(raw_answer)
        
        # If already perfect length, return as-is
        if 300 <= current_length <= 500:
            return raw_answer

        # If too short, pad with helpful context or return as-is
        if current_length < 300:
            if current_length < 100:  # Very short responses need padding
                padding = " For more specific information, please ask about particular aspects of the available content."
                if len(raw_answer + padding) <= 500:
                    return raw_answer + padding
            return raw_answer

        # If too long, apply SMART TRUNCATION with priority preservation
        # Split into sentences for better truncation
        sentences = re.split(r'[.!?]+', raw_answer)
        
        # Smart sentence prioritization based on question type
        priority_sentences = []
        regular_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short fragments
                continue
                
            # Check if sentence contains high-priority information
            is_priority = False
            if is_timeline and re.search(r'\b(19|20)\d{2}|present|current|experience|years?\b', sentence, re.IGNORECASE):
                is_priority = True
            elif is_job_title and re.search(r'\b(director|manager|founder|co-founder|lead|senior|ceo|cto)\b', sentence, re.IGNORECASE):
                is_priority = True
            elif is_company and re.search(r'\b(tech|services|management|digital|company|organization)\b', sentence, re.IGNORECASE):
                is_priority = True
            elif is_skill and re.search(r'\b(skill|expertise|specializ|focus|technology|development)\b', sentence, re.IGNORECASE):
                is_priority = True
            elif re.search(r'\b(key|main|primary|important|significant|founded|established)\b', sentence, re.IGNORECASE):
                is_priority = True
                
            if is_priority:
                priority_sentences.append(sentence)
            else:
                regular_sentences.append(sentence)
        
        # Build optimized response within 300-500 character limit
        result_parts = []
        char_count = 0
        target_max = 480  # Leave room for potential ellipsis
        
        # Add priority sentences first
        for sentence in priority_sentences:
            sentence_with_period = sentence.rstrip('.!?') + '.'
            if char_count + len(sentence_with_period) + 1 <= target_max:
                result_parts.append(sentence_with_period)
                char_count += len(sentence_with_period) + 1
            elif char_count < 300:  # If we haven't reached minimum, try to fit partial
                remaining_chars = target_max - char_count - 4  # Leave room for "..."
                if remaining_chars > 50:  # Only if we have meaningful space
                    partial = sentence[:remaining_chars].rstrip() + '...'
                    result_parts.append(partial)
                    char_count += len(partial)
                break
        
        # Add regular sentences if we have space and haven't reached minimum
        if char_count < 350:  # Try to get closer to optimal length
            for sentence in regular_sentences:
                sentence_with_period = sentence.rstrip('.!?') + '.'
                if char_count + len(sentence_with_period) + 1 <= target_max:
                    result_parts.append(sentence_with_period)
                    char_count += len(sentence_with_period) + 1
                    if char_count >= 400:  # Good length reached
                        break
                else:
                    break
        
        result = ' '.join(result_parts).strip()
        
        # Final enforcement: Ensure we're within 300-500 range
        if len(result) > 500:
            result = result[:497] + '...'
        elif len(result) < 300:
            # If still too short, add a helpful suffix
            suffix = " Ask for more specific details if needed."
            if len(result + suffix) <= 500:
                result += suffix
        
        return result

    try:
        # Check if it's a basic greeting or conversational message
        question_lower = request.question.lower().strip()
        greeting_patterns = [
            'hi', 'hello', 'hey', 'hii', 'helo', 'hii there', 'hello there',
            'how are you', 'how r u', 'how are u', 'whats up', "what's up",
            'good morning', 'good afternoon', 'good evening', 'good night',
            'thanks', 'thank you', 'bye', 'goodbye', 'see you', 'nice to meet you'
        ]
        
        # Check for basic greetings
        is_greeting = any(pattern in question_lower for pattern in greeting_patterns)
        
        if is_greeting:
            # Handle basic conversational responses
            if any(word in question_lower for word in ['hi', 'hello', 'hey', 'hii', 'helo']):
                greeting_response = "Hello! I'm your AI assistant. I can help you find information from the scraped websites. What would you like to know?"
            elif any(word in question_lower for word in ['how are you', 'how r u', 'how are u']):
                greeting_response = "I'm doing great, thank you for asking! I'm here to help you with information from your scraped websites. How can I assist you today?"
            elif any(word in question_lower for word in ['whats up', "what's up"]):
                greeting_response = "Not much, just ready to help you find information from your scraped content! What can I help you with?"
            elif any(word in question_lower for word in ['thanks', 'thank you']):
                greeting_response = "You're welcome! I'm always here to help with questions about your scraped website content."
            elif any(word in question_lower for word in ['bye', 'goodbye', 'see you']):
                greeting_response = "Goodbye! Feel free to come back anytime if you have questions about your website content."
            elif any(word in question_lower for word in ['good morning', 'good afternoon', 'good evening']):
                greeting_response = "Good day to you too! I'm ready to help you with any questions about your scraped website content."
            else:
                greeting_response = "Hello! I'm here to help you find information from your scraped websites. What would you like to know?"
            
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ChatResponse(
                answer=greeting_response,
                source_urls=[],
                response_time_ms=response_time,
                context_found=False
            )
        
        # Only restrict clearly unrelated topics (much more permissive)
        highly_restricted_patterns = [
            'write code for', 'debug this code', 'fix this error', 'create a program',
            'solve this math equation', 'calculate the derivative', 'integrate this function',
            'recipe for cooking', 'how to cook', 'weather forecast', 'stock market',
            'current news', 'latest news', 'sports scores', 'movie reviews'
        ]
        
        is_highly_restricted = any(pattern in question_lower for pattern in highly_restricted_patterns)
        
        if is_highly_restricted:
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ChatResponse(
                answer="I specialize in helping with information from this website. For coding help, math problems, recipes, or current news, please use specialized tools. What can I help you find on this website?",
                source_urls=[],
                response_time_ms=response_time,
                context_found=False
            )
        
        # COMPREHENSIVE SEARCH - Analyze ALL stored content for structured data
        search_results = []
        
        # ENHANCED question type detection with comprehensive company identification patterns
        question_lower = request.question.lower()
        
        # Timeline/Experience questions
        is_timeline_question = any(word in question_lower for word in [
            'timeline', 'experience', 'career', 'history', 'when did', 'how long', 'years', 'since when',
            'worked', 'started', 'joined', 'founded', 'established', 'began', 'duration', 'period'
        ])
        
        # Job title/Position questions
        is_job_title_question = any(word in question_lower for word in [
            'job', 'title', 'position', 'role', 'designation', 'what does', 'works as', 'employed as',
            'director', 'manager', 'founder', 'ceo', 'lead', 'head', 'senior', 'junior', 'analyst'
        ])
        
        # ENHANCED Company/Organization questions with comprehensive patterns
        is_company_question = any([
            # Direct company keywords
            any(word in question_lower for word in [
                'company', 'companies', 'organization', 'business', 'firm', 'employer', 'workplace',
                'works at', 'works for', 'employed by', 'founded', 'owns', 'runs', 'manages'
            ]),
            # List-based queries
            any(phrase in question_lower for phrase in [
                'list company', 'list companies', 'give me company', 'show me company', 'tell me company',
                'company names', 'company list', 'all companies', 'what companies', 'which companies',
                'name of company', 'names of companies', 'business names', 'organization names'
            ]),
            # Specific company inquiry patterns (enhanced with extracted entities)
            any(phrase in question_lower for phrase in [
                'troika tech', 'troika management', 'troika plus', 'tts digital', 'tech services', 
                'management company', 'digital company', 'solutions company', 'consulting company', 'services company'
            ]),
            # Action-based company queries
            any(phrase in question_lower for phrase in [
                'companies he founded', 'companies he owns', 'companies he runs', 'companies he manages',
                'businesses he started', 'organizations he created', 'firms he established'
            ]),
            # Smart detection based on extracted entities
            len(all_extracted_entities['companies']) > 0
        ])
        
        # Skills/Expertise questions
        is_skill_question = any(word in question_lower for word in [
            'skill', 'skills', 'expertise', 'specialization', 'focus', 'area', 'responsibility',
            'good at', 'expert in', 'specializes', 'focuses on', 'experienced in', 'knowledge'
        ])
        
        try:
            comprehensive_results = db_manager.search_content(request.question, limit=8)
            search_results.extend(comprehensive_results)
            logger.info(f"Ultra-fast search found {len(comprehensive_results)} results for: {request.question}")
        except Exception as e:
            logger.error(f"Enhanced search failed, using fallback: {e}")
            # Fallback to original search if enhanced search fails
            comprehensive_results = execute_query(
                """
                SELECT url, title, content, meta_description, keywords,
                       MATCH(title, content, meta_description, keywords) 
                       AGAINST (%s IN NATURAL LANGUAGE MODE) as relevance_score
                FROM scraped_pages 
                WHERE status = 'scraped'
                AND (MATCH(title, content, meta_description, keywords) AGAINST (%s IN NATURAL LANGUAGE MODE)
                     OR title LIKE %s OR content LIKE %s OR meta_description LIKE %s)
                ORDER BY relevance_score DESC
                LIMIT 5
                """,
                (request.question, request.question, f'%{request.question}%', f'%{request.question}%', f'%{request.question}%'),
                fetch='all'
            ) or []
            search_results.extend(comprehensive_results)
        
        # Strategy 3: Keyword-based search for structured content
        if not search_results or len(search_results) < 2:
            import re
            # Extract meaningful keywords
            keywords = re.findall(r'\b\w{3,}\b', request.question.lower())
            stop_words = {'the', 'and', 'are', 'you', 'can', 'how', 'what', 'where', 'when', 'why', 'who', 'tell', 'show', 'give'}
            keywords = [k for k in keywords if k not in stop_words][:5]
            
            if keywords:
                # Build flexible search patterns
                keyword_patterns = []
                for keyword in keywords:
                    keyword_patterns.extend([
                        keyword,
                        f'{keyword}s',  # plural
                        f'{keyword}ed', # past tense
                        f'{keyword}ing' # present participle
                    ])
                
                keyword_pattern = '|'.join(keyword_patterns)
                
                fallback_results = execute_query(
                    """
                    SELECT url, title, content, meta_description, keywords
                    FROM scraped_pages 
                    WHERE (title REGEXP %s OR content REGEXP %s OR meta_description REGEXP %s OR keywords REGEXP %s)
                    AND status = 'scraped'
                    ORDER BY 
                        (CASE WHEN title REGEXP %s THEN 4 ELSE 0 END) +
                        (CASE WHEN meta_description REGEXP %s THEN 3 ELSE 0 END) +
                        (CASE WHEN keywords REGEXP %s THEN 2 ELSE 0 END) +
                        (CASE WHEN content REGEXP %s THEN 1 ELSE 0 END) DESC
                    LIMIT 3
                    """,
                    (keyword_pattern, keyword_pattern, keyword_pattern, keyword_pattern,
                     keyword_pattern, keyword_pattern, keyword_pattern, keyword_pattern),
                    fetch='all'
                ) or []
                search_results.extend(fallback_results)
        
        # Remove duplicates while preserving order
        seen_urls = set()
        unique_results = []
        for result in search_results:
            if result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                unique_results.append(result)
        search_results = unique_results[:5]  # Top 5 results for better context
        
        if search_results:
            context = "Website Information:\n"
            source_urls = []
            
            # SMART CONTENT ANALYSIS with entity extraction
            for result in search_results:
                url = result['url']
                title = result['title'] or 'Page'
                content = result['content'] or ''
                meta_desc = result.get('meta_description', '') or ''
                keywords = result.get('keywords', '') or ''
                source_urls.append(url)
                
                # Combine all available content for analysis
                full_content = f"{title} {meta_desc} {keywords} {content}"
                
                # Use Smart Content Analyzer to extract all entities
                analysis_result = smart_analyzer.analyze_content(full_content, request.question)
                
                # Merge extracted entities
                for entity_type in all_extracted_entities.keys():
                    if entity_type in analysis_result:
                        all_extracted_entities[entity_type].extend(analysis_result[entity_type])
                
                # Build context with both traditional and smart analysis
                context_parts = []
                if title:
                    context_parts.append(f"Title: {title}")
                if meta_desc:
                    context_parts.append(f"Description: {meta_desc}")
                if keywords:
                    context_parts.append(f"Keywords: {keywords}")
                
                # Add smart context from entity extraction
                smart_context = smart_analyzer.generate_smart_context(analysis_result, request.question)
                if smart_context:
                    context_parts.append(f"Smart Analysis: {smart_context}")
                
                # Include content with intelligent sizing
                if content:
                    # For structured content questions, include more content
                    if any([is_timeline_question, is_job_title_question, is_company_question, is_skill_question]):
                        content_excerpt = content[:2500]  # Even larger excerpt for smart analysis
                    else:
                        content_excerpt = content[:1000]   # Increased standard excerpt
                    context_parts.append(f"Content: {content_excerpt}")
                
                full_context = " | ".join(context_parts)
                context += f"• {full_context}\n\n"
            
            # Add comprehensive entity summary to context
            entity_summary = []
            
            # High-confidence companies
            high_conf_companies = [c['name'] for c in all_extracted_entities['companies'] if c.get('confidence', 0) > 0.7]
            if high_conf_companies:
                entity_summary.append(f"COMPANIES IDENTIFIED: {', '.join(set(high_conf_companies))}")
            
            # High-confidence people
            high_conf_people = [p['name'] for p in all_extracted_entities['people'] if p.get('confidence', 0) > 0.7]
            if high_conf_people:
                entity_summary.append(f"PEOPLE IDENTIFIED: {', '.join(set(high_conf_people))}")
            
            # High-confidence roles
            high_conf_roles = [r['title'] for r in all_extracted_entities['roles'] if r.get('confidence', 0) > 0.7]
            if high_conf_roles:
                entity_summary.append(f"ROLES IDENTIFIED: {', '.join(set(high_conf_roles))}")
            
            # Timeline information
            timeline_info = []
            for t in all_extracted_entities['timeline']:
                if t.get('confidence', 0) > 0.7:
                    if t.get('type') == 'year_range':
                        timeline_info.append(f"{t.get('start', '')}-{t.get('end', '')}")
                    elif t.get('type') == 'single_year':
                        timeline_info.append(t.get('year', ''))
            if timeline_info:
                entity_summary.append(f"TIMELINE IDENTIFIED: {', '.join(set(timeline_info))}")
            
            # Skills
            high_conf_skills = [s['name'] for s in all_extracted_entities['skills'] if s.get('confidence', 0) > 0.6]
            if high_conf_skills:
                entity_summary.append(f"SKILLS IDENTIFIED: {', '.join(set(high_conf_skills[:10]))}")
            
            if entity_summary:
                context += "\n=== SMART ENTITY EXTRACTION ===\n"
                context += "\n".join(entity_summary)
                context += "\n=== END SMART ANALYSIS ===\n\n"
            
            # INTELLIGENT RESPONSE GENERATION based on question type and comprehensive analysis
            
            # Determine specific response approach based on structured content detection
            if is_timeline_question:
                instruction = "Extract and present ALL timeline information, dates, years, experience periods, and career progression details. Look for patterns like '2012-PRESENT', '2014-2020', years, and date ranges. Present them chronologically."
            elif is_job_title_question:
                instruction = "Extract and list ALL job titles, positions, roles, and professional designations mentioned. Include current and past positions. Look for titles like 'Co-Founder', 'Director', 'Manager', etc."
            elif is_company_question:
                instruction = """COMPANY EXTRACTION EXPERT MODE:
                1. Extract ALL company names, organizations, businesses, and employers mentioned
                2. Look for these patterns:
                   • Words ending with: Services, Tech, Technologies, Management, Plus, Digital, Corp, Inc, Ltd, LLC, Group, Solutions, Systems, Company
                   • Proper nouns that appear to be business names (e.g., "Troika Tech Services", "Troika Management")
                   • Companies mentioned in context like "Founder of [Company]", "CEO of [Company]", "works at [Company]"
                   • Business names in ALL CAPS or Title Case
                3. Include current companies, past companies, founded companies, and managed companies
                4. Format as a clear list: "• Company Name 1 • Company Name 2 • Company Name 3"
                5. If multiple companies found, prioritize the most relevant ones first
                6. Look specifically for chunks that start with "Companies:" or "Company:" as these contain pre-extracted company data"""
            elif is_skill_question:
                instruction = "Extract and describe ALL skills, expertise areas, specializations, responsibilities, and professional focus areas mentioned. Include technical skills, business areas, and core competencies."
            elif any(word in question_lower for word in ['what is', 'what are', 'define', 'explain']):
                instruction = "Provide a comprehensive explanation using ALL available information. Include specific details, examples, and context from the website content."
            elif any(word in question_lower for word in ['how much', 'price', 'cost', 'fee', 'pricing']):
                instruction = "Focus on ALL pricing, costs, or fee information. Be specific with numbers, currency, and payment details."
            elif any(word in question_lower for word in ['when', 'time', 'hours', 'schedule', 'date']):
                instruction = "Provide ALL timing, schedule, date, and availability information. Include specific times, dates, and periods."
            elif any(word in question_lower for word in ['where', 'location', 'address', 'find']):
                instruction = "Provide ALL location, address, and geographical information. Be as specific as possible with addresses and directions."
            elif any(word in question_lower for word in ['how to', 'how do', 'how can', 'steps']):
                instruction = "Provide clear, detailed steps and instructions. Include all relevant procedures and processes."
            elif any(word in question_lower for word in ['who', 'contact', 'team', 'staff']):
                instruction = "Provide information about ALL people, contacts, team members, and staff mentioned. Include names, titles, and roles."
            elif any(word in question_lower for word in ['why', 'because', 'reason']):
                instruction = "Explain ALL reasoning, benefits, rationale, and explanations based on the website content."
            elif '?' in request.question:
                instruction = "Answer the question comprehensively using ALL available information. Be thorough and detailed."
            else:
                instruction = "Provide ALL helpful, relevant information based on the website content. Be comprehensive and detailed."
            
            # ULTRA-SMART AI PROMPT with comprehensive entity-aware analysis
            prompt = f"""ADVANCED AI CONTENT ANALYSIS WITH SMART ENTITY RECOGNITION:
{context}

QUESTION: {request.question}

TASK: {instruction}

INTELLIGENT ANALYSIS FRAMEWORK:
🧠 ENTITY-AWARE PROCESSING:
- Companies Detected: {len(all_extracted_entities['companies'])} entities
- People Detected: {len(all_extracted_entities['people'])} entities  
- Roles Detected: {len(all_extracted_entities['roles'])} entities
- Timeline Events: {len(all_extracted_entities['timeline'])} events
- Skills Identified: {len(all_extracted_entities['skills'])} skills

🎯 SMART RESPONSE STRATEGY:
1. PRIORITIZE extracted entities that directly match the question
2. For company questions: Use identified company names, not generic terms
3. For people questions: Reference specific names and roles found
4. For timeline questions: Use exact dates and periods identified
5. For skill questions: Reference specific technologies and expertise found
6. CROSS-REFERENCE entities with content for accurate context
7. AVOID generic responses - be specific using extracted data

📊 RESPONSE OPTIMIZATION:
✅ LENGTH: Exactly 300-500 characters (including spaces)
✅ SPECIFICITY: Use exact names, dates, and terms from entity extraction
✅ ACCURACY: Cross-validate entities with original content
✅ RELEVANCE: Prioritize entities most relevant to the question
✅ COMPLETENESS: Include all relevant extracted entities within limit
✅ INTELLIGENCE: Show understanding of relationships between entities

🚀 ADVANCED INSTRUCTIONS:
- If asking about companies: List specific company names found, not "various companies"
- If asking about people: Use actual names identified, not "the person"
- If asking about timeline: Use specific years/periods found, not "over time"
- If asking about skills: Reference actual technologies/skills identified
- ALWAYS prefer specific extracted entities over generic descriptions
- Combine related entities intelligently (e.g., "John Doe, Co-Founder of TTS Digital (2012-Present)")

If no relevant entities are found, respond: "I don't have specific information about [topic] in the available content. Ask me about other topics from the website."

Provide your intelligent, entity-aware response now:"""
        else:
            # Calculate response time for no-context case
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Enhanced no-results response with helpful suggestions
            helpful_response = f"""I couldn't find specific information about "{request.question}" in the website content I currently have access to.

Here are some suggestions:
• Try rephrasing your question with different keywords
• Ask about general topics like "experience", "background", "services", or "about"
• If asking about specific details, try broader questions first
• Make sure the website has been fully scraped and indexed

I'm here to help with any information that's available from the website content!"""
            
            return ChatResponse(
                answer=helpful_response,
                source_urls=[],
                response_time_ms=response_time,
                context_found=False
            )
        
        # Get response from Gemini with quota error handling
        try:
            response = model.generate_content(prompt)
            raw_answer = response.text
            
            # SMART REPLY FILTERING - Keep comprehensive search, filter response length
            answer = _filter_and_format_response(raw_answer, request.question, is_timeline_question, is_job_title_question, is_company_question, is_skill_question)
            
        except Exception as gemini_error:
            # Check if it's a quota exceeded error
            error_str = str(gemini_error)
            if "429" in error_str and "quota" in error_str.lower():
                response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                return ChatResponse(
                    answer="I'm currently experiencing high usage and my daily quota is over. I'll be back up and running soon. Please try again later!",
                    source_urls=[],
                    response_time_ms=response_time,
                    context_found=False
                )
            else:
                # For other Gemini API errors, re-raise
                raise gemini_error
        
        # Calculate response time
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Store chat history (optimized)
        execute_query(
            """
            INSERT INTO chat_history 
            (user_id, question, answer, source_url, context_used, response_time_ms)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                request.user_id,
                request.question[:500],  # Limit question length
                answer[:500],  # Store filtered answer
                source_urls[0] if source_urls else None,
                context[:1000] if context else None,  # Store more context for debugging
                response_time
            )
        )
        
        return ChatResponse(
            answer=answer,
            source_urls=source_urls,
            response_time_ms=response_time,
            context_found=len(search_results) > 0
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return ChatResponse(
            answer="I'm experiencing a technical issue. Please try your question again.",
            source_urls=[],
            response_time_ms=response_time,
            context_found=False
        )
        """Filter and format response to 300-500 characters while maintaining key information"""
        if not raw_answer:
            return "I couldn't find specific information to answer your question."
        
        # If already within range, return as-is
        if 300 <= len(raw_answer) <= 500:
            return raw_answer
        
        # If too short, return as-is
        if len(raw_answer) < 300:
            return raw_answer
        
        # If too long, apply intelligent filtering based on question type
        lines = raw_answer.split('\n')
        filtered_lines = []
        char_count = 0
        
        # Prioritize content based on question type
        if is_timeline:
            # For timeline questions, prioritize lines with dates/years
            priority_patterns = [r'\b(19|20)\d{2}\b', r'present', r'current', r'-', r'to']
        elif is_job_title:
            # For job title questions, prioritize lines with title keywords
            priority_patterns = [r'\b(director|manager|founder|lead|senior|junior|analyst|specialist|coordinator)\b']
        elif is_company:
            # For company questions, prioritize lines with company indicators
            priority_patterns = [r'\b[A-Z]{2,}\b', r'\b(inc|llc|corp|ltd|company|organization)\b']
        elif is_skill:
            # For skill questions, prioritize lines with skill keywords
            priority_patterns = [r'\b(skill|expertise|experience|specializ|focus|area|responsibility)\b']
        else:
            # General prioritization
            priority_patterns = [r'\b(key|main|primary|important|significant)\b']
        
        # Sort lines by priority (lines matching patterns first)
        import re
        priority_lines = []
        regular_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            is_priority = any(re.search(pattern, line, re.IGNORECASE) for pattern in priority_patterns)
            if is_priority:
                priority_lines.append(line)
            else:
                regular_lines.append(line)
        
        # Build response starting with priority content
        all_lines = priority_lines + regular_lines
        
        for line in all_lines:
            # Check if adding this line would exceed 500 chars
            if char_count + len(line) + 2 > 500:  # +2 for \n
                break
            
            filtered_lines.append(line)
            char_count += len(line) + 1  # +1 for space/newline
            
            # Stop if we've reached a good length (400+ chars)
            if char_count >= 400:
                break
        
        result = ' '.join(filtered_lines)
        
        # Ensure minimum length by adding ellipsis if needed
        if len(result) < 300 and len(raw_answer) > 500:
            # Try to get more content
            remaining_chars = 450 - len(result)
            if remaining_chars > 20:
                additional_content = raw_answer[len(result):len(result) + remaining_chars]
                result += ' ' + additional_content
        
        # Final length check and cleanup
        if len(result) > 500:
            result = result[:497] + '...'
        elif len(result) < 300 and '...' not in result:
            result += ' (More details available in the source content)'
        
        return result.strip()

@app.get("/api/stats")
async def get_system_stats():
    """Get system statistics for admin dashboard"""
    try:
        stats = {}
        
        # Total users
        result = execute_query("SELECT COUNT(*) as count FROM users", fetch='one')
        stats["total_users"] = result['count'] if result else 0
        
        # Total scraped pages
        result = execute_query("SELECT COUNT(*) as count FROM scraped_pages WHERE status = 'scraped'", fetch='one')
        stats["total_pages"] = result['count'] if result else 0
        
        # Total chat conversations
        result = execute_query("SELECT COUNT(*) as count FROM chat_history", fetch='one')
        stats["total_chats"] = result['count'] if result else 0
        
        # Active sitemap sources
        result = execute_query("SELECT COUNT(*) as count FROM sitemap_sources WHERE status = 'completed'", fetch='one')
        stats["active_sitemaps"] = result['count'] if result else 0
        
        # Recent activity (last 24 hours)
        result = execute_query(
            "SELECT COUNT(*) as count FROM chat_history WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)",
            fetch='one'
        )
        stats["recent_chats"] = result['count'] if result else 0
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PYTHON_API_PORT", 8000)),
        reload=True,
        log_level="info"
    )
