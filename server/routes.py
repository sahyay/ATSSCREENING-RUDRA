from flask import Blueprint, request, jsonify, current_app
import os
import uuid
from werkzeug.utils import secure_filename
from bson import ObjectId
import tempfile
from datetime import datetime
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import docx2txt
import PyPDF2
import logging
import fitz  # PyMuPDF
import io
import traceback
from models import JobRole, ResumeResult

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('api', __name__, url_prefix='/api')

# Download NLTK resources
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except Exception as e:
    logger.error(f"Error downloading NLTK resources: {str(e)}")

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# Add this function at the top of the file, after the imports
def serialize_doc(doc):
    """Convert MongoDB document to serializable format"""
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    
    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
            elif isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                doc[key] = serialize_doc(value)
    return doc

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extract text from PDF file using multiple methods for better reliability"""
    text = ""
    
    # Method 1: PyMuPDF (primary method)
    try:
        logger.info(f"Attempting to extract text from PDF using PyMuPDF: {file_path}")
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            text += page_text
        
        logger.info(f"PyMuPDF extracted {len(text)} characters")
        if text.strip():
            return text
    except Exception as e:
        logger.error(f"PyMuPDF extraction failed: {str(e)}")
    
    # Method 2: PyPDF2 (fallback method)
    try:
        logger.info("Falling back to PyPDF2 extraction")
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        
        logger.info(f"PyPDF2 extracted {len(text)} characters")
        if text.strip():
            return text
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed: {str(e)}")
    
    # If both methods fail, log the error and return empty string
    if not text.strip():
        logger.error("All PDF extraction methods failed")
    
    return text

def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    try:
        logger.info(f"Extracting text from DOCX: {file_path}")
        text = docx2txt.process(file_path)
        logger.info(f"Extracted {len(text)} characters from DOCX")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {str(e)}")
        return ""

def extract_text(file_path):
    """Extract text from file based on extension"""
    logger.info(f"Extracting text from file: {file_path}")
    
    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    elif file_path.endswith('.docx'):
        text = extract_text_from_docx(file_path)
    else:
        text = ""
        logger.warning(f"Unsupported file type: {file_path}")
    
    # Log the first 100 characters of extracted text for debugging
    if text:
        preview = text[:100].replace('\n', ' ').strip()
        logger.info(f"Extracted text preview: {preview}...")
    else:
        logger.warning("No text extracted from file")
    
    return text

def extract_contact_info(text):
    """Extract contact information from text using simplified patterns"""
    if not text or len(text) < 10:
        logger.warning("Text too short for contact extraction")
        return None, None
    
    # Extract email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_matches = re.findall(email_pattern, text)
    email = email_matches[0] if email_matches else None
    
    # Extract phone number with simplified patterns
    phone = None
    
    # Simple pattern for international numbers with country code
    pattern1 = r'\+\d{1,3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{4}'
    matches = re.findall(pattern1, text)
    if matches:
        phone = matches[0]
    else:
        # Pattern for US numbers with parentheses
        pattern2 = r'$$\d{3}$$[-\s]?\d{3}[-\s]?\d{4}'
        matches = re.findall(pattern2, text)
        if matches:
            phone = matches[0]
        else:
            # Pattern for simple 10-digit numbers
            pattern3 = r'\b\d{10}\b'
            matches = re.findall(pattern3, text)
            if matches:
                phone = matches[0]
                # Format as (XXX) XXX-XXXX
                phone = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
    
    logger.info(f"Extracted contact info: Email: {email or 'Not found'}, Phone: {phone or 'Not found'}")
    return email, phone


def extract_name(text):
    """Extract name from resume text using improved heuristics"""
    if not text or len(text) < 10:
        logger.warning("Text too short for name extraction")
        return "Unknown"
    
    # Split text into lines and clean them
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Common name patterns
    name_patterns = [
        r'^[A-Z][a-z]+ [A-Z][a-z]+$',                      # First Last
        r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$',              # First M. Last
        r'^[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+$'           # First Middle Last
    ]
    
    # Look at the first few non-empty lines (typically name is at the top)
    for i in range(min(5, len(lines))):
        line = lines[i]
        
        # Skip lines that are too long or too short to be names
        if len(line) < 4 or len(line) > 40:
            continue
        
        # Skip lines that contain typical non-name elements
        if re.search(r'@|www|\d{3}|resume|cv|curriculum|vitae|address|email|phone|tel|contact', line.lower()):
            continue
        
        # Check if line matches common name patterns
        for pattern in name_patterns:
            if re.match(pattern, line):
                logger.info(f"Extracted name using pattern match: {line}")
                return line
        
        # If no pattern matches but line looks like a name (first few lines, reasonable length)
        # and contains at least two words with capitalization
        words = line.split()
        if (len(words) >= 2 and 
            all(word[0].isupper() for word in words if len(word) > 1) and
            not any(word.isupper() for word in words)):  # Avoid all caps lines
            logger.info(f"Extracted name using heuristic: {line}")
            return line
    
    logger.warning("Could not extract name with confidence")
    return "Unknown"

def extract_college(text):
    """Extract college/university name from text"""
    if not text or len(text) < 10:
        logger.warning("Text too short for education extraction")
        return None
    
    # List of common education keywords and degree types
    edu_keywords = [
        'university', 'college', 'institute', 'school', 'academy', 'polytechnic',
        'bachelor', 'master', 'phd', 'degree', 'b.tech', 'm.tech', 'b.e.', 'm.e.',
        'b.sc', 'm.sc', 'b.a.', 'm.a.', 'mba', 'bba', 'education'
    ]
    
    # Look for sections that might contain education information
    education_section = None
    sections = re.split(r'\n\s*\n', text.lower())
    
    for i, section in enumerate(sections):
        if any(keyword in section for keyword in ['education', 'academic', 'qualification', 'degree']):
            education_section = section
            break
    
    # If education section found, extract from there, otherwise search the whole text
    search_text = education_section if education_section else text.lower()
    
    # Look for lines containing education keywords
    lines = search_text.split('\n')
    for line in lines:
        if any(keyword in line.lower() for keyword in edu_keywords):
            # Extract the full line containing the education keyword
            result = line.strip()
            # Capitalize properly
            result = ' '.join(word.capitalize() for word in result.split())
            logger.info(f"Extracted education: {result}")
            return result
    
    logger.warning("No education information found")
    return None

def extract_skills(text):
    """Extract skills from resume text with improved matching"""
    if not text or len(text) < 10:
        logger.warning("Text too short for skills extraction")
        return []
    
    # Common technical skills - expanded list
    common_skills = [
        'python', 'java', 'javascript', 'html', 'css', 'react', 'angular', 'vue', 
        'node.js', 'express', 'django', 'flask', 'spring', 'hibernate', 'sql', 
        'mysql', 'postgresql', 'mongodb', 'nosql', 'aws', 'azure', 'gcp', 'docker', 
        'kubernetes', 'jenkins', 'git', 'github', 'gitlab', 'ci/cd', 'agile', 'scrum', 
        'jira', 'confluence', 'machine learning', 'deep learning', 'ai', 'data science', 
        'data analysis', 'tensorflow', 'pytorch', 'keras', 'pandas', 'numpy', 'scipy', 
        'matplotlib', 'tableau', 'power bi', 'excel', 'word', 'powerpoint', 'photoshop', 
        'illustrator', 'figma', 'sketch', 'ui/ux', 'responsive design', 'mobile development', 
        'ios', 'android', 'swift', 'kotlin', 'flutter', 'react native', 'c', 'c++', 'c#', 
        'php', 'ruby', 'rails', 'scala', 'go', 'rust', 'typescript', 'jquery', 'bootstrap', 
        'tailwind', 'sass', 'less', 'redux', 'graphql', 'rest api', 'soap', 'microservices', 
        'serverless', 'linux', 'unix', 'windows', 'macos', 'bash', 'powershell', 'networking', 
        'security', 'penetration testing', 'ethical hacking', 'blockchain', 'cryptocurrency', 
        'smart contracts', 'solidity', 'web3', 'devops', 'sre', 'cloud computing', 'big data', 
        'hadoop', 'spark', 'kafka', 'elasticsearch', 'logstash', 'kibana', 'data warehousing', 
        'etl', 'business intelligence', 'project management', 'leadership', 'communication', 
        'problem solving', 'critical thinking', 'teamwork', 'time management', 'creativity',
        'mern', 'mean', 'full stack', 'frontend', 'backend', 'web development', 'mobile app',
        'database', 'api', 'rest', 'soap', 'json', 'xml', 'http', 'tcp/ip', 'dns', 'ssl',
        'tls', 'oauth', 'jwt', 'authentication', 'authorization', 'encryption', 'hashing',
        'testing', 'unit testing', 'integration testing', 'e2e testing', 'qa', 'quality assurance',
        'debugging', 'performance optimization', 'seo', 'analytics', 'marketing', 'sales',
        'customer service', 'support', 'helpdesk', 'technical writing', 'documentation',
        'node', 'npm', 'yarn', 'webpack', 'babel', 'eslint', 'prettier', 'jest', 'mocha', 'chai',
        'cypress', 'selenium', 'postman', 'swagger', 'openapi', 'firebase', 'supabase', 'amplify',
        'vercel', 'netlify', 'heroku', 'digital ocean', 'linode', 'ec2', 's3', 'lambda', 'dynamodb',
        'rds', 'aurora', 'redis', 'memcached', 'nginx', 'apache', 'iis', 'tomcat', 'websocket',
        'webrtc', 'pwa', 'spa', 'ssr', 'ssg', 'jamstack', 'cms', 'wordpress', 'drupal', 'joomla',
        'magento', 'shopify', 'woocommerce', 'ecommerce', 'payment gateway', 'stripe', 'paypal',
        'braintree', 'square', 'authorize.net', 'seo', 'sem', 'smm', 'content marketing', 'email marketing',
        'affiliate marketing', 'growth hacking', 'a/b testing', 'user research', 'user testing',
        'usability testing', 'accessibility', 'wcag', 'aria', 'screen reader', 'keyboard navigation',
        'responsive web design', 'mobile first', 'progressive enhancement', 'graceful degradation',
        'cross-browser compatibility', 'cross-platform compatibility', 'internationalization', 'localization',
        'i18n', 'l10n', 'rtl', 'ltr', 'unicode', 'utf-8', 'ascii', 'character encoding', 'emoji',
        'svg', 'canvas', 'webgl', 'three.js', 'd3.js', 'chart.js', 'highcharts', 'plotly', 'leaflet',
        'mapbox', 'google maps', 'bing maps', 'openstreetmap', 'geolocation', 'geocoding', 'reverse geocoding',
        'push notifications', 'service worker', 'web worker', 'indexeddb', 'localstorage', 'sessionstorage',
        'cookies', 'jwt', 'oauth', 'openid connect', 'saml', 'ldap', 'active directory', 'kerberos',
        'sso', 'mfa', '2fa', 'biometric authentication', 'facial recognition', 'fingerprint recognition',
        'voice recognition', 'iris recognition', 'retina recognition', 'palm recognition', 'vein recognition',
        'behavioral biometrics', 'keystroke dynamics', 'gait analysis', 'signature recognition',
        'handwriting recognition', 'speech recognition', 'natural language processing', 'nlp',
        'sentiment analysis', 'entity recognition', 'text classification', 'text summarization',
        'machine translation', 'speech synthesis', 'text to speech', 'speech to text', 'chatbot',
        'virtual assistant', 'conversational ai', 'dialog system', 'intent recognition', 'entity extraction',
        'slot filling', 'context management', 'dialog management', 'dialog flow', 'dialog state tracking',
        'dialog policy', 'dialog generation', 'dialog evaluation', 'dialog annotation', 'dialog corpus',
        'dialog dataset', 'dialog system evaluation', 'dialog system annotation', 'dialog system corpus',
        'dialog system dataset', 'dialog system benchmark', 'dialog system challenge', 'dialog system competition',
        # HR skills
        'recruiting', 'talent acquisition', 'onboarding', 'offboarding', 'employee relations',
        'benefits administration', 'compensation', 'payroll', 'hr policies', 'hr compliance',
        'performance management', 'succession planning', 'workforce planning', 'employee engagement',
        'diversity and inclusion', 'training and development', 'organizational development',
        'change management', 'conflict resolution', 'labor relations', 'collective bargaining',
        'hris', 'applicant tracking system', 'ats', 'workday', 'sap hr', 'peoplesoft',
        'oracle hcm', 'bamboo hr', 'greenhouse', 'lever', 'indeed', 'linkedin recruiter',
        # Finance skills
        'accounting', 'financial analysis', 'financial reporting', 'budgeting', 'forecasting',
        'financial planning', 'financial modeling', 'cost accounting', 'tax preparation',
        'tax planning', 'audit', 'risk assessment', 'compliance', 'sarbanes-oxley', 'sox',
        'gaap', 'ifrs', 'bookkeeping', 'accounts payable', 'accounts receivable', 'general ledger',
        'balance sheet', 'income statement', 'cash flow statement', 'financial statements',
        'quickbooks', 'sap finance', 'oracle financials', 'sage', 'xero', 'excel financial functions',
        # Marketing skills
        'digital marketing', 'content marketing', 'social media marketing', 'email marketing',
        'search engine optimization', 'search engine marketing', 'pay-per-click', 'ppc',
        'google ads', 'facebook ads', 'instagram ads', 'twitter ads', 'linkedin ads',
        'conversion rate optimization', 'a/b testing', 'marketing automation', 'customer segmentation',
        'customer journey mapping', 'brand management', 'product marketing', 'market research',
        'competitive analysis', 'google analytics', 'adobe analytics', 'hubspot', 'marketo',
        'mailchimp', 'constant contact', 'hootsuite', 'buffer', 'canva', 'adobe creative suite',
        # Sales skills
        'sales strategy', 'sales management', 'account management', 'business development',
        'lead generation', 'lead qualification', 'cold calling', 'sales presentations',
        'negotiation', 'closing techniques', 'customer relationship management', 'crm',
        'salesforce', 'hubspot crm', 'zoho crm', 'pipedrive', 'sales forecasting',
        'territory management', 'channel sales', 'direct sales', 'inside sales', 'outside sales',
        # Customer service skills
        'customer support', 'customer success', 'technical support', 'help desk',
        'service desk', 'call center', 'customer satisfaction', 'customer retention',
        'complaint resolution', 'service level agreements', 'sla', 'zendesk', 'freshdesk',
        'intercom', 'live chat', 'ticketing systems', 'knowledge base management',
        # Operations skills
        'operations management', 'supply chain management', 'inventory management',
        'logistics', 'warehouse management', 'procurement', 'vendor management',
        'quality control', 'quality assurance', 'process improvement', 'lean', 'six sigma',
        'kaizen', 'erp systems', 'sap', 'oracle', 'netsuite', 'microsoft dynamics',
        # Project management skills
        'project management', 'program management', 'portfolio management', 'agile',
        'scrum', 'kanban', 'waterfall', 'prince2', 'pmp', 'project planning',
        'resource allocation', 'risk management', 'stakeholder management',
        'microsoft project', 'asana', 'trello', 'jira', 'basecamp', 'smartsheet',
        # Legal skills
        'contract law', 'corporate law', 'intellectual property', 'patents',
        'trademarks', 'copyrights', 'compliance', 'regulatory affairs', 'legal research',
        'legal writing', 'litigation', 'arbitration', 'mediation', 'negotiation',
        'westlaw', 'lexisnexis', 'docusign', 'e-discovery', 'legal document management',
        # Healthcare skills
        'patient care', 'clinical documentation', 'medical coding', 'medical billing',
        'electronic health records', 'ehr', 'epic', 'cerner', 'meditech', 'allscripts',
        'hipaa compliance', 'healthcare compliance', 'clinical trials', 'medical research',
        'telehealth', 'telemedicine', 'healthcare administration', 'healthcare management',
        # Education skills
        'curriculum development', 'instructional design', 'e-learning', 'lms',
        'learning management systems', 'blackboard', 'canvas', 'moodle', 'google classroom',
        'student assessment', 'educational technology', 'classroom management',
        'special education', 'iep', 'differentiated instruction', 'student engagement',
        # Data science skills
        'data analysis', 'data mining', 'data visualization', 'statistical analysis',
        'predictive modeling', 'machine learning', 'deep learning', 'natural language processing',
        'computer vision', 'big data', 'data warehousing', 'etl', 'sql', 'nosql',
        'r', 'python', 'sas', 'spss', 'stata', 'matlab', 'tableau', 'power bi',
        'looker', 'qlik', 'd3.js', 'hadoop', 'spark', 'aws redshift', 'google bigquery',
        'azure synapse', 'snowflake', 'data lake', 'data governance', 'data quality',
        # Soft skills
        'communication', 'teamwork', 'leadership', 'problem solving', 'critical thinking',
        'decision making', 'time management', 'organization', 'adaptability', 'flexibility',
        'creativity', 'innovation', 'emotional intelligence', 'conflict resolution',
        'negotiation', 'persuasion', 'presentation skills', 'public speaking',
        'active listening', 'written communication', 'verbal communication',
        'interpersonal skills', 'customer service', 'attention to detail',
        'multitasking', 'work ethic', 'self-motivation', 'resilience', 'stress management'
    ]
    
    # Try to find a skills section first
    skills_section = None
    text_lower = text.lower()
    
    # Look for a skills section
    skills_headers = ['skills', 'technical skills', 'core competencies', 'technologies', 'proficiencies']
    for header in skills_headers:
        match = re.search(rf'{header}[:\s]*\n', text_lower, re.IGNORECASE)
        if match:
            start_idx = match.end()
            # Find the end of the section (next header or end of text)
            next_header = re.search(r'\n\s*[a-z\s]+[:\s]*\n', text_lower[start_idx:], re.IGNORECASE)
            end_idx = start_idx + next_header.start() if next_header else len(text_lower)
            skills_section = text_lower[start_idx:end_idx]
            logger.info(f"Found skills section: {len(skills_section)} chars")
            break
    
    # If skills section found, prioritize extracting from there
    search_text = skills_section if skills_section else text_lower
    
    # Extract skills using different methods
    skills = set()
    
    # Method 1: Direct matching of common skills
    for skill in common_skills:
        # Use word boundary to avoid partial matches
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, search_text, re.IGNORECASE):
            skills.add(skill)
    
    # Method 2: Look for bullet points or comma-separated lists in skills section
    if skills_section:
        # Extract bullet points
        bullet_skills = re.findall(r'[•\-*]\s*([^•\-*\n]+)', skills_section)
        for skill_text in bullet_skills:
            skill_text = skill_text.strip().lower()
            # Check if this matches any known skill
            for known_skill in common_skills:
                if known_skill in skill_text:
                    skills.add(known_skill)
        
        # Extract comma-separated skills
        comma_lists = re.findall(r'([^•\-*\n:]+(?:,\s*[^,\n]+)+)', skills_section)
        for skill_list in comma_lists:
            for skill_item in skill_list.split(','):
                skill_item = skill_item.strip().lower()
                # Check if this matches any known skill
                for known_skill in common_skills:
                    if known_skill == skill_item:
                        skills.add(known_skill)
    
    # Method 3: Look for skills in the entire text if we found few skills
    if len(skills) < 5 and not skills_section:
        # Look for skills mentioned in context
        skill_contexts = [
            r'proficient in\s+([^.,:;]+)',
            r'experience with\s+([^.,:;]+)',
            r'knowledge of\s+([^.,:;]+)',
            r'familiar with\s+([^.,:;]+)',
            r'skilled in\s+([^.,:;]+)',
            r'worked with\s+([^.,:;]+)',
            r'expertise in\s+([^.,:;]+)',
            r'specialized in\s+([^.,:;]+)'
        ]
        
        for context_pattern in skill_contexts:
            matches = re.findall(context_pattern, text_lower)
            for match in matches:
                for skill in common_skills:
                    if skill in match.lower():
                        skills.add(skill)
    
    logger.info(f"Extracted {len(skills)} skills")
    return list(skills)

def extract_experience(text):
    """Extract work experience details from resume"""
    if not text or len(text) < 10:
        logger.warning("Text too short for experience extraction")
        return []

    # Look for experience section
    experience_section = None
    text_lower = text.lower()

    # Common headers for experience sections
    exp_headers = ['experience', 'work experience', 'professional experience', 'employment history', 'work history']

    # Try to find the experience section
    for header in exp_headers:
        match = re.search(rf'{header}[:\s]*\n', text_lower, re.IGNORECASE)
        if match:
            start_idx = match.end()
            # Find the end of the section (next major header or end of text)
            next_header = re.search(r'\n\s*(?:education|skills|projects|certifications|awards|languages|interests|references)[:\s]*\n', 
                                   text_lower[start_idx:], re.IGNORECASE)
            end_idx = start_idx + next_header.start() if next_header else len(text_lower)
            experience_section = text[start_idx:end_idx]  # Use original case for better analysis
            logger.info(f"Found experience section: {len(experience_section)} chars")
            break

    if not experience_section:
        logger.warning("No clear experience section found")
        return []

    # Extract job titles, companies, and dates
    experiences = []

    # Common job title patterns
    job_title_patterns = [
        r'(senior|junior|lead|principal|staff)?\s*(software|web|mobile|frontend|backend|full stack|devops|cloud|data|machine learning|ai|product|project)?\s*(developer|engineer|architect|manager|designer|analyst|scientist|specialist|consultant)',
        r'(cto|ceo|cio|vp|director|head|chief)\s*(technology|information|product|engineering|technical|executive|operating)',
        r'(intern|internship|co-op|trainee|graduate)'
    ]

    # Try to extract structured experience entries
    lines = experience_section.split('\n')
    current_exp = {}

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check if this line looks like a job title
        is_job_title = False
        for pattern in job_title_patterns:
            if re.search(pattern, line.lower()):
                is_job_title = True
                break
        
        # Check if this line contains a date range
        has_date = bool(re.search(r'(19|20)\d{2}\s*[-–—to]*\s*((19|20)\d{2}|present|current|now)', line.lower()))
        
        # If we find what looks like a new job entry
        if (is_job_title or has_date) and (i == 0 or not lines[i-1].strip()):
            # Save previous entry if it exists
            if current_exp and 'title' in current_exp:
                experiences.append(current_exp)
                current_exp = {}
            
            # Start new entry
            current_exp = {'title': line}
            
            # Try to extract company and dates from this or next line
            if i + 1 < len(lines) and lines[i+1].strip():
                next_line = lines[i+1].strip()
                
                # Check if next line has dates
                date_match = re.search(r'(19|20)\d{2}\s*[-–—to]*\s*((19|20)\d{2}|present|current|now)', next_line.lower())
                if date_match:
                    current_exp['dates'] = next_line
                    
                    # If dates are on a separate line, company might be in the current line
                    if not has_date:
                        # Try to extract company from current line
                        title_parts = line.split(' at ', 1)
                        if len(title_parts) > 1:
                            current_exp['title'] = title_parts[0].strip()
                            current_exp['company'] = title_parts[1].strip()
                else:
                    # Next line might be company
                    current_exp['company'] = next_line
        
        # If we're in a current entry, collect description
        elif current_exp and 'title' in current_exp:
            if 'description' not in current_exp:
                current_exp['description'] = line
            else:
                current_exp['description'] += ' ' + line

    # Add the last entry if it exists
    if current_exp and 'title' in current_exp:
        experiences.append(current_exp)

    logger.info(f"Extracted {len(experiences)} experience entries")
    return experiences

def extract_projects(text):
    """Extract project information from resume"""
    if not text or len(text) < 10:
        logger.warning("Text too short for project extraction")
        return []

    # Look for projects section
    projects_section = None
    text_lower = text.lower()

    # Common headers for project sections
    project_headers = ['projects', 'personal projects', 'academic projects', 'key projects', 'relevant projects']

    # Try to find the projects section
    for header in project_headers:
        match = re.search(rf'{header}[:\s]*\n', text_lower, re.IGNORECASE)
        if match:
            start_idx = match.end()
            # Find the end of the section (next major header or end of text)
            next_header = re.search(r'\n\s*(?:experience|education|skills|certifications|awards|languages|interests|references)[:\s]*\n', 
                                   text_lower[start_idx:], re.IGNORECASE)
            end_idx = start_idx + next_header.start() if next_header else len(text_lower)
            projects_section = text[start_idx:end_idx]  # Use original case for better analysis
            logger.info(f"Found projects section: {len(projects_section)} chars")
            break

    if not projects_section:
        logger.warning("No clear projects section found")
        return []

    # Extract project titles and descriptions
    projects = []

    # Try to extract structured project entries
    lines = projects_section.split('\n')
    current_project = {}

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check if this line looks like a project title (typically short, possibly with tech stack in parentheses)
        is_title = (len(line) < 100 and 
                   (i == 0 or not lines[i-1].strip()) and 
                   not re.match(r'^[•\-*]', line))  # Not a bullet point
        
        if is_title:
            # Save previous project if it exists
            if current_project and 'title' in current_project:
                projects.append(current_project)
                current_project = {}
            
            # Start new project
            current_project = {'title': line}
        
        # If we're in a current project, collect description
        elif current_project and 'title' in current_project:
            if 'description' not in current_project:
                current_project['description'] = line
            else:
                current_project['description'] += ' ' + line

    # Add the last project if it exists
    if current_project and 'title' in current_project:
        projects.append(current_project)

    logger.info(f"Extracted {len(projects)} project entries")
    return projects

def extract_education_details(text):
    """Extract detailed education information from resume"""
    if not text or len(text) < 10:
        logger.warning("Text too short for education extraction")
        return []

    # Look for education section
    education_section = None
    text_lower = text.lower()

    # Common headers for education sections
    edu_headers = ['education', 'academic background', 'academic qualifications', 'educational qualifications']

    # Try to find the education section
    for header in edu_headers:
        match = re.search(rf'{header}[:\s]*\n', text_lower, re.IGNORECASE)
        if match:
            start_idx = match.end()
            # Find the end of the section (next major header or end of text)
            next_header = re.search(r'\n\s*(?:experience|skills|projects|certifications|awards|languages|interests|references)[:\s]*\n', 
                                   text_lower[start_idx:], re.IGNORECASE)
            end_idx = start_idx + next_header.start() if next_header else len(text_lower)
            education_section = text[start_idx:end_idx]  # Use original case for better analysis
            logger.info(f"Found education section: {len(education_section)} chars")
            break

    if not education_section:
        logger.warning("No clear education section found")
        return []

    # Extract education entries
    education = []

    # Common degree patterns
    degree_patterns = [
        r'(bachelor|master|phd|doctorate|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?a\.?|b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?|mba)',
        r'(associate|diploma|certificate)'
    ]

    # Try to extract structured education entries
    lines = education_section.split('\n')
    current_edu = {}

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check if this line looks like a degree or institution
        is_edu_entry = False
        for pattern in degree_patterns:
            if re.search(pattern, line.lower()):
                is_edu_entry = True
                break
        
        # Also check for institution keywords
        if not is_edu_entry:
            if re.search(r'(university|college|institute|school|academy)', line.lower()):
                is_edu_entry = True
        
        # Check if this line contains a date range
        has_date = bool(re.search(r'(19|20)\d{2}\s*[-–—to]*\s*((19|20)\d{2}|present|current|now)', line.lower()))
        
        # If we find what looks like a new education entry
        if (is_edu_entry or has_date) and (i == 0 or not lines[i-1].strip()):
            # Save previous entry if it exists
            if current_edu and ('institution' in current_edu or 'degree' in current_edu):
                education.append(current_edu)
                current_edu = {}
            
            # Start new entry
            if re.search(r'(university|college|institute|school|academy)', line.lower()):
                current_edu = {'institution': line}
            else:
                current_edu = {'degree': line}
            
            # Try to extract other details from this or next line
            if i + 1 < len(lines) and lines[i+1].strip():
                next_line = lines[i+1].strip()
                
                # Check if next line has dates
                if re.search(r'(19|20)\d{2}\s*[-–—to]*\s*((19|20)\d{2}|present|current|now)', next_line.lower()):
                    current_edu['dates'] = next_line
                elif 'institution' not in current_edu and re.search(r'(university|college|institute|school|academy)', next_line.lower()):
                    current_edu['institution'] = next_line
                elif 'degree' not in current_edu:
                    for pattern in degree_patterns:
                        if re.search(pattern, next_line.lower()):
                            current_edu['degree'] = next_line
                            break
        
        # If we're in a current entry, collect additional details
        elif current_edu and ('institution' in current_edu or 'degree' in current_edu):
            if 'details' not in current_edu:
                current_edu['details'] = line
            else:
                current_edu['details'] += ' ' + line

    # Add the last entry if it exists
    if current_edu and ('institution' in current_edu or 'degree' in current_edu):
        education.append(current_edu)

    logger.info(f"Extracted {len(education)} education entries")
    return education

def extract_certifications(text):
    """Extract certification information from resume"""
    if not text or len(text) < 10:
        logger.warning("Text too short for certification extraction")
        return []

    # Look for certifications section
    cert_section = None
    text_lower = text.lower()

    # Common headers for certification sections
    cert_headers = ['certifications', 'certificates', 'professional certifications', 'credentials']

    # Try to find the certifications section
    for header in cert_headers:
        match = re.search(rf'{header}[:\s]*\n', text_lower, re.IGNORECASE)
        if match:
            start_idx = match.end()
            # Find the end of the section (next major header or end of text)
            next_header = re.search(r'\n\s*(?:experience|education|skills|projects|awards|languages|interests|references)[:\s]*\n', 
                                   text_lower[start_idx:], re.IGNORECASE)
            end_idx = start_idx + next_header.start() if next_header else len(text_lower)
            cert_section = text[start_idx:end_idx]  # Use original case
            logger.info(f"Found certifications section: {len(cert_section)} chars")
            break

    if not cert_section:
        logger.warning("No clear certifications section found")
        return []

    # Extract certification entries
    certifications = []

    # Try to extract structured certification entries
    lines = cert_section.split('\n')
    current_cert = {}

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check if this line looks like a certification title (typically starts with a bullet or is a short line)
        is_title = (len(line) < 100 and 
                   (i == 0 or not lines[i-1].strip() or re.match(r'^[•\-*]', line)))
        
        if is_title:
            # Clean up bullet points if present
            if re.match(r'^[•\-*]', line):
                line = re.sub(r'^[•\-*]\s*', '', line)
            
            # Save previous certification if it exists
            if current_cert and 'title' in current_cert:
                certifications.append(current_cert)
                current_cert = {}
            
            # Start new certification
            current_cert = {'title': line}
            
            # Try to extract date if it's in the same line
            date_match = re.search(r'(19|20)\d{2}', line)
            if date_match:
                current_cert['date'] = date_match.group(0)
        
        # If we're in a current certification, collect additional details
        elif current_cert and 'title' in current_cert:
            if 'details' not in current_cert:
                current_cert['details'] = line
            else:
                current_cert['details'] += ' ' + line

    # Add the last certification if it exists
    if current_cert and 'title' in current_cert:
        certifications.append(current_cert)

    logger.info(f"Extracted {len(certifications)} certification entries")
    return certifications

def preprocess_text(text):
    """Preprocess text to focus on important terms"""
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def calculate_semantic_similarity(resume_text, job_text):
    """Calculate semantic similarity between resume and job description using TF-IDF and cosine similarity"""
    if not resume_text or not job_text:
        return 0.0
    
    try:
        # Preprocess texts
        resume_processed = preprocess_text(resume_text)
        job_processed = preprocess_text(job_text)
        
        # Create TF-IDF vectorizer
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([resume_processed, job_processed])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        
        logger.info(f"Semantic similarity score: {similarity:.4f}")
        return similarity
    except Exception as e:
        logger.error(f"Error calculating semantic similarity: {str(e)}")
        return 0.0

def calculate_skills_match_score(resume_skills, required_skills):
    """Calculate a score based on matching skills"""
    if not required_skills:
        logger.warning("No required skills specified for job")
        return 0.0, []
    
    # Filter out empty strings from required skills
    required_skills = [s for s in required_skills if s]
    if not required_skills:
        return 0.0, []
    
    # Case-insensitive matching
    required_lower = [s.lower() for s in required_skills]
    
    # Check for exact matches
    matched_skills = []
    for skill in resume_skills:
        if skill.lower() in required_lower:
            matched_skills.append(skill)
    
    # Calculate skills match ratio
    skills_match_ratio = len(matched_skills) / len(required_skills)
    
    # Bonus for having most of the required skills
    if skills_match_ratio >= 0.7:
        skills_match_ratio = min(1.0, skills_match_ratio + 0.1)  # Bonus for having most required skills
    
    logger.info(f"Skills match: {len(matched_skills)}/{len(required_skills)} = {skills_match_ratio:.4f}")
    
    return skills_match_ratio, matched_skills

def calculate_experience_relevance(resume_experiences, job_text):
    """Calculate how relevant the candidate's experience is to the job"""
    if not resume_experiences or not job_text:
        return 0.0

    job_text_lower = job_text.lower()

    # Extract key terms from job description
    job_terms = set(re.findall(r'\b\w+\b', job_text_lower))
    job_terms = {term for term in job_terms if len(term) > 3 and term not in stopwords.words('english')}

    # Calculate relevance for each experience entry
    relevance_scores = []

    for exp in resume_experiences:
        if 'description' not in exp:
            continue
        
        exp_text = exp.get('title', '') + ' ' + exp.get('company', '') + ' ' + exp.get('description', '')
        exp_text_lower = exp_text.lower()
        
        # Count matching terms
        exp_terms = set(re.findall(r'\b\w+\b', exp_text_lower))
        exp_terms = {term for term in exp_terms if len(term) > 3 and term not in stopwords.words('english')}
        
        matching_terms = job_terms.intersection(exp_terms)
        
        # Calculate relevance score for this experience
        if len(job_terms) > 0:
            relevance = len(matching_terms) / len(job_terms)
            relevance_scores.append(relevance)

    # Return average relevance across all experiences
    if relevance_scores:
        return sum(relevance_scores) / len(relevance_scores)
    return 0.0

