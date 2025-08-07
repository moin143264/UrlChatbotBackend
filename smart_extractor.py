"""
Smart Entity and Information Extraction System
Advanced AI-powered content analysis for comprehensive information extraction
"""

import re
import json
from typing import List, Dict, Set, Tuple, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SmartContentAnalyzer:
    """
    Advanced content analyzer that intelligently extracts all types of entities and information
    from scraped web content including people, companies, roles, timelines, skills, etc.
    """
    
    def __init__(self):
        self.initialize_patterns()
        
    def initialize_patterns(self):
        """Initialize all detection patterns and rules"""
        
        # PERSON NAME PATTERNS
        self.person_indicators = {
            'titles': ['mr', 'mrs', 'ms', 'dr', 'prof', 'sir', 'madam'],
            'patterns': [
                r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # First Last
                r'\b[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\b',  # First M. Last
            ]
        }
        
        # COMPANY/ORGANIZATION PATTERNS
        self.company_patterns = {
            'suffixes': {
                'services', 'tech', 'technologies', 'management', 'plus', 'digital',
                'corp', 'corporation', 'inc', 'incorporated', 'ltd', 'limited',
                'llc', 'group', 'solutions', 'systems', 'company', 'co', 'enterprises',
                'consulting', 'consultancy', 'agency', 'studio', 'labs', 'works',
                'partners', 'associates', 'holdings', 'ventures', 'capital', 'media',
                'communications', 'marketing', 'advertising', 'design', 'development'
            },
            'prefixes': {
                'the', 'a', 'an'
            },
            'context_words': {
                'founded', 'established', 'started', 'launched', 'created', 'owns',
                'runs', 'manages', 'works at', 'works for', 'employed by', 'joined',
                'company', 'organization', 'business', 'firm', 'employer', 'workplace'
            }
        }
        
        # JOB TITLE/ROLE PATTERNS
        self.role_patterns = {
            'executive': {
                'ceo', 'chief executive officer', 'cto', 'chief technology officer',
                'cfo', 'chief financial officer', 'coo', 'chief operating officer',
                'president', 'vice president', 'vp', 'executive director'
            },
            'leadership': {
                'founder', 'co-founder', 'director', 'managing director', 'head',
                'lead', 'team lead', 'manager', 'senior manager', 'general manager',
                'project manager', 'product manager', 'program manager'
            },
            'technical': {
                'developer', 'engineer', 'software engineer', 'senior developer',
                'lead developer', 'architect', 'technical lead', 'tech lead',
                'analyst', 'consultant', 'specialist', 'expert', 'advisor'
            },
            'business': {
                'strategist', 'consultant', 'advisor', 'coordinator', 'supervisor',
                'administrator', 'executive', 'officer', 'representative', 'agent'
            }
        }
        
        # TIMELINE/DATE PATTERNS
        self.timeline_patterns = {
            'year_ranges': [
                r'\b(19|20)\d{2}\s*[-–—]\s*(present|current|now|\d{4})\b',
                r'\b(19|20)\d{2}\s*[-–—]\s*(19|20)\d{2}\b'
            ],
            'single_years': [
                r'\b(19|20)\d{2}\b'
            ],
            'date_formats': [
                r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(19|20)\d{2}\b',
                r'\b\d{1,2}[/\-]\d{1,2}[/\-](19|20)\d{2}\b',
                r'\b(19|20)\d{2}[/\-]\d{1,2}[/\-]\d{1,2}\b'
            ],
            'duration_words': {
                'years', 'months', 'weeks', 'days', 'experience', 'since', 'until',
                'from', 'to', 'during', 'between', 'over', 'more than', 'less than'
            }
        }
        
        # SKILL/TECHNOLOGY PATTERNS
        self.skill_patterns = {
            'programming': {
                'python', 'javascript', 'java', 'c++', 'c#', 'php', 'ruby', 'go',
                'swift', 'kotlin', 'typescript', 'scala', 'rust', 'html', 'css',
                'sql', 'nosql', 'mongodb', 'mysql', 'postgresql', 'redis'
            },
            'frameworks': {
                'react', 'angular', 'vue', 'django', 'flask', 'spring', 'laravel',
                'express', 'fastapi', 'bootstrap', 'tailwind', 'jquery', 'node.js'
            },
            'tools': {
                'git', 'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'jenkins',
                'gitlab', 'github', 'jira', 'confluence', 'slack', 'teams'
            },
            'business_skills': {
                'management', 'leadership', 'strategy', 'planning', 'analysis',
                'marketing', 'sales', 'consulting', 'project management',
                'business development', 'operations', 'finance', 'accounting'
            }
        }
        
        # LOCATION PATTERNS
        self.location_patterns = {
            'indicators': ['located', 'based', 'headquarters', 'office', 'address'],
            'formats': [
                r'\b[A-Z][a-z]+,\s*[A-Z][a-z]+\b',  # City, State
                r'\b[A-Z][a-z]+,\s*[A-Z]{2}\b',     # City, ST
                r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)'
            ]
        }

    def analyze_content(self, content: str, question: str = "") -> Dict[str, Any]:
        """
        Comprehensive content analysis to extract all relevant entities and information
        """
        analysis_result = {
            'people': [],
            'companies': [],
            'roles': [],
            'timeline': [],
            'skills': [],
            'locations': [],
            'projects': [],
            'achievements': [],
            'contact_info': [],
            'other_entities': [],
            'structured_data': {},
            'confidence_score': 0.0
        }
        
        # Analyze different types of entities
        analysis_result['people'] = self._extract_people(content)
        analysis_result['companies'] = self._extract_companies(content)
        analysis_result['roles'] = self._extract_roles(content)
        analysis_result['timeline'] = self._extract_timeline_info(content)
        analysis_result['skills'] = self._extract_skills(content)
        analysis_result['locations'] = self._extract_locations(content)
        analysis_result['projects'] = self._extract_projects(content)
        analysis_result['achievements'] = self._extract_achievements(content)
        analysis_result['contact_info'] = self._extract_contact_info(content)
        analysis_result['other_entities'] = self._extract_other_entities(content)
        analysis_result['structured_data'] = self._extract_structured_data(content)
        
        # Calculate overall confidence score
        analysis_result['confidence_score'] = self._calculate_confidence(analysis_result)
        
        # If a specific question is provided, prioritize relevant entities
        if question:
            analysis_result = self._prioritize_for_question(analysis_result, question)
        
        return analysis_result

    def _extract_people(self, content: str) -> List[Dict[str, Any]]:
        """Extract person names and related information"""
        people = []
        
        # Pattern 1: Names with titles
        for title in self.person_indicators['titles']:
            pattern = rf'\b{title}\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                people.append({
                    'name': match,
                    'title': title,
                    'confidence': 0.9,
                    'context': f"Found with title: {title}"
                })
        
        # Pattern 2: Proper names in professional context
        professional_contexts = [
            r'founded by ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'created by ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'developed by ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*) is (?:a|an|the) (?:founder|director|manager|ceo)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*) founded',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*) established'
        ]
        
        for pattern in professional_contexts:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(match.split()) <= 3:  # Reasonable name length
                    people.append({
                        'name': match,
                        'confidence': 0.8,
                        'context': "Found in professional context"
                    })
        
        return self._deduplicate_entities(people, 'name')

    def _extract_companies(self, content: str) -> List[Dict[str, Any]]:
        """Extract company/organization names"""
        companies = []
        
        # Pattern 1: Names with business suffixes
        suffix_pattern = r'\b([A-Z][A-Za-z\s&]+?)\s+(' + '|'.join(self.company_patterns['suffixes']) + r')\b'
        matches = re.findall(suffix_pattern, content, re.IGNORECASE)
        
        for match in matches:
            company_base, suffix = match
            company_name = f"{company_base.strip()} {suffix.strip()}"
            companies.append({
                'name': self._clean_entity_name(company_name),
                'type': 'business_suffix',
                'confidence': 0.85,
                'context': f"Found with business suffix: {suffix}"
            })
        
        # Pattern 2: Companies in job context
        job_context_patterns = [
            r'(?:co-founder|founder|director|manager|ceo|cto|head|lead)\s+(?:at|of|for)\s+([A-Z][A-Za-z\s&]+?)(?:\s|$|,|\.|;)',
            r'works (?:at|for)\s+([A-Z][A-Za-z\s&]+?)(?:\s|$|,|\.|;)',
            r'employed (?:by|at)\s+([A-Z][A-Za-z\s&]+?)(?:\s|$|,|\.|;)',
            r'joined\s+([A-Z][A-Za-z\s&]+?)(?:\s|$|,|\.|;)'
        ]
        
        for pattern in job_context_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                company_name = self._clean_entity_name(match)
                if len(company_name) > 2:
                    companies.append({
                        'name': company_name,
                        'type': 'job_context',
                        'confidence': 0.8,
                        'context': "Found in job/role context"
                    })
        
        # Pattern 3: Timeline company extraction
        timeline_pattern = r'(\d{4})\s*[-–—]\s*(?:present|current|\d{4})\s+[^-\n]*?[-–—]\s*([A-Z][A-Za-z\s&]+?)(?:\s|$|,|\.|;)'
        matches = re.findall(timeline_pattern, content, re.IGNORECASE)
        
        for match in matches:
            year, company_text = match
            company_name = self._clean_entity_name(company_text)
            if len(company_name) > 2:
                companies.append({
                    'name': company_name,
                    'type': 'timeline',
                    'confidence': 0.9,
                    'context': f"Found in timeline starting {year}"
                })
        
        return self._deduplicate_entities(companies, 'name')

    def _extract_roles(self, content: str) -> List[Dict[str, Any]]:
        """Extract job titles and professional roles"""
        roles = []
        
        # Combine all role categories
        all_roles = set()
        for category in self.role_patterns.values():
            all_roles.update(category)
        
        for role in all_roles:
            # Look for the role in various contexts
            patterns = [
                rf'\b{re.escape(role)}\b',
                rf'\b{re.escape(role)}s?\b',  # plural
                rf'\b(?:senior|lead|junior|assistant)\s+{re.escape(role)}\b'
            ]
            
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Determine role category
                    category = 'general'
                    for cat_name, cat_roles in self.role_patterns.items():
                        if role in cat_roles:
                            category = cat_name
                            break
                    
                    roles.append({
                        'title': role,
                        'category': category,
                        'confidence': 0.8,
                        'context': f"Found as {category} role"
                    })
        
        return self._deduplicate_entities(roles, 'title')

    def _extract_timeline_info(self, content: str) -> List[Dict[str, Any]]:
        """Extract timeline, dates, and experience information"""
        timeline_info = []
        
        # Year ranges
        for pattern in self.timeline_patterns['year_ranges']:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                start_year, end_period = match
                timeline_info.append({
                    'type': 'year_range',
                    'start': start_year,
                    'end': end_period,
                    'confidence': 0.9,
                    'context': f"Experience period: {start_year}-{end_period}"
                })
        
        # Single years
        for pattern in self.timeline_patterns['single_years']:
            matches = re.findall(pattern, content)
            for match in matches:
                timeline_info.append({
                    'type': 'single_year',
                    'year': match,
                    'confidence': 0.7,
                    'context': f"Mentioned year: {match}"
                })
        
        # Date formats
        for pattern in self.timeline_patterns['date_formats']:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    date_str = ' '.join(str(m) for m in match if m)
                else:
                    date_str = str(match)
                
                timeline_info.append({
                    'type': 'formatted_date',
                    'date': date_str,
                    'confidence': 0.8,
                    'context': f"Formatted date: {date_str}"
                })
        
        return timeline_info

    def _extract_skills(self, content: str) -> List[Dict[str, Any]]:
        """Extract skills, technologies, and expertise"""
        skills = []
        content_lower = content.lower()
        
        # Check all skill categories
        for category, skill_set in self.skill_patterns.items():
            for skill in skill_set:
                if skill.lower() in content_lower:
                    skills.append({
                        'name': skill,
                        'category': category,
                        'confidence': 0.7,
                        'context': f"Found {category} skill: {skill}"
                    })
        
        # Look for skill-related phrases
        skill_phrases = [
            r'skilled in ([^,.]+)',
            r'expertise in ([^,.]+)',
            r'specializes in ([^,.]+)',
            r'experienced with ([^,.]+)',
            r'proficient in ([^,.]+)'
        ]
        
        for pattern in skill_phrases:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                skills.append({
                    'name': match.strip(),
                    'category': 'mentioned_skill',
                    'confidence': 0.8,
                    'context': f"Explicitly mentioned skill: {match}"
                })
        
        return self._deduplicate_entities(skills, 'name')

    def _extract_locations(self, content: str) -> List[Dict[str, Any]]:
        """Extract location information"""
        locations = []
        
        # Location indicators
        for indicator in self.location_patterns['indicators']:
            pattern = rf'{indicator}\s+(?:in|at)?\s*([A-Z][A-Za-z\s,]+?)(?:\s|$|,|\.|;)'
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                locations.append({
                    'name': match.strip(),
                    'type': 'indicated_location',
                    'confidence': 0.8,
                    'context': f"Found with indicator: {indicator}"
                })
        
        # Address formats
        for pattern in self.location_patterns['formats']:
            matches = re.findall(pattern, content)
            for match in matches:
                locations.append({
                    'name': match,
                    'type': 'formatted_address',
                    'confidence': 0.9,
                    'context': "Formatted address pattern"
                })
        
        return self._deduplicate_entities(locations, 'name')

    def _extract_projects(self, content: str) -> List[Dict[str, Any]]:
        """Extract project and work information"""
        projects = []
        
        project_indicators = [
            'project', 'developed', 'created', 'built', 'launched', 'implemented',
            'designed', 'worked on', 'contributed to', 'led', 'managed'
        ]
        
        for indicator in project_indicators:
            pattern = rf'{indicator}\s+([A-Z][A-Za-z\s]+?)(?:\s|$|,|\.|;)'
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(match.strip()) > 3:
                    projects.append({
                        'name': match.strip(),
                        'indicator': indicator,
                        'confidence': 0.6,
                        'context': f"Found with indicator: {indicator}"
                    })
        
        return self._deduplicate_entities(projects, 'name')

    def _extract_achievements(self, content: str) -> List[Dict[str, Any]]:
        """Extract achievements and accomplishments"""
        achievements = []
        
        achievement_indicators = [
            'achieved', 'accomplished', 'awarded', 'recognized', 'honored',
            'certified', 'graduated', 'completed', 'successful', 'winner'
        ]
        
        for indicator in achievement_indicators:
            pattern = rf'{indicator}\s+([^,.]+?)(?:\s|$|,|\.|;)'
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(match.strip()) > 5:
                    achievements.append({
                        'description': match.strip(),
                        'indicator': indicator,
                        'confidence': 0.7,
                        'context': f"Achievement with indicator: {indicator}"
                    })
        
        return achievements

    def _extract_contact_info(self, content: str) -> List[Dict[str, Any]]:
        """Extract contact information"""
        contact_info = []
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        for email in emails:
            contact_info.append({
                'type': 'email',
                'value': email,
                'confidence': 0.95
            })
        
        # Phone pattern
        phone_pattern = r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, content)
        for phone in phones:
            contact_info.append({
                'type': 'phone',
                'value': phone,
                'confidence': 0.9
            })
        
        # Website pattern
        website_pattern = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+\.[a-z]{2,}'
        websites = re.findall(website_pattern, content, re.IGNORECASE)
        for website in websites:
            contact_info.append({
                'type': 'website',
                'value': website,
                'confidence': 0.8
            })
        
        return contact_info

    def _extract_other_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract other relevant entities not covered by specific categories"""
        other_entities = []
        
        # Numbers and statistics
        number_patterns = [
            r'\b\d+(?:,\d{3})*\+?\s*(?:users|clients|customers|employees|years|months)\b',
            r'\b\$\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:million|billion|thousand)?\b',
            r'\b\d+%\s*(?:growth|increase|improvement|success)\b'
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                other_entities.append({
                    'type': 'statistic',
                    'value': match,
                    'confidence': 0.8,
                    'context': "Numerical statistic or metric"
                })
        
        return other_entities

    def _extract_structured_data(self, content: str) -> Dict[str, Any]:
        """Extract structured data like JSON-LD, meta information"""
        structured_data = {}
        
        # Look for JSON-LD data
        json_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        json_matches = re.findall(json_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for match in json_matches:
            try:
                json_data = json.loads(match)
                structured_data['json_ld'] = json_data
            except:
                pass
        
        # Look for meta tags
        meta_pattern = r'<meta[^>]*name=["\']([^"\']+)["\'][^>]*content=["\']([^"\']+)["\'][^>]*>'
        meta_matches = re.findall(meta_pattern, content, re.IGNORECASE)
        
        meta_data = {}
        for name, content_val in meta_matches:
            meta_data[name] = content_val
        
        if meta_data:
            structured_data['meta_tags'] = meta_data
        
        return structured_data

    def _clean_entity_name(self, name: str) -> str:
        """Clean and normalize entity names"""
        if not name:
            return ""
        
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Remove common prefixes/suffixes that aren't part of the name
        prefixes_to_remove = ['the ', 'a ', 'an ']
        for prefix in prefixes_to_remove:
            if name.lower().startswith(prefix):
                name = name[len(prefix):]
        
        # Remove trailing punctuation
        name = name.rstrip('.,;:!?')
        
        return name.strip()

    def _deduplicate_entities(self, entities: List[Dict], key: str) -> List[Dict]:
        """Remove duplicate entities based on a key"""
        seen = set()
        unique_entities = []
        
        for entity in entities:
            entity_key = entity.get(key, '').lower().strip()
            if entity_key and entity_key not in seen:
                seen.add(entity_key)
                unique_entities.append(entity)
        
        return unique_entities

    def _calculate_confidence(self, analysis_result: Dict[str, Any]) -> float:
        """Calculate overall confidence score for the analysis"""
        total_entities = 0
        total_confidence = 0.0
        
        for category, entities in analysis_result.items():
            if isinstance(entities, list) and category != 'structured_data':
                for entity in entities:
                    if isinstance(entity, dict) and 'confidence' in entity:
                        total_entities += 1
                        total_confidence += entity['confidence']
        
        return total_confidence / total_entities if total_entities > 0 else 0.0

    def _prioritize_for_question(self, analysis_result: Dict[str, Any], question: str) -> Dict[str, Any]:
        """Prioritize extracted entities based on the specific question asked"""
        question_lower = question.lower()
        
        # Determine question type and boost relevant categories
        if any(word in question_lower for word in ['company', 'companies', 'business', 'organization']):
            # Boost company confidence scores
            for company in analysis_result['companies']:
                company['confidence'] = min(1.0, company['confidence'] + 0.1)
        
        elif any(word in question_lower for word in ['who', 'person', 'people', 'name']):
            # Boost people confidence scores
            for person in analysis_result['people']:
                person['confidence'] = min(1.0, person['confidence'] + 0.1)
        
        elif any(word in question_lower for word in ['when', 'timeline', 'experience', 'years']):
            # Boost timeline confidence scores
            for timeline in analysis_result['timeline']:
                timeline['confidence'] = min(1.0, timeline['confidence'] + 0.1)
        
        elif any(word in question_lower for word in ['skill', 'technology', 'expertise']):
            # Boost skills confidence scores
            for skill in analysis_result['skills']:
                skill['confidence'] = min(1.0, skill['confidence'] + 0.1)
        
        return analysis_result

    def generate_smart_context(self, analysis_result: Dict[str, Any], question: str) -> str:
        """Generate intelligent context for AI response based on extracted entities"""
        context_parts = []
        
        # Add high-confidence entities first
        if analysis_result['people']:
            people_names = [p['name'] for p in analysis_result['people'] if p['confidence'] > 0.7]
            if people_names:
                context_parts.append(f"People: {', '.join(people_names)}")
        
        if analysis_result['companies']:
            company_names = [c['name'] for c in analysis_result['companies'] if c['confidence'] > 0.7]
            if company_names:
                context_parts.append(f"Companies: {', '.join(company_names)}")
        
        if analysis_result['roles']:
            role_titles = [r['title'] for r in analysis_result['roles'] if r['confidence'] > 0.7]
            if role_titles:
                context_parts.append(f"Roles: {', '.join(role_titles)}")
        
        if analysis_result['timeline']:
            timeline_info = []
            for t in analysis_result['timeline']:
                if t['confidence'] > 0.7:
                    if t['type'] == 'year_range':
                        timeline_info.append(f"{t['start']}-{t['end']}")
                    elif t['type'] == 'single_year':
                        timeline_info.append(t['year'])
            if timeline_info:
                context_parts.append(f"Timeline: {', '.join(timeline_info)}")
        
        if analysis_result['skills']:
            skill_names = [s['name'] for s in analysis_result['skills'] if s['confidence'] > 0.7]
            if skill_names:
                context_parts.append(f"Skills: {', '.join(skill_names[:10])}")  # Limit to top 10
        
        if analysis_result['locations']:
            location_names = [l['name'] for l in analysis_result['locations'] if l['confidence'] > 0.7]
            if location_names:
                context_parts.append(f"Locations: {', '.join(location_names)}")
        
        return " | ".join(context_parts)
