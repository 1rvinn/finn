from simplegmail import Gmail 
from notion_client import Client
import os
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv
import ollama
import json
import re

# gmail auth
gmail = Gmail()

# groq api key
load_dotenv()  # Load .env file
API_KEY = os.getenv("GROQ_API_KEY")
print(API_KEY)

# notion page and token details
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
print(NOTION_TOKEN)
DATABASE_ID = os.getenv("DATABASE_ID")
print(DATABASE_ID)
headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# last run details
LAST_RUN_FILE = "last_run.txt"
# extracts last run time, if not found then defaults to 7 days ago
def get_last_run_time():
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, "r") as file:
            timestamp = file.read().strip()
            if timestamp:
                try:
                    return datetime.fromisoformat(timestamp)
                except ValueError:
                    print("invalid. defaulting to 7 days ago")
    return datetime.now(timezone.utc) - timedelta(days=7)

def update_last_run_time():
    with open(LAST_RUN_FILE, "w") as file:
        file.write(datetime.now(timezone.utc).isoformat())

# gets emails using the simplegmail library
def get_emails_from_sender(sender_email, subjects=None, after=None, before=None):
    query = f'from:{sender_email}'
    if after:
        query += f' after:{after}'
    if before:
        query += f' before:{before}'
    if subjects:
        subjects_query = ' OR '.join(f'subject:"{subject}"' for subject in subjects)
        query += f' ({subjects_query})'
    messages = gmail.get_messages(query=query)
    
    email_data = []
    for message in messages:
        full_body = message.plain if message.plain else message.snippet if message.snippet else ""
        relevant_body = extract_relevant_part(full_body)
        email_data.append({
            'Subject': message.subject,
            'From': message.sender,
            'Date': message.date,
            'Body': relevant_body
        })
    return email_data

# reduces the size of email content by omitting the footer
def extract_relevant_part(full_body):
    delimiter = "For any concerns regarding this transaction, please contact"
    if delimiter in full_body:
        return full_body.split(delimiter)[0].strip()
    return full_body.strip()

# saves the transaction to notion
def save_transaction_to_notion(transaction_details):
    published_date = datetime.now().astimezone(timezone.utc).isoformat()
    properties = {
        "Date": {"date": {"start": transaction_details["date"]}},
        "Time": {"rich_text": [{"text": {"content": transaction_details["time"]}}]},  
        "Recipient": {"rich_text": [{"text": {"content": transaction_details["recipient"]}}]},  
        "Type": {"title": [{"text": {"content": transaction_details["type"]}}]},  
        "Amount": {"number": float(transaction_details["amount"])},  
        "Category": {"rich_text": [{"text": {"content": transaction_details["category"]}}]}  
    }
    create_url = "https://api.notion.com/v1/pages"
    payload = {"parent": {"database_id": DATABASE_ID}, "properties": properties}
    res = requests.post(create_url, headers=headers, json=payload)
    print(res.status_code)
    if res.status_code != 200:
        print("Response:", res.json())
    return res


def analyze_email_content(email_body, categories):
    prompt = f"""
    Extract the following details from the given email content containing details about a transaction and return the result in JSON format:
    - Date of transaction (format: DD/MM/YYYY)
    - Time (format: HH:MM:SS)
    - Recipient (extract name from 'Info-'. Output only the **name of the receiving entity** not the upi transaction details.)
    - Type of transaction (credit or debit only)
    - Amount (decimal value, add '-' for debit, '+' for credit, no symbols)
    - Category (from provided list: {', '.join(f'{key}: {value}' for key, value in categories.items())})
        note: if recipient 'isthara' or 'vendify', put category as food
    
    **Ensure the output follows this exact JSON format:**
    {{
        "date": "<DD/MM/YYYY>",
        "time": "<HH:MM:SS>",
        "recipient": "<name>",
        "type": "<credit/debit>",
        "amount": "<amount>",
        "category": "<category>"
    }}
    For Example:
    {{
        "date": "05/06/2024>",
        "time": "15:11:36",
        "recipient": "Vendify",
        "type": "debit",
        "amount": "-100",
        "category": "Food"
    }}
    
    - **Give only the json as output, nothing before or after the json.**
    - **The format should be exactly the same. Ensure perfect formatting of the date, time etc.**
    """
    response = ollama.chat(
        model="llama3.2", 
        messages=[
            {"role": "system", "content": f"You are a helpful financial assistant. {prompt}"},
            {"role": "user", "content": email_body}
        ]
    )
    
    return response["message"]["content"]

