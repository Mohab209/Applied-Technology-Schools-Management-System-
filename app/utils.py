import re

def normalize_arabic(text: str) -> str:
    """تجريد وتوحيد الحروف والهمزات والتشكيل للغة العربية"""
    if not text:
        return ""
        
    text = re.sub(r'[\u064B-\u0652]', '', text)
    replacements = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
        'ى': 'ي',
        'ة': 'ه',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
        
    return text.strip()