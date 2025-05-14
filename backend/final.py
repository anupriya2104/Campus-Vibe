import re
from dateparser import parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from transformers import pipeline

event_extractor = pipeline(
    "text2text-generation",
    model="google/flan-t5-small",
    device=-1
)

def extract_structured_bullets(text: str) -> Dict[str, str]:
    structured_bullets = re.findall(
        r'-\s+\*([A-Za-z ]+)\*\s*:\s*([^\n]+)',
        text
    )
    
    results = {}
    for field, value in structured_bullets:
        field_lower = field.lower().strip()
        value_clean = value.strip()
        
        if field_lower == 'speaker' and value_clean:
            results['speaker'] = value_clean
        elif field_lower == 'topic' and value_clean:
            results['topic'] = value_clean
        elif field_lower == 'venue' and value_clean:
            results['venue'] = value_clean
        elif field_lower == 'time' and value_clean:
            results['time'] = value_clean
        elif field_lower == 'date' and value_clean:
            results['date'] = value_clean
    
    return results

def clean_event_name(raw_name: str) -> str:
    if re.match(r'^[A-Z]{1,3}\d{1,4}$', raw_name):
        return "Unnamed Event"
    
    location_indicators = {
        'room', 'hall', 'building', 'center', 'centre', 'lab',
        'theater', 'theatre', 'auditorium', 'campus', 'floor', 'mess'
    }
    lower_name = raw_name.lower()
    if any(indicator in lower_name for indicator in location_indicators):
        return "Unnamed Event"
    
    raw_words = raw_name.strip().split()
    has_capitalized = any(w[0].isupper() for w in raw_words if len(w) > 1)
    
    if len(raw_words) > 1 and has_capitalized:
        return raw_name.strip()
    
    clean = re.split(r'(?:\bon\b|\bat\b|\sfrom\s|,|;|-)', raw_name, maxsplit=1)[0].strip()
    clean = re.sub(r'\s*(?:to|will|the|a|for|by|of|on|at|p\.?s\.?)\s*$', '', clean, flags=re.I)
    
    cleaned_words = clean.split()
    if len(cleaned_words) > 1 and any(w[0].isupper() for w in cleaned_words):
        return clean
    
    return "Unnamed Event"