def calculate_project_relevance(resume_projects, job_text):
    """Calculate how relevant the candidate's projects are to the job"""
    if not resume_projects or not job_text:
        return 0.0

    job_text_lower = job_text.lower()

    # Extract key terms from job description
    job_terms = set(re.findall(r'\b\w+\b', job_text_lower))
    job_terms = {term for term in job_terms if len(term) > 3 and term not in stopwords.words('english')}

    # Calculate relevance for each project entry
    relevance_scores = []

    for project in resume_projects:
        if 'description' not in project:
            continue
        
        project_text = project.get('title', '') + ' ' + project.get('description', '')
        project_text_lower = project_text.lower()
        
        # Count matching terms
        project_terms = set(re.findall(r'\b\w+\b', project_text_lower))
        project_terms = {term for term in project_terms if len(term) > 3 and term not in stopwords.words('english')}
        
        matching_terms = job_terms.intersection(project_terms)
        
        # Calculate relevance score for this project
        if len(job_terms) > 0:
            relevance = len(matching_terms) / len(job_terms)
            relevance_scores.append(relevance)

    # Return average relevance across all projects
    if relevance_scores:
        return sum(relevance_scores) / len(relevance_scores)
    return 0.0

def calculate_education_relevance(resume_education, job_text):
    """Calculate how relevant the candidate's education is to the job"""
    if not resume_education or not job_text:
        return 0.0

    job_text_lower = job_text.lower()

    # Extract education-related terms from job description
    edu_keywords = [
        'degree', 'bachelor', 'master', 'phd', 'doctorate', 'bs', 'ms', 'ba', 'ma',
        'btech', 'mtech', 'be', 'me', 'mba', 'education', 'university', 'college',
        'academic', 'graduate', 'undergraduate', 'major', 'minor', 'concentration',
        'computer science', 'engineering', 'information technology', 'it', 'business',
        'management', 'marketing', 'finance', 'accounting', 'economics', 'mathematics',
        'statistics', 'data science', 'machine learning', 'artificial intelligence'
    ]

    # Check if job requires specific education
    required_edu_terms = []
    for term in edu_keywords:
        if term in job_text_lower:
            required_edu_terms.append(term)

    if not required_edu_terms:
        # If job doesn't specify education requirements, give a neutral score
        return 0.5

    # Calculate relevance for each education entry
    relevance_scores = []

    for edu in resume_education:
        edu_text = ' '.join([
            edu.get('institution', ''),
            edu.get('degree', ''),
            edu.get('details', '')
        ]).lower()
        
        # Count matching terms
        matches = sum(1 for term in required_edu_terms if term in edu_text)
        
        # Calculate relevance score for this education entry
        if len(required_edu_terms) > 0:
            relevance = matches / len(required_edu_terms)
            relevance_scores.append(relevance)

    # Return highest education relevance (most relevant degree)
    if relevance_scores:
        return max(relevance_scores)
    return 0.0

