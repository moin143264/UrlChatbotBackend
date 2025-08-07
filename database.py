"""
Database manager for hybrid chatbot system
Compatible with Python 3.13 and SQLAlchemy 2.x
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import pymysql

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database manager for handling all database operations"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=False, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.metadata = MetaData()
    
    def get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        """Execute a query and return results as list of dictionaries"""
        try:
            with self.get_session() as session:
                result = session.execute(text(query), params or {})
                
                if result.returns_rows:
                    columns = result.keys()
                    rows = result.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                else:
                    session.commit()
                    return []
                    
        except SQLAlchemyError as e:
            logger.error(f"Database query error: {e}")
            raise
    
    def insert_scraped_page(self, page_data: Dict[str, Any]) -> int:
        """Insert or update a scraped page with chunked content storage"""
        try:
            with self.get_session() as session:
                # First insert/update the main page record
                result = session.execute(
                    text("""
                        INSERT INTO scraped_pages 
                        (url, title, content, headings, image_url, meta_description, keywords, status)
                        VALUES (:url, :title, :content, :headings, :image_url, :meta_desc, :keywords, 'scraped')
                        ON DUPLICATE KEY UPDATE
                        title = VALUES(title),
                        content = VALUES(content),
                        headings = VALUES(headings),
                        image_url = VALUES(image_url),
                        meta_description = VALUES(meta_description),
                        keywords = VALUES(keywords),
                        status = 'scraped',
                        updated_at = NOW()
                    """),
                    {
                        "url": page_data["url"],
                        "title": page_data.get("title", ""),
                        "content": page_data.get("content", ""),
                        "headings": page_data.get("headings", ""),
                        "image_url": page_data.get("image_url", ""),
                        "meta_desc": page_data.get("meta_description", ""),
                        "keywords": page_data.get("keywords", "")
                    }
                )
                
                page_id = result.lastrowid or self._get_page_id_by_url(page_data["url"])
                
                # Now create content chunks for better searchability
                if page_data.get("content"):
                    self._create_content_chunks(session, page_id, page_data)
                
                session.commit()
                return page_id
                
        except SQLAlchemyError as e:
            logger.error(f"Error inserting scraped page: {e}")
            raise
    
    def _get_page_id_by_url(self, url: str) -> int:
        """Get page ID by URL"""
        try:
            result = self.execute_query(
                "SELECT id FROM scraped_pages WHERE url = :url",
                {"url": url}
            )
            return result[0]['id'] if result else 0
        except SQLAlchemyError:
            return 0
    
    def _create_content_chunks(self, session, page_id: int, page_data: Dict[str, Any]):
        """Create searchable content chunks from page data"""
        try:
            # Delete existing chunks for this page
            session.execute(
                text("DELETE FROM content_chunks WHERE page_id = :page_id"),
                {"page_id": page_id}
            )
            
            chunks = []
            content = page_data.get("content", "")
            title = page_data.get("title", "")
            headings = page_data.get("headings", "")
            
            # Create title chunk (highest priority)
            if title:
                chunks.append({
                    "chunk_text": title,
                    "chunk_type": "title",
                    "priority": 10
                })
            
            # Create heading chunks
            if headings:
                heading_lines = [h.strip() for h in headings.split('\n') if h.strip()]
                for heading in heading_lines:
                    chunks.append({
                        "chunk_text": heading,
                        "chunk_type": "heading",
                        "priority": 8
                    })
            
            # Create content chunks (split by sentences/paragraphs)
            if content:
                content_chunks = self._split_content_into_chunks(content)
                for i, chunk in enumerate(content_chunks):
                    chunks.append({
                        "chunk_text": chunk,
                        "chunk_type": "content",
                        "priority": 5,
                        "chunk_order": i
                    })
            
            # Insert all chunks
            for chunk in chunks:
                session.execute(
                    text("""
                        INSERT INTO content_chunks 
                        (page_id, chunk_text, chunk_type, priority, chunk_order, created_at)
                        VALUES (:page_id, :chunk_text, :chunk_type, :priority, :chunk_order, NOW())
                    """),
                    {
                        "page_id": page_id,
                        "chunk_text": chunk["chunk_text"],
                        "chunk_type": chunk["chunk_type"],
                        "priority": chunk["priority"],
                        "chunk_order": chunk.get("chunk_order", 0)
                    }
                )
                
        except SQLAlchemyError as e:
            logger.error(f"Error creating content chunks: {e}")
    
    def _split_content_into_chunks(self, content: str, max_chunk_size: int = 300) -> List[str]:
        """Split content into meaningful, searchable chunks"""
        if not content:
            return []
        
        chunks = []
        
        # Method 1: Split by common separators and patterns
        # Split by multiple line breaks, bullet points, years, etc.
        import re
        
        # First, split by major separators
        major_splits = re.split(r'\n\n+|\|\s*|\s*•\s*|\s*-\s*(?=\d{4})|\s*\d{4}\s*-\s*(?:Present|\d{4})', content)
        
        for section in major_splits:
            section = section.strip()
            if not section or len(section) < 10:  # Skip very short sections
                continue
                
            # If section is still too long, split by sentences
            if len(section) > max_chunk_size:
                # Split by sentences (periods, exclamation, question marks)
                sentences = re.split(r'[.!?]+\s+', section)
                current_chunk = ""
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                        
                    # If adding this sentence exceeds max size, save current chunk
                    if len(current_chunk + " " + sentence) > max_chunk_size and current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = sentence
                    else:
                        current_chunk += " " + sentence if current_chunk else sentence
                
                # Add remaining chunk
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
            else:
                # Section is small enough, add as is
                chunks.append(section)
        
        # Method 2: Extract specific patterns as separate chunks
        # Extract company names, people names, years, etc.
        
        # ENHANCED: Extract company names with comprehensive patterns
        companies = set()
        
        # Pattern 1: Business suffixes (most common)
        business_suffixes = r'\b([A-Z][a-zA-Z\s&.-]+(?:Services|Tech|Technologies|Management|Plus|Digital|One|Corp|Corporation|Inc|Incorporated|Ltd|Limited|LLC|Group|Solutions|Systems|Consulting|Associates|Partners|Enterprises|Holdings|Industries|Company|Co\.|Pvt|Private|Public|International|Global|Worldwide))\b'
        companies.update(re.findall(business_suffixes, content, re.IGNORECASE))
        
        # Pattern 2: "Founder of [Company]" or "CEO of [Company]"
        founder_pattern = r'(?:Founder|Co-Founder|CEO|Director|Owner|President)\s+(?:of|at)\s+([A-Z][a-zA-Z\s&.-]+(?:Services|Tech|Technologies|Management|Plus|Digital|One|Corp|Inc|Ltd|LLC|Group|Solutions|Systems|Company))'
        companies.update(re.findall(founder_pattern, content, re.IGNORECASE))
        
        # Pattern 3: "[Company] is a" or "[Company] provides"
        company_description = r'\b([A-Z][a-zA-Z\s&.-]{2,30})\s+(?:is a|provides|offers|specializes|focuses)'
        potential_companies = re.findall(company_description, content)
        # Filter to likely company names
        for comp in potential_companies:
            if any(word in comp.lower() for word in ['tech', 'service', 'solution', 'digital', 'management', 'group', 'company']):
                companies.add(comp.strip())
        
        # Pattern 4: Specific known patterns from content
        known_company_patterns = [
            r'\b(Troika\s+Tech\s+Services?)\b',
            r'\b(Troika\s+Management)\b', 
            r'\b(Troika\s+Plus)\b',
            r'\b([A-Z][a-zA-Z]+\s+Tech(?:nologies?)?)\b',
            r'\b([A-Z][a-zA-Z]+\s+Digital)\b',
            r'\b([A-Z][a-zA-Z]+\s+Solutions?)\b'
        ]
        
        for pattern in known_company_patterns:
            companies.update(re.findall(pattern, content, re.IGNORECASE))
        
        # Clean and filter companies
        if companies:
            # Remove common false positives and clean up
            filtered_companies = []
            for comp in companies:
                comp_clean = comp.strip()
                # Skip if too short, too long, or contains common false positive words
                if (5 <= len(comp_clean) <= 50 and 
                    not any(word in comp_clean.lower() for word in ['the', 'and', 'with', 'from', 'this', 'that', 'have', 'been', 'will', 'would', 'could', 'should']) and
                    not comp_clean.lower() in ['services', 'management', 'technology', 'digital', 'solutions']):
                    filtered_companies.append(comp_clean)
            
            if filtered_companies:
                # Create comprehensive company chunk
                unique_companies = list(set(filtered_companies))
                company_chunk = "Companies: " + ", ".join(unique_companies[:10])  # Limit to top 10
                chunks.append(company_chunk)
                
                # Also create individual company chunks for better search
                for company in unique_companies[:5]:  # Top 5 companies get individual chunks
                    individual_chunk = f"Company: {company}"
                    chunks.append(individual_chunk)
        
        # Extract people names (capitalized words that look like names)
        name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        names = re.findall(name_pattern, content)
        if names:
            # Filter out common false positives
            filtered_names = [name for name in set(names) if not any(word in name.lower() for word in ['april', 'standard', 'financial', 'chartered'])]
            if filtered_names:
                name_chunk = "People: " + ", ".join(filtered_names)
                chunks.append(name_chunk)
        
        # Extract years and experience
        year_pattern = r'\b(\d{4})\s*-\s*(Present|\d{4})\b'
        years = re.findall(year_pattern, content)
        if years:
            year_chunk = "Timeline: " + ", ".join([f"{start}-{end}" for start, end in years])
            chunks.append(year_chunk)
        
        # Remove duplicates and very short chunks
        final_chunks = []
        seen = set()
        for chunk in chunks:
            chunk_clean = chunk.strip()
            if len(chunk_clean) >= 15 and chunk_clean.lower() not in seen:
                seen.add(chunk_clean.lower())
                final_chunks.append(chunk_clean)
        
        return final_chunks
    
    def search_content(self, query: str, limit: int = 10) -> List[Dict]:
        """FIXED: Ultra-fast search with collation-safe queries and better chunk prioritization"""
        session = self.get_session()
        try:
            # STRATEGY 1: Prioritized chunk-based search (most accurate)
            chunk_query = text("""
                SELECT DISTINCT
                    sp.url, sp.title, sp.content, sp.headings, sp.meta_description,
                    GROUP_CONCAT(DISTINCT cc.chunk_text ORDER BY cc.priority DESC SEPARATOR ' | ') as matching_chunks,
                    (
                        -- Enhanced relevance scoring with chunk type weighting
                        (CASE WHEN cc.chunk_type = 'title' THEN 20 ELSE 0 END) +
                        (CASE WHEN cc.chunk_type = 'heading' THEN 15 ELSE 0 END) +
                        (CASE WHEN cc.chunk_type = 'content' THEN 10 ELSE 0 END) +
                        -- COMPANY DETECTION BOOST: Prioritize company-related chunks
                        (CASE WHEN cc.chunk_text LIKE 'Companies:%' THEN 30 ELSE 0 END) +
                        (CASE WHEN cc.chunk_text LIKE 'Company:%' THEN 25 ELSE 0 END) +
                        (CASE WHEN cc.chunk_text REGEXP '\\b(Services|Tech|Technologies|Management|Plus|Digital|Corp|Inc|Ltd|LLC|Group|Solutions|Systems|Company)\\b' THEN 15 ELSE 0 END) +
                        -- Boost exact matches heavily
                        (CASE WHEN cc.chunk_text LIKE CONCAT('%%', :exact_query, '%%') THEN 25 ELSE 0 END) +
                        -- Boost title matches in main page
                        (CASE WHEN sp.title LIKE CONCAT('%%', :exact_query, '%%') THEN 20 ELSE 0 END) +
                        -- Boost meta description matches
                        (CASE WHEN sp.meta_description LIKE CONCAT('%%', :exact_query, '%%') THEN 12 ELSE 0 END) +
                        -- Full-text search bonus
                        (CASE WHEN MATCH(cc.chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE) > 0 THEN 15 ELSE 0 END)
                    ) * COUNT(DISTINCT cc.id) as relevance_score,
                    'chunk' as search_type
                FROM content_chunks cc
                JOIN scraped_pages sp ON cc.page_id = sp.id
                WHERE (
                    -- Multi-strategy search for maximum coverage
                    cc.chunk_text LIKE CONCAT('%%', :exact_query, '%%') OR
                    MATCH(cc.chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE) OR
                    cc.chunk_text REGEXP :word_regex OR
                    sp.title LIKE CONCAT('%%', :exact_query, '%%') OR
                    sp.meta_description LIKE CONCAT('%%', :exact_query, '%%') OR
                    sp.headings LIKE CONCAT('%%', :exact_query, '%%')
                )
                AND sp.status = 'scraped'
                GROUP BY sp.id, sp.url, sp.title, sp.content, sp.headings, sp.meta_description
                HAVING relevance_score > 0
                ORDER BY relevance_score DESC
                LIMIT :limit
                """)
            
            # Execute chunk search first
            chunk_result = session.execute(chunk_query, {
                'exact_query': query,
                'query': query,
                'word_regex': '|'.join([word.strip() for word in query.split() if len(word.strip()) > 2]),
                'limit': limit
            })
            
            results = []
            found_urls = set()
            
            # Process chunk results
            for row in chunk_result:
                results.append({
                    'url': row.url,
                    'title': row.title,
                    'content': row.content,
                    'headings': row.headings,
                    'meta_description': row.meta_description,
                    'matching_chunks': row.matching_chunks,
                    'relevance_score': float(row.relevance_score),
                    'search_type': row.search_type
                })
                found_urls.add(row.url)
            
            # STRATEGY 2: Full-text fallback if we need more results
            if len(results) < limit:
                remaining_limit = limit - len(results)
                
                fulltext_query = text("""
                    SELECT DISTINCT
                        url, title, content, headings, meta_description,
                        CONCAT(SUBSTRING(content, 1, 200), '...') as matching_chunks,
                        MATCH(title, content, meta_description, keywords)
                        AGAINST(:query IN NATURAL LANGUAGE MODE) * 8 as relevance_score,
                        'fulltext' as search_type
                    FROM scraped_pages
                    WHERE MATCH(title, content, meta_description, keywords)
                    AGAINST(:query IN NATURAL LANGUAGE MODE)
                    AND status = 'scraped'
                    AND url NOT IN :found_urls
                    ORDER BY relevance_score DESC
                    LIMIT :remaining_limit
                    """)
                
                if found_urls:  # Only if we have URLs to exclude
                    fulltext_result = session.execute(fulltext_query, {
                        'query': query,
                        'found_urls': tuple(found_urls) if found_urls else ('',),
                        'remaining_limit': remaining_limit
                    })
                    
                    # Add fulltext results
                    for row in fulltext_result:
                        results.append({
                            'url': row.url,
                            'title': row.title,
                            'content': row.content,
                            'headings': row.headings,
                            'meta_description': row.meta_description,
                            'matching_chunks': row.matching_chunks,
                            'relevance_score': float(row.relevance_score),
                            'search_type': row.search_type
                        })
            
            # Sort final results by relevance
            results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            logger.info(f"FIXED search found {len(results)} results for: {query}")
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Database query error: {e}")
            # Emergency fallback to simple search
            try:
                fallback_query = text("""
                    SELECT DISTINCT
                        sp.url, sp.title, sp.content, sp.headings, sp.meta_description,
                        SUBSTRING(sp.content, 1, 200) as matching_chunks,
                        1 as relevance_score,
                        'fallback' as search_type
                    FROM scraped_pages sp
                    WHERE (sp.title LIKE :query OR sp.content LIKE :query OR sp.headings LIKE :query)
                    AND sp.status = 'scraped'
                    ORDER BY 
                        CASE WHEN sp.title LIKE :query THEN 3
                             WHEN sp.headings LIKE :query THEN 2
                             ELSE 1 END DESC
                    LIMIT :limit
                    """)
                
                fallback_result = session.execute(fallback_query, {
                    'query': f'%{query}%',
                    'limit': limit
                })
                
                fallback_results = []
                for row in fallback_result:
                    fallback_results.append({
                        'url': row.url,
                        'title': row.title,
                        'content': row.content,
                        'headings': row.headings,
                        'meta_description': row.meta_description,
                        'matching_chunks': row.matching_chunks,
                        'relevance_score': float(row.relevance_score),
                        'search_type': row.search_type
                    })
                
                logger.info(f"Fallback search found {len(fallback_results)} results")
                return fallback_results
            except Exception as fallback_error:
                logger.error(f"Fallback search also failed: {fallback_error}")
                return []
        finally:
            session.close()
    
    def _fulltext_search(self, query: str, limit: int) -> List[Dict]:
        """Full-text search using MySQL MATCH AGAINST"""
        try:
            return self.execute_query(
                """
                SELECT url, title, content, headings, meta_description,
                       MATCH(title, content, headings, meta_description, keywords) 
                       AGAINST (:query IN NATURAL LANGUAGE MODE) as relevance_score
                FROM scraped_pages 
                WHERE MATCH(title, content, headings, meta_description, keywords) 
                AGAINST (:query IN NATURAL LANGUAGE MODE)
                AND status = 'scraped'
                ORDER BY relevance_score DESC
                LIMIT :limit
                """,
                {"query": query, "limit": limit}
            )
        except SQLAlchemyError as e:
            logger.warning(f"Fulltext search failed: {e}")
            return []
    
    def _like_search(self, query: str, limit: int) -> List[Dict]:
        """LIKE-based search for better name and keyword matching"""
        try:
            # Split query into individual terms
            terms = query.lower().split()
            
            # Build dynamic WHERE clause for multiple terms
            where_conditions = []
            params = {"limit": limit}
            
            for i, term in enumerate(terms):
                param_name = f"term_{i}"
                params[param_name] = f"%{term}%"
                where_conditions.append(f"""
                    (LOWER(title) LIKE :{param_name} OR 
                     LOWER(content) LIKE :{param_name} OR 
                     LOWER(headings) LIKE :{param_name} OR 
                     LOWER(meta_description) LIKE :{param_name} OR 
                     LOWER(keywords) LIKE :{param_name})
                """)
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            query_sql = f"""
                SELECT url, title, content, headings, meta_description,
                       (
                           CASE WHEN LOWER(title) LIKE :term_0 THEN 10 ELSE 0 END +
                           CASE WHEN LOWER(content) LIKE :term_0 THEN 5 ELSE 0 END +
                           CASE WHEN LOWER(headings) LIKE :term_0 THEN 8 ELSE 0 END
                       ) as relevance_score
                FROM scraped_pages 
                WHERE {where_clause}
                AND status = 'scraped'
                ORDER BY relevance_score DESC, id DESC
                LIMIT :limit
            """
            
            return self.execute_query(query_sql, params)
            
        except SQLAlchemyError as e:
            logger.error(f"Like search failed: {e}")
            return []
    
    def _combine_search_results(self, fulltext_results: List[Dict], like_results: List[Dict], limit: int) -> List[Dict]:
        """Combine and deduplicate search results"""
        seen_urls = set()
        combined = []
        
        # Add fulltext results first (higher priority)
        for result in fulltext_results:
            if result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                combined.append(result)
        
        # Add like results that weren't already included
        for result in like_results:
            if result['url'] not in seen_urls and len(combined) < limit:
                seen_urls.add(result['url'])
                combined.append(result)
        
        return combined[:limit]
    
    def _search_chunks(self, query: str, limit: int) -> List[Dict]:
        """Search content chunks for more precise results"""
        try:
            # Split query into terms
            terms = query.lower().split()
            
            # Build search conditions for chunks
            where_conditions = []
            params = {"limit": limit}
            
            for i, term in enumerate(terms):
                param_name = f"term_{i}"
                params[param_name] = f"%{term}%"
                where_conditions.append(f"LOWER(cc.chunk_text) LIKE :{param_name}")
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            query_sql = f"""
                SELECT DISTINCT sp.url, sp.title, sp.content, sp.headings, sp.meta_description,
                       (
                           MAX(cc.priority) * 2 +
                           SUM(CASE WHEN cc.chunk_type = 'title' THEN 15 ELSE 0 END) +
                           SUM(CASE WHEN cc.chunk_type = 'heading' THEN 10 ELSE 0 END) +
                           SUM(CASE WHEN cc.chunk_type = 'content' THEN 5 ELSE 0 END)
                       ) as relevance_score,
                       GROUP_CONCAT(DISTINCT cc.chunk_text ORDER BY cc.priority DESC SEPARATOR ' | ') as matching_chunks
                FROM content_chunks cc
                JOIN scraped_pages sp ON cc.page_id = sp.id
                WHERE {where_clause}
                AND sp.status = 'scraped'
                GROUP BY sp.id, sp.url, sp.title, sp.content, sp.headings, sp.meta_description
                ORDER BY relevance_score DESC
                LIMIT :limit
            """
            
            return self.execute_query(query_sql, params)
            
        except SQLAlchemyError as e:
            logger.error(f"Chunk search failed: {e}")
            return []
    
    def _combine_all_search_results(self, chunk_results: List[Dict], fulltext_results: List[Dict], 
                                  like_results: List[Dict], limit: int) -> List[Dict]:
        """Combine results from all search methods with priority"""
        seen_urls = set()
        combined = []
        
        # Priority 1: Chunk results (most accurate)
        for result in chunk_results:
            if result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                combined.append(result)
        
        # Priority 2: Fulltext results
        for result in fulltext_results:
            if result['url'] not in seen_urls and len(combined) < limit:
                seen_urls.add(result['url'])
                combined.append(result)
        
        # Priority 3: Like results
        for result in like_results:
            if result['url'] not in seen_urls and len(combined) < limit:
                seen_urls.add(result['url'])
                combined.append(result)
        
        return combined[:limit]
    
    def insert_chat_history(self, user_id: int, question: str, answer: str, 
                          source_url: str = None, context_used: str = None, 
                          response_time_ms: int = 0) -> int:
        """Insert chat history record"""
        try:
            with self.get_session() as session:
                result = session.execute(
                    text("""
                        INSERT INTO chat_history 
                        (user_id, question, answer, source_url, context_used, response_time_ms)
                        VALUES (:user_id, :question, :answer, :source_url, :context, :response_time)
                    """),
                    {
                        "user_id": user_id,
                        "question": question,
                        "answer": answer,
                        "source_url": source_url,
                        "context": context_used,
                        "response_time": response_time_ms
                    }
                )
                session.commit()
                return result.lastrowid
                
        except SQLAlchemyError as e:
            logger.error(f"Error inserting chat history: {e}")
            raise
    
    def get_user_chat_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get chat history for a specific user"""
        try:
            return self.execute_query(
                """
                SELECT id, question, answer, source_url, timestamp
                FROM chat_history 
                WHERE user_id = :user_id
                ORDER BY timestamp DESC
                LIMIT :limit
                """,
                {"user_id": user_id, "limit": limit}
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting chat history: {e}")
            return []
    
    def get_system_stats(self) -> Dict[str, int]:
        """Get system statistics"""
        try:
            stats = {}
            
            # Get various counts
            queries = {
                "total_users": "SELECT COUNT(*) as count FROM users",
                "total_pages": "SELECT COUNT(*) as count FROM scraped_pages WHERE status = 'scraped'",
                "total_chats": "SELECT COUNT(*) as count FROM chat_history",
                "active_sitemaps": "SELECT COUNT(*) as count FROM sitemap_sources WHERE status = 'completed'",
                "recent_chats": "SELECT COUNT(*) as count FROM chat_history WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
            }
            
            for key, query in queries.items():
                result = self.execute_query(query)
                stats[key] = result[0]["count"] if result else 0
            
            return stats
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def create_sitemap_source(self, sitemap_url: str, domain: str, user_id: int) -> int:
        """Create a new sitemap source record"""
        try:
            with self.get_session() as session:
                result = session.execute(
                    text("""
                        INSERT INTO sitemap_sources (sitemap_url, domain, created_by, status) 
                        VALUES (:url, :domain, :user_id, 'pending')
                    """),
                    {"url": sitemap_url, "domain": domain, "user_id": user_id}
                )
                session.commit()
                return result.lastrowid
                
        except SQLAlchemyError as e:
            logger.error(f"Error creating sitemap source: {e}")
            raise
    
    def update_sitemap_status(self, sitemap_id: int, status: str, 
                            total_pages: int = None, scraped_pages: int = None, 
                            failed_pages: int = None) -> bool:
        """Update sitemap source status and counts"""
        try:
            with self.get_session() as session:
                update_parts = ["status = :status"]
                params = {"id": sitemap_id, "status": status}
                
                if total_pages is not None:
                    update_parts.append("total_pages = :total")
                    params["total"] = total_pages
                
                if scraped_pages is not None:
                    update_parts.append("scraped_pages = :scraped")
                    params["scraped"] = scraped_pages
                
                if failed_pages is not None:
                    update_parts.append("failed_pages = :failed")
                    params["failed"] = failed_pages
                
                if status == 'completed':
                    update_parts.append("last_scraped = NOW()")
                
                query = f"""
                    UPDATE sitemap_sources 
                    SET {', '.join(update_parts)}, updated_at = NOW()
                    WHERE id = :id
                """
                
                session.execute(text(query), params)
                session.commit()
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating sitemap status: {e}")
            return False
    
    def get_sitemap_status(self, sitemap_id: int) -> Optional[Dict]:
        """Get sitemap source status"""
        try:
            result = self.execute_query(
                """
                SELECT id, sitemap_url, domain, total_pages, scraped_pages, failed_pages, 
                       status, last_scraped, created_at, updated_at
                FROM sitemap_sources 
                WHERE id = :id
                """,
                {"id": sitemap_id}
            )
            return result[0] if result else None
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting sitemap status: {e}")
            return None
    
    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """Clean up old data (optional maintenance function)"""
        try:
            cleanup_stats = {}
            
            with self.get_session() as session:
                # Clean up old API logs
                result = session.execute(
                    text("DELETE FROM api_logs WHERE timestamp < DATE_SUB(NOW(), INTERVAL :days DAY)"),
                    {"days": days}
                )
                cleanup_stats["api_logs_deleted"] = result.rowcount
                
                # Clean up expired sessions
                result = session.execute(
                    text("DELETE FROM sessions WHERE expires_at < NOW()")
                )
                cleanup_stats["expired_sessions_deleted"] = result.rowcount
                
                session.commit()
            
            logger.info(f"Cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except SQLAlchemyError as e:
            logger.error(f"Error during cleanup: {e}")
            return {}
    
    def close(self):
        """Close database connections"""
        if hasattr(self, 'engine'):
            self.engine.dispose()