def extract_json(text):
    """Extracts and sanitizes valid json from the response."""
    
    # Find JSON object using regex (handles multiline JSON)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        print("No JSON object found in response.")
        return None
    
    json_str = match.group(0)
    
    # Remove trailing commas before closing braces or brackets
    json_str = re.sub(r",\s*}", "}", json_str)  # Remove trailing commas before closing curly brace
    json_str = re.sub(r",\s*\]", "]", json_str)  # Remove trailing commas before closing square bracket

    # Attempt to parse JSON
    try:
        parsed_json = json.loads(json_str)
        return parsed_json
    except json.JSONDecodeError as e:
        print(f"JSON Parsing Error: {e}")
        print(f"Sanitized JSON:\n{json_str}")
        return None

def chatbot_interface(data):
    print("Welcome to finn - your financial assistant. Ask anything about your finances here. Type 'exit' to quit.")

    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        messages = [
            {"role": "system", "content": f"You are a helpful financial assistant capable of processing queries about an individual's transactions. The transaction data is as follows: {data}"},
            {"role": "user", "content": user_input}
        ]

        try:
            response = ollama.chat(
                model="llama3",
                messages=messages,
                temperature=0.7,
                max_tokens=256,
                top_p=1
            )
            
            response_text = response["message"]["content"] if "message" in response else "I'm sorry, I couldn't understand your request."
            print(f"finn: {response_text}")
        
        except Exception as e:
            print(f"Error with chatbot processing: {e}")

def main():
    last_run_time = get_last_run_time()
    print(f"Last execution time: {last_run_time}")

    after_date = last_run_time.strftime("%Y/%m/%d")
    before_date = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    print(f"Processing emails from {after_date} to {before_date}")
    categories_dict = {
        'Food': 'Receipt from restaurant/food purchase', 
        'Travel': 'Travel-related expenses', 
        'Software': 'Software purchase/subscription', 
        'Personal': 'Transaction with a friend/relative', 
        'Subscription': 'Online subscription - music, streaming, etc',
        'Laundry': 'Money spent on laundry shops like Wash Door',
        'Shopping': 'E-commerce, retail shops, quick commerce'
    }
    sender_email = "alerts@axisbank.com"
    #after_date = input('after date (Format: YYYY/MM/DD): ')
    #before_date = input('before date (Format: YYYY/MM/DD): ')
    subjects = ["Debit notification from Axis Bank", "Credit notification from Axis Bank"] 
    emails = get_emails_from_sender(sender_email, subjects, after_date, before_date)
    print(emails)
    model_name = "llama3.2"
    pull_status = os.system(f"ollama pull {model_name}")
    if pull_status != 0:
        print(f"Failed to pull model '{model_name}'. Ensure that ollama is installed and configured correctly.")

    if emails:
        for email in emails:
            email_body = email['Body']
            transaction_details_json = analyze_email_content(email_body, categories_dict)
            print("transaction details:"+transaction_details_json)
            
            if transaction_details_json is None:
                continue 
            try:
                transaction_details = json.loads(transaction_details_json)
                transaction_details['date'] = datetime.strptime(transaction_details['date'], "%d/%m/%Y").date().isoformat()
                save_transaction_to_notion(transaction_details)
                print(f"Transaction Details:\n{transaction_details}")
                print("="*50)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Raw response: {transaction_details_json}")
        update_last_run_time()
        print("Categorized emails saved to notion.")
        chatbot_interface(transaction_details)
    else:
        print(f'No emails found from {sender_email} with subjects {", ".join(subjects)}.')

if __name__ == '__main__':
    main()