def calculate_certification_relevance(resume_certifications, job_text):
    """Calculate how relevant the candidate's certifications are to the job"""
    if not resume_certifications or not job_text:
        return 0.0

    job_text_lower = job_text.lower()

    # Extract certification-related terms from job description
    cert_keywords = [
        'certification', 'certificate', 'certified', 'credential', 'license',
        'aws', 'azure', 'gcp', 'google cloud', 'microsoft', 'oracle', 'cisco',
        'comptia', 'pmp', 'scrum', 'agile', 'itil', 'security', 'network',
        'cloud', 'data', 'ai', 'machine learning', 'web', 'mobile', 'development'
    ]

    # Check if job mentions certifications
    required_cert_terms = []
    for term in cert_keywords:
        if term in job_text_lower:
            required_cert_terms.append(term)

    if not required_cert_terms:
        # If job doesn't specify certification requirements, give a neutral score
        return 0.5

    # Calculate relevance for each certification entry
    relevance_scores = []

    for cert in resume_certifications:
        cert_text = ' '.join([
            cert.get('title', ''),
            cert.get('details', '')
        ]).lower()
        
        # Count matching terms
        matches = sum(1 for term in required_cert_terms if term in cert_text)
        
        # Calculate relevance score for this certification entry
        if len(required_cert_terms) > 0:
            relevance = matches / len(required_cert_terms)
            relevance_scores.append(relevance)

    # Return highest certification relevance (most relevant certification)
    if relevance_scores:
        return max(relevance_scores)
    return 0.0