def extract_cultural_event(text: str) -> Optional[str]:
    patterns = [
        r'(?:celebrat|observ|invit|join).*?\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Puja|Pooja|Celebration|Festival|Utsav))',
        r'\b([A-Z][a-z]+\s+(?:Puja|Pooja|Utsav))\b',
        r'\b(?:Special\s+)?([A-Z][a-z]+\s+Celebration)\b'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_event_name(match.group(1))
    return None

def transformer_extract_event(email_body: str) -> str:
    cultural_event = extract_cultural_event(email_body)
    if cultural_event:
        return cultural_event
        
    prompt = f"""Extract ONLY the full official event name from this email. 
    Return the COMPLETE name, even if it contains technical terms or is long.
    Preserve capitalization and exact wording
    Email: "{email_body[:1000]}"
    Event name: """
    
    try:
        result = event_extractor(
            prompt,
            max_length=50,
            num_beams=3,
            do_sample=False,
            early_stopping=True
        )[0]['generated_text']
        return clean_event_name(result)
    except:
        return "Unnamed Event"

def regex_extract_event(text: str) -> str:
    if cultural_event := extract_cultural_event(text):
        return cultural_event
    
    screening_match = re.search(
        r'screening\s+(?:of\s+)?([^.!?]+?(?:episodes?|movies?|films?)[^.!?]+)',
        text, 
        re.IGNORECASE
    )
    if screening_match:
        return clean_event_name(screening_match.group(1))
    
    venue_phrases = re.findall(r'(?:Where|Venue|Location)\s*[:\?]\s*([^\n]+)', text, re.I)
    venue_words = {word for phrase in venue_phrases for word in phrase.strip().split()}
    
    location_indicators = {
        'room', 'hall', 'building', 'center', 'centre', 'lab', 
        'theater', 'theatre', 'auditorium', 'campus', 'floor'
    }
    venue_words.update(location_indicators)
    
    pattern = r'''
        (?:^|\s)  
        (
            (?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)+)  
            |
            (?:[A-Z][A-Za-z0-9]+\s+[A-Z][A-Za-z0-9]+) 
        )
        (?=\s|$|[.,;:!?)])  
    '''
    
    candidates = [
        match.group(1).strip() 
        for match in re.finditer(pattern, text, re.VERBOSE)
        if not any(
            word.lower() in match.group(1).lower() 
            for word in venue_words
        )
    ]
    
    if candidates:
        longest_candidate = max(candidates, key=len)
        return re.sub(r'\s*[.,;:!?)]*$', '', longest_candidate).strip()
    
    return "Unnamed Event"

def extract_event_details(email_body: str) -> Dict[str, str]:
    clean_text = ' '.join(email_body.split()[:500])
    
    cultural_event = extract_cultural_event(clean_text)
    if cultural_event:
        return {
            'event_name': cultural_event
        }
    
    venue_names = set()
    venue = extract_venue(clean_text)
    if venue:
        venue_names.update(venue.split())
    
    event_name = transformer_extract_event(clean_text)
    
    if (event_name == "Unnamed Event" or 
        any(venue_word.lower() in event_name.lower() for venue_word in venue_names)):
        event_name = regex_extract_event(clean_text)
    
    if any(venue_word.lower() in event_name.lower() for venue_word in venue_names):
        event_name = "Unnamed Event"
    
    return {
        'event_name': event_name
    }

def remove_event_name(text: str, event_name: str) -> str:
    if not event_name or event_name == "Unnamed Event":
        return text
    
    pattern = re.compile(re.escape(event_name), re.IGNORECASE)
    return pattern.sub("", text)

def is_proper_name(text: str) -> bool:
    if len(text) < 2:
        return False
    
    excluded_terms = {
        'uncover', 'join', 'attend', 'learn', 'discover', 'explore',
        'register', 'participate', 'submit', 'pumped', 'hey', 'there',
        'welcome', 'hello', 'hi', 'dear', 'thanks', 'regards',
        "we're", "i'm", "you're", "they're", "he's", "she's", "it's",
        "we", "i", "you", "they", "he", "she", "it"
    }
    if any(term == text.lower() for term in excluded_terms):
        return False
    
    if "'" in text:
        return False
    
    words = text.split()
    if len(words) > 1 and not all(w[0].isupper() for w in words if w):
        return False
    
    generic_terms = {
        'exam', 'exams', 'test', 'tests', 'meeting', 'event',
        'announcement', 'notification', 'deadline', 'assignment',
        'team', 'club', 'committee', 'department'
    }
    if any(word.lower() in generic_terms for word in words):
        return False
    
    titles = {'Dr.', 'Prof.', 'Mr.', 'Mrs.', 'Ms.', 'PhD', 'M.Tech', 'B.Tech'}
    if any(word in titles for word in words):
        return len(words) > 1
    
    if text.isupper():
        return len(text) <= 3 and '.' not in text
    
    return text[0].isupper()

def predict(text: str, current_event_name: str = None) -> List[str]:
    text = re.sub(r'^\s*(Dear|Hello|Hi)\s+[^,\n]+,?\s*', '', text, flags=re.IGNORECASE)
    
    if current_event_name:
        text = remove_event_name(text, current_event_name)
    
    structured_data = extract_structured_bullets(text)
    if 'speaker' in structured_data:
        speaker = structured_data['speaker']
        if is_proper_name(speaker):
            return [speaker.strip(', *')]
    
    bullet_speaker = re.search(
        r'-\s*\*?Speaker\*?\s*:\s*\*([^\n*]+)\*',
        text, 
        re.IGNORECASE
    )
    if bullet_speaker:
        speaker = bullet_speaker.group(1).strip()
        if is_proper_name(speaker):
            return [speaker.strip(', *')]

    speaker_patterns = [
        r'(?:Speaker|Presented by|By|Talk by|Keynote by)\s*[:\-]\s*((?:Mr\.|Mrs\.|Ms\.|Prof\.|Dr\.)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'(?:Speaker|Presented by|By|Talk by|Keynote by)\s*[:\-]\s*((?:Mr\.|Mrs\.|Ms\.|Prof\.|Dr\.)\s*[A-Z]+(?:\s+[A-Z]+)*)',
        r'\b(?:by|from)\s+((?:Mr\.|Mrs\.|Ms\.|Prof\.|Dr\.)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
    ]
    
    for pattern in speaker_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            speaker = match.group(1).strip()
            if is_proper_name(speaker):
                return [speaker.strip(', *')]
    
    signature_match = re.search(
        r'(?:Regards|Thanks|From)[,\s]+([A-Z][a-zA-Z\s]+Team\b|[A-Z][a-zA-Z\s]+Club\b)',
        text,
        re.IGNORECASE
    )
    if signature_match:
        return []

    return []

def extract_time(text):
    def extract_first_time(time_str):
        range_match = re.search(
            r'(\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?)\s*(?:to|-|–)\s*(?:[01]?\d|2[0-3])(?::[0-5]\d)?(\s*[APap][Mm]\b)', 
            time_str, 
            re.IGNORECASE
        )
        
        if range_match:
            time_part = range_match.group(1)
            period_part = range_match.group(2) or ''
            
            time_part = time_part.replace('.', ':')
            combined = (time_part + period_part).replace(' ', '').upper()
            
            if ':' not in time_part and any(p in combined for p in ['AM', 'PM']):
                combined = time_part + ':00' + period_part
                combined = combined.replace(' ', '').upper()
            
            return combined
        
        standalone_match = re.search(
            r'\b(?:[01]?\d|2[0-3])(?:[:.][0-5]\d)?(?:\s*[APap][Mm]\b)?',
            time_str,
            re.IGNORECASE
        )
        
        if standalone_match:
            time_part = standalone_match.group(0)
            time_part = time_part.replace('.', ':')
            time_part = time_part.replace(' ', '').upper()
            
            if ':' not in time_part and any(p in time_part for p in ['AM', 'PM']):
                time_part = time_part.replace('AM', ':00AM').replace('PM', ':00PM')
            
            return time_part
        
        return None

    time_match = re.search(r'(?:Time|Timing)\s*:\s*([^\n]+)', text, re.IGNORECASE)
    if time_match:
        result = extract_first_time(time_match.group(1).strip())
        if result:
            return 'NIL' if result == '0' else result
    
    structured_data = extract_structured_bullets(text) if 'extract_structured_bullets' in globals() else {}
    if 'time' in structured_data:
        result = extract_first_time(structured_data['time'])
        if result:
            return 'NIL' if result == '0' else result
    
    time_pattern = r'''
        (?:[01]?\d|2[0-3])        
        (?::[0-5]\d)?               
        (?:\s*[APap][Mm]\b)?        
        (?:\s*(?:to|-|–)\s*         
        (?:[01]?\d|2[0-3])           
        (?::[0-5]\d)?                
        (?:\s*[APap][Mm]\b)?)?       
    '''
    
    try:
        matches = re.finditer(time_pattern, text, re.VERBOSE | re.IGNORECASE)
        for match in matches:
            result = extract_first_time(match.group(0))
            if result:
                return 'NIL' if result == '0' else result
        return None
    
    except Exception as e:
        return None

def get_day_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return 'th'
    else:
        return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')

def extract_date(text: str) -> str | None:
    structured_data = extract_structured_bullets(text)
    if 'date' in structured_data:
        date_str = structured_data['date']
        parsed_date = parse(date_str, settings={'PREFER_DATES_FROM': 'future'})
        if parsed_date:
            day = parsed_date.day
            suffix = get_day_suffix(day)
            return parsed_date.strftime(f"%d{suffix} %B %Y")
    
    weekday_match = re.search(
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*,\s*'
        r'(\d{1,2}(?:st|nd|rd|th)?\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December))',
        text, 
        re.IGNORECASE
    )
    if weekday_match:
        day = re.sub(r'\D', '', weekday_match.group(1).split()[0])
        month = weekday_match.group(2)
        year = datetime.now().year
        suffix = get_day_suffix(int(day))
        return f"{day}{suffix} {month.capitalize()} {year}"

    month_match = re.search(
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|'
        r'August|September|October|November|December)\s+\d{4})',
        text, 
        re.IGNORECASE
    )
    if month_match:
        full_date = month_match.group(1)
        day = re.sub(r'\D', '', full_date.split()[0])
        month = month_match.group(2)
        year = re.search(r'\d{4}', full_date).group()
        suffix = get_day_suffix(int(day))
        return f"{day}{suffix} {month.capitalize()} {year}"

    when_match = re.search(r'(?:When|Date)\s*[:\?]\s*([^\n]+)', text, re.IGNORECASE)
    if when_match:
        when_text = when_match.group(1).strip()
        parsed_date = parse(when_text, settings={'PREFER_DATES_FROM': 'future'})
        if parsed_date:
            day = parsed_date.day
            suffix = get_day_suffix(day)
            return parsed_date.strftime(f"%d{suffix} %B %Y")

    time_phrase_match = re.search(
        r'\b(this evening|tonight|this morning)\b', 
        text, 
        re.IGNORECASE
    )
    if time_phrase_match:
        today = datetime.today()
        day = today.day
        suffix = get_day_suffix(day)
        return today.strftime(f"%d{suffix} %B %Y")

    if re.search(r'\btoday\b', text, re.IGNORECASE):
        today = datetime.today()
        day = today.day
        suffix = get_day_suffix(day)
        return today.strftime(f"%d{suffix} %B %Y")

    if re.search(r'\btomorrow\b', text, re.IGNORECASE):
        tomorrow = datetime.today() + timedelta(days=1)
        day = tomorrow.day
        suffix = get_day_suffix(day)
        return tomorrow.strftime(f"%d{suffix} %B %Y")

    date_range_match = re.search(
        r'(?:Dates?|🗓)\s*:\s*([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{1,2}(?:st|nd|rd|th)?)*(?:\s+and\s+\d{1,2}(?:st|nd|rd|th)?)?)',
        text, 
        re.IGNORECASE
    )
    if not date_range_match:
        date_range_match = re.search(
            r'([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{1,2}(?:st|nd|rd|th)?)*(?:\s+and\s+\d{1,2}(?:st|nd|rd|th)?))',
            text, 
            re.IGNORECASE
        )
    
    if date_range_match:
        date_str = date_range_match.group(1)
        first_date = re.search(r'([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)', date_str)
        if first_date:
            date_str = first_date.group(1)
            current_year = datetime.now().year
            parsed_date = parse(f"{date_str} {current_year}")
            if parsed_date:
                day = parsed_date.day
                suffix = get_day_suffix(day)
                return parsed_date.strftime(f"%d{suffix} %B %Y")

    date_pattern = r"""
        \b(?P<dmy>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b|
        \b(?P<ymd>\d{4}-\d{1,2}-\d{1,2})\b|
        \b(?P<word>\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})\b|
        \b(?P<word_comma>[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})\b
    """
    match = re.search(date_pattern, text, re.VERBOSE | re.IGNORECASE)
    if match:
        matched_date = next(g for g in match.groups() if g)
        matched_date = re.sub(r'(\d)(st|nd|rd|th)\b', r'\1', matched_date)
        parsed_date = parse(matched_date, settings={'PREFER_DATES_FROM': 'future'})
        if parsed_date:
            day = parsed_date.day
            suffix = get_day_suffix(day)
            return parsed_date.strftime(f"%d{suffix} %B %Y")

    return None

def extract_topic(text):
    pattern = re.compile(
        r'(?:^|\n)\s*[-*]?\s*\*?Topic\*?\s*:\s*'  
        r'([^\n]+'                                
        r'(?:\n\s+(?!\s*[-*]\s*\*?(?:Speaker|Date|Time|Venue)\*?\s*:)[^\n*]+)*)',
        re.IGNORECASE
    )
    
    match = pattern.search(text)
    if match:
        topic = match.group(1)
        topic = re.sub(r'\n\s*', ' ', topic)  
        topic = re.sub(r'\s+', ' ', topic)
        topic = re.sub(r'\*', '', topic)  
        return topic.strip()
    
    return None

def extract_venue(text):
    structured_data = extract_structured_bullets(text)
    if structured_data and 'venue' in structured_data:
        return structured_data['venue']
    
    room_match = re.search(
        r'\b([A-Z]{1,5}[-\s]?\d{1,5}[A-Z]?)\b',  
        text
    )
    if room_match:
        room = re.sub(r'[-\s]', '', room_match.group(1))
        return room
    
    venue_match = re.search(
        r'(?:Venue|Location|Place)\s*[:-]\s*([^\n]+)',
        text,
        re.IGNORECASE
    )
    if venue_match:
        raw_venue = venue_match.group(1).strip()
        clean_venue = re.sub(r'[^\w\s-]', '', raw_venue).strip()
        
        if re.search(r'\bSc\s*ops\b', clean_venue, re.IGNORECASE):
            return 'Sccoops area'
        return clean_venue
    
    area_match = re.search(
        r'\b(?:in|at)\s+(?:the\s+)?([A-Z][a-zA-Z0-9\s-]+?(?:area|room|hall|theater|lab|building))\b',
        text,
        re.IGNORECASE
    )
    if area_match:
        raw_venue = area_match.group(1).strip()
        clean_venue = re.sub(r'[^\w\s-]', '', raw_venue).strip()
        
        if re.search(r'\bSc\s*ops\b', clean_venue, re.IGNORECASE):
            return 'Sccoops area'
        return clean_venue
    
    return None

def extract_links(text: str) -> Dict[str, List[str]]:
    text = re.sub(r'(https?://[^\s]+)\s+([^\s]+)', r'\1\2', text)
    
    closing_phrases = r"(regards|cheers|thank you|thanks|sincerely|best wishes)[\s\S]*$"
    truncated_text = re.sub(closing_phrases, "", text, flags=re.IGNORECASE)

    url_pattern = r'(?<!@)(?:https?://|www\.)[^\s<>"\']+\.(?:ac\.in|edu|org)[^\s<>"\']*'

    context_patterns = {
        "Registration": r'(?:register|sign\s*up|registration|rsvp|join|participate|last\s*day\s*to\s*register)\b[\s\S]*?(?:here|link|at)?\s*[:=]?\s*({})'.format(url_pattern),
        "Photo Album": r'(?:album|photos?|pictures?|gallery)\b[\s\S]*?(?:here|link)?\s*[:=]?\s*({})'.format(url_pattern),
        "Social Media": r'(?:\binstagram\b|\bfb\b|\bfacebook\b|\btwitter\b|\bx\b|\blinkedin\b|\bsocial\s*media\b)\b[\s\S]*?(?:here|profile|page)?\s*[:=]?\s*({})'.format(url_pattern),
        "Contact": r'(?:\bcontact\b|\breach\s*out\b|\bwhatsapp\b|\bcall\b|\bphone\b|\bmobile\b|\bnumber\b)\b[\s\S]*?(?:here|us|at)?\s*[:=]?\s*({})'.format(url_pattern),
        "Event/Official Link": r'(?:event|official|website|college|iiit|valentine|enigma)\b[\s\S]*?(?:here|link|visit)?\s*[:=]?\s*({})'.format(url_pattern),
    }

    extracted_links = {key: [] for key in context_patterns.keys()}
    matched_urls = set()

    for link_type, pattern in context_patterns.items():
        matches = re.findall(pattern, truncated_text, re.IGNORECASE)
        for url in matches:
            clean_url = url.strip().rstrip('.,;:!?-')
            if clean_url not in matched_urls:
                extracted_links[link_type].append(clean_url)
                matched_urls.add(clean_url)

    academic_urls = re.findall(r'https?://[^\s<>"\']+\.(?:ac\.in|edu|org)[^\s<>"\']*', truncated_text, re.IGNORECASE)
    for url in academic_urls:
        clean_url = url.strip().rstrip('.,;:!?-')
        if clean_url not in matched_urls:
            extracted_links["Event/Official Link"].append(clean_url)
            matched_urls.add(clean_url)

    all_urls = re.findall(r'(?<!@)(?:https?://|www\.)[^\s<>"\']+', truncated_text, re.IGNORECASE)
    other_urls = [
        url.strip().rstrip('.,;:!?-')
        for url in all_urls
        if url.strip().rstrip('.,;:!?-') not in matched_urls
    ]
    if other_urls:
        extracted_links["Other Links"] = other_urls

    return {k: v for k, v in extracted_links.items() if v}

def similar_text(text1: str, text2: str) -> bool:
    return text1.lower() in text2.lower() or text2.lower() in text1.lower()
