import re
import time
import schedule
import json
import os
import base64
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from googleapiclient.discovery import build
from auth import authenticate_gmail
from final import extract_event_details, extract_date, extract_topic, extract_time, extract_venue, predict, extract_links

FETCHED_IDS_FILE = "fetched_ids.json"
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'xdrtyu',
    'database': 'campus_vibes'
}

def load_fetched_ids():
    if os.path.exists(FETCHED_IDS_FILE):
        try:
            with open(FETCHED_IDS_FILE, "r") as file:
                return set(json.load(file))
        except (json.JSONDecodeError, FileNotFoundError):
            return set()
    return set()

def save_fetched_ids(ids):
    with open(FETCHED_IDS_FILE, "w") as file:
        json.dump(list(ids), file)

fetched_ids = load_fetched_ids()

def create_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def clean_email_body(body):
    lines = body.splitlines()
    cleaned_lines = []
    date_header_removed = False
    
    for line in lines:
        if not date_header_removed and line.strip().startswith('date:'):
            date_header_removed = True
            continue
        cleaned_lines.append(line)
    
    cleaned_body = '\n'.join(cleaned_lines)
    cleaned_body = re.sub(r'^(From|To|Subject):.*$', '', cleaned_body, flags=re.MULTILINE)
    cleaned_body = re.sub(r'\n{3,}', '\n\n', cleaned_body).strip()
    
    return cleaned_body

def get_club_id(sender_email):
    if not sender_email:
        return None
        
    email_match = re.search(r'<(.+?)>', sender_email)
    if email_match:
        sender_email = email_match.group(1)
    
    club_mapping = {
        'wildbeats@iiitkottayam.ac.in': 1001,
        'trendles@iiitkottayam.ac.in': 1002,
        'mindquest@iiitkottayam.ac.in': 1003,
        'sports@iiitkottayam.ac.in': 1004,
        'techclub@iiitkottayam.ac.in': 1005,
        'gdsc@iiitkottayam.ac.in': 1006,
        'csyclub@iiitkottayam.ac.in': 1007,
        'enigma@iiitkottayam.ac.in': 1008,
        'elix@iiitkottayam.ac.in': 1009,
        'abrahamthomas1002@gmail.com': 1010
    }
    
    sender_email_lower = sender_email.lower()
    for email, club_id in club_mapping.items():
        if email.lower() in sender_email_lower:
            return club_id

    return None

def get_primary_link(links):
    if not links:
        return None
        
    priority_order = [
        'registration',
        'register',
        'signup',
        'rsvp',
        'form',
        'link'
    ]
    
    lower_links = {k.lower(): v for k, v in links.items()}
    
    for keyword in priority_order:
        for link_text, url in lower_links.items():
            if keyword in link_text:
                return url
                
    return next(iter(links.values())) if links else None

def process_email(msg_id, service):
    if msg_id in fetched_ids:
        return None

    msg_data = service.users().messages().get(userId="me", id=msg_id).execute()
    payload = msg_data["payload"]
    headers = payload["headers"]

    subject = None
    sender = None
    for header in headers:
        if header["name"] == "Subject":
            subject = header["value"]
        if header["name"] == "From":
            sender = header["value"]

    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                body_data = part["body"].get("data", "")
                body = base64.urlsafe_b64decode(body_data).decode("utf-8")
                print(body)
                body = clean_email_body(body)

    event_details = extract_event_details(subject)
    dates = extract_date(body)
    times = extract_time(body)
    place = extract_venue(body)
    links = extract_links(body)
    topic = extract_topic(body)
    print(body)
    speaker = predict(body, event_details.get('event_name', ''))

    club_id = get_club_id(sender)
    if club_id is None:
        print(f"Skipping email from unknown sender: {sender}")
        return None

    event_name = event_details.get('event_name', '')
    if not event_name or event_name.lower() == 'unnamed event':
        event_name = subject 
    
    if not event_name:
        print("Skipping email with no event name or subject")
        return None

    event_data = {
        "Club_ID": club_id,
        "Event_Name": event_name[:100],
        "Location": place[:100] if place else None,
        "Speaker": speaker[0][:100] if speaker else None,
        "Link": str(links) if links else None,
        "Topic": topic if topic else None,
        "Description": event_details.get('event_description', '')[:255],
        "Date": dates if dates else None,
        "Time": times if times else None
    }
    

    db_record = {k: v for k, v in event_data.items() if v is not None}

    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            columns = ', '.join(db_record.keys())
            placeholders = ', '.join(['%s'] * len(db_record))
            
            query = f"""
            INSERT INTO event
            ({columns})
            VALUES ({placeholders})
            """
            cursor.execute(query, tuple(db_record.values()))
            connection.commit()
            
            cursor.execute("SELECT LAST_INSERT_ID()")
            event_id = cursor.fetchone()[0]
            event_data["Event_ID"] = event_id
            
            print(f"Successfully inserted event ID {event_id}: {event_data['Event_Name']}")
        except Error as e:
            print(f"Error inserting into database: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    fetched_ids.add(msg_id)
    save_fetched_ids(fetched_ids)

    return {
        "From": sender,
        "Dates": dates,
        "Links": links,
        "Times": times,
        "Venue": place,
        "Topic": topic,
        "Speaker": speaker,
        "Event": event_details,
        "DB_Record": event_data
    }

def fetch_emails():
    try:
        creds = authenticate_gmail()
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(userId="me", q="-category:promotions", maxResults=5).execute()
        messages = results.get("messages", [])
        
        while 'nextPageToken' in results:
            results = service.users().messages().list(userId="me", q="-category:promotions", pageToken=results['nextPageToken'], maxResults=5).execute()
            messages.extend(results.get("messages", []))

        messages.reverse()

        for msg in messages:
            msg_id = msg["id"]
            event_info = process_email(msg_id, service)
            
            if event_info:
                print("\nProcessed Event Information:")
                print(f"From: {event_info['From']}")
                print(f"Event: {event_info['Event']}")
                print(f"Dates: {event_info['Dates']}")
                print(f"Links: {event_info['Links']}")
                print(f"Times: {event_info['Times']}")
                print(f"Venue: {event_info['Venue']}")
                print(f"Topic: {event_info['Topic']}")
                print(f"Speaker: {event_info['Speaker']}")
                print("\nDatabase Record:")
                print(json.dumps(event_info['DB_Record'], indent=2, default=str))

    except Exception as e:
        print(f"Error fetching emails: {e}")

schedule.every(1).seconds.do(fetch_emails)

if __name__ == "__main__":
    print("Starting email event processor")
    while True:
        schedule.run_pending()
        time.sleep(1)