def calculate_comprehensive_ats_score(resume_text, job_description, job_requirements, required_skills):
    """Calculate a comprehensive ATS score that truly compares the entire resume against all job details"""
    if not resume_text or not job_description:
        logger.warning("Missing text for score calculation")
        return 0, [], [], {}
    
    # Extract all components from resume
    resume_skills = extract_skills(resume_text)
    resume_experiences = extract_experience(resume_text)
    resume_projects = extract_projects(resume_text)
    resume_education = extract_education_details(resume_text)
    resume_certifications = extract_certifications(resume_text)
    
    logger.info(f"Extracted from resume: {len(resume_skills)} skills, {len(resume_experiences)} experiences, "
                f"{len(resume_projects)} projects, {len(resume_education)} education entries, "
                f"{len(resume_certifications)} certifications")
    
    # Combine job description and requirements for text analysis
    job_text = job_description + " " + job_requirements
    
    # 1. Skills Match Score 
    skills_match_ratio, matched_skills = calculate_skills_match_score(resume_skills, required_skills)
    
    # 2. Semantic Similarity Score
    # This compares the entire resume text against the entire job text
    semantic_similarity = calculate_semantic_similarity(resume_text, job_text)
    
    # 3. Experience Relevance 
    experience_relevance = calculate_experience_relevance(resume_experiences, job_text)
    
    # 4. Project Relevance 
    project_relevance = calculate_project_relevance(resume_projects, job_text)
    
    # 5. Education Relevance
    education_relevance = calculate_education_relevance(resume_education, job_text)
    
    # 6. Certification Relevance
    certification_relevance = calculate_certification_relevance(resume_certifications, job_text)
    
    # Calculate final score with component weights
    final_score = (
    (skills_match_ratio * 0.40) +       
    (semantic_similarity * 0.35) +      
    (experience_relevance * 0.05) +     
    (project_relevance * 0.05) +        
    (education_relevance * 0.10) +      
    (certification_relevance * 0.05)    
    ) * 100
    
    # Round to nearest integer
    final_score = round(final_score)
     

    # Skills match (40%)
    # Semantic similarity (35%)
    # Experience relevance (5%)
    # Project relevance (5%)
    # Education relevance (10%)
     # Certification relevance (5%)

   




    if 18 <= final_score <= 25:
      final_score += 28
    elif 10 <= final_score <= 17:
      final_score += 20
    elif 26 <= final_score <= 40:
      final_score += 20
    elif 41 <= final_score <= 60:
      final_score += 15
    elif 61 <= final_score <= 70:
      final_score += 10
    
    # Ensure score is between 0 and 100
    final_score = max(0, min(100, final_score))
    
    # Generate score breakdown for transparency
    score_breakdown = {
        "skills_match": round(skills_match_ratio * 100),
        "semantic_similarity": round(semantic_similarity * 100),
        "experience_relevance": round(experience_relevance * 100),
        "project_relevance": round(project_relevance * 100),
        "education_relevance": round(education_relevance * 100),
        "certification_relevance": round(certification_relevance * 100),
        "total_score": final_score
    }
    
    logger.info(f"Final ATS score: {final_score}")
    logger.info(f"Score breakdown: {score_breakdown}")
    
    return final_score, resume_skills, matched_skills, score_breakdown

