import os
import sys
import logging
import argparse
from improved_routes import extract_text_from_pdf, extract_text_from_docx, extract_name, extract_contact_info, extract_skills

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

def test_pdf_extraction(file_path):
    """Test PDF text extraction and information parsing"""
    logger.info(f"Testing PDF extraction on: {file_path}")
    
    # Extract text
    text = extract_text_from_pdf(file_path)
    
    if not text:
        logger.error("Failed to extract any text from the PDF")
        return False
    
    logger.info(f"Successfully extracted {len(text)} characters")
    logger.info(f"Text preview: {text[:200].replace(chr(10), ' ')}...")
    
    # Extract information
    name = extract_name(text)
    email, phone = extract_contact_info(text)
    skills = extract_skills(text)
    
    # Print results
    logger.info(f"Extracted Name: {name}")
    logger.info(f"Extracted Email: {email}")
    logger.info(f"Extracted Phone: {phone}")
    logger.info(f"Extracted Skills: {', '.join(skills)}")
    
    return True

def test_docx_extraction(file_path):
    """Test DOCX text extraction and information parsing"""
    logger.info(f"Testing DOCX extraction on: {file_path}")
    
    # Extract text
    text = extract_text_from_docx(file_path)
    
    if not text:
        logger.error("Failed to extract any text from the DOCX")
        return False
    
    logger.info(f"Successfully extracted {len(text)} characters")
    logger.info(f"Text preview: {text[:200].replace(chr(10), ' ')}...")
    
    # Extract information
    name = extract_name(text)
    email, phone = extract_contact_info(text)
    skills = extract_skills(text)
    
    # Print results
    logger.info(f"Extracted Name: {name}")
    logger.info(f"Extracted Email: {email}")
    logger.info(f"Extracted Phone: {phone}")
    logger.info(f"Extracted Skills: {', '.join(skills)}")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test PDF/DOCX extraction')
    parser.add_argument('file_path', help='Path to the PDF or DOCX file to test')
    args = parser.parse_args()
    
    file_path = args.file_path
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    
    if file_path.lower().endswith('.pdf'):
        success = test_pdf_extraction(file_path)
    elif file_path.lower().endswith('.docx'):
        success = test_docx_extraction(file_path)
    else:
        logger.error(f"Unsupported file type: {file_path}")
        sys.exit(1)
    
    if success:
        logger.info("Extraction test completed successfully")
    else:
        logger.error("Extraction test failed")
        sys.exit(1)