@bp.route('/jobs', methods=['GET', 'POST'])
def jobs():
    db = current_app.config["db"]
    
    if request.method == 'POST':
        # Create new job role
        job_data = request.json
        job_id = JobRole.create(db, job_data)
        return jsonify({"success": True, "jobId": job_id}), 201
    else:
        # Get all job roles
        limit = request.args.get('limit', type=int)
        skip = request.args.get('skip', type=int, default=0)
        jobs = JobRole.get_all(db, limit, skip)
        # Serialize the jobs before returning
        serialized_jobs = serialize_doc(jobs)
        return jsonify({"jobs": serialized_jobs})

@bp.route('/jobs/<job_id>', methods=['GET', 'PUT', 'DELETE'])
def job(job_id):
    db = current_app.config["db"]
    
    if request.method == 'GET':
        # Get job role by ID
        job = JobRole.get_by_id(db, job_id)
        if not job:
            return jsonify({"error": "Job role not found"}), 404
        # Serialize the job before returning
        serialized_job = serialize_doc(job)
        return jsonify({"job": serialized_job})
    
    elif request.method == 'PUT':
        # Update job role
        job_data = request.json
        success = JobRole.update(db, job_id, job_data)
        if not success:
            return jsonify({"error": "Job role not found"}), 404
        return jsonify({"success": True})
    
    elif request.method == 'DELETE':
        # Delete job role
        success = JobRole.delete(db, job_id)
        if not success:
            return jsonify({"error": "Job role not found"}), 404
        return jsonify({"success": True})

@bp.route('/upload', methods=['POST'])
def upload_resumes():
    db = current_app.config["db"]
    
    logger.info("Resume upload request received")
    
    if 'resumes' not in request.files:
        logger.error("No files provided in request")
        return jsonify({"error": "No files provided"}), 400
    
    if 'jobId' not in request.form:
        logger.error("Job ID not provided in request")
        return jsonify({"error": "Job ID is required"}), 400
    
    job_id = request.form['jobId']
    job = JobRole.get_by_id(db, job_id)
    
    if not job:
        logger.error(f"Job role with ID {job_id} not found")
        return jsonify({"error": "Job role not found"}), 404
    
    files = request.files.getlist('resumes')
    logger.info(f"Received {len(files)} resume files")
    
    if not files or files[0].filename == '':
        logger.error("No files selected")
        return jsonify({"error": "No files selected"}), 400
    
    # Create batch ID for this upload
    batch_id = str(uuid.uuid4())
    logger.info(f"Created batch ID: {batch_id}")
    
    results = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            logger.info(f"Processing file: {filename}")
            
            # Save file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename.split('.')[-1]}") as temp:
                file.save(temp.name)
                file_path = temp.name
            
            try:
                # Extract text from file
                resume_text = extract_text(file_path)
                
                # Log the text extraction result
                if resume_text:
                    logger.info(f"Successfully extracted {len(resume_text)} characters from {filename}")
                else:
                    logger.warning(f"Failed to extract text from {filename}")
                
                if not resume_text or len(resume_text) < 50:
                    logger.warning(f"Extracted text is too short or empty: {len(resume_text) if resume_text else 0} chars")
                    # Add a basic result with minimal information
                    result = {
                        "name": "Unknown",
                        "email": None,
                        "phone": None,
                        "college": None,
                        "jobId": ObjectId(job_id),
                        "jobTitle": job['title'],
                        "skills": [],
                        "matchedSkills": [],
                        "score": 0,
                        "batchId": batch_id,
                        "filename": filename,
                        "processed": True,
                        "processingError": "Could not extract text from resume"
                    }
                else:
                    # Extract information
                    name = extract_name(resume_text)
                    email, phone = extract_contact_info(resume_text)
                    college = extract_college(resume_text)
                    
                    # Calculate comprehensive score
                    score, skills, matched_skills, score_breakdown = calculate_comprehensive_ats_score(
                        resume_text, 
                        job.get('description', ''), 
                        job.get('requirements', ''), 
                        job.get('skills', [])
                    )
                    
                    # Create result object
                    result = {
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "college": college,
                        "jobId": ObjectId(job_id),
                        "jobTitle": job['title'],
                        "skills": skills,
                        "matchedSkills": matched_skills,
                        "score": score,
                        "scoreBreakdown": score_breakdown,
                        "batchId": batch_id,
                        "filename": filename,
                        "processed": True
                    }
                
                results.append(result)
                logger.info(f"Successfully processed {filename}, score: {result['score']}")
            
            except Exception as e:
                logger.error(f"Error processing file {filename}: {str(e)}")
                logger.error(traceback.format_exc())
                # Add a result with error information
                results.append({
                    "name": "Error",
                    "email": None,
                    "phone": None,
                    "college": None,
                    "jobId": ObjectId(job_id),
                    "jobTitle": job['title'],
                    "skills": [],
                    "matchedSkills": [],
                    "score": 0,
                    "batchId": batch_id,
                    "filename": filename,
                    "processed": False,
                    "processingError": str(e)
                })
            
            finally:
                # Clean up temporary file
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Error removing temp file: {str(e)}")
    
    # Save results to database
    if results:
        ResumeResult.create_many(db, results)
        logger.info(f"Saved {len(results)} results to database")
    
    return jsonify({
        "success": True,
        "batchId": batch_id,
        "processedCount": len(results)
    })

@bp.route('/results', methods=['GET'])
def get_results():
    db = current_app.config["db"]
    
    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    sort_by = request.args.get('sort', 'score')
    sort_order = request.args.get('order', 'desc')
    job_id = request.args.get('job')
    batch_id = request.args.get('batch')
    search = request.args.get('search')
    
    # Build filters
    filters = {}
    
    if job_id and job_id != 'all':
        filters['jobId'] = job_id
    
    if batch_id:
        filters['batchId'] = batch_id
    
    if search:
        filters['search'] = search
    
    # Get results
    results, total = ResumeResult.get_all(
        db, 
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit
    )
    
    # Serialize results before returning
    serialized_results = serialize_doc(results)
    
    return jsonify({
        "results": serialized_results,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    })

@bp.route('/stats', methods=['GET'])
def get_stats():
    db = current_app.config["db"]
    
    # Get statistics
    total_jobs = JobRole.count(db)
    total_resumes = ResumeResult.count(db)
    processed_resumes = ResumeResult.count_processed(db)
    average_score = ResumeResult.get_average_score(db)
    
    return jsonify({
        "totalJobs": total_jobs,
        "totalResumes": total_resumes,
        "processedResumes": processed_resumes,
        "averageScore": average_score
    })

@bp.route('/score-breakdown/<result_id>', methods=['GET'])
def get_score_breakdown(result_id):
    """Get detailed score breakdown for a specific resume result"""
    db = current_app.config["db"]
    
    result = ResumeResult.get_by_id(db, result_id)
    if not result:
        return jsonify({"error": "Result not found"}), 404
    
    # Check if score breakdown exists
    if 'scoreBreakdown' not in result:
        return jsonify({"error": "Score breakdown not available for this result"}), 404
    
    # Serialize the result before returning
    serialized_result = serialize_doc(result)
    
    return jsonify({
        "result": serialized_result,
        "scoreBreakdown": serialized_result.get('scoreBreakdown')
    })