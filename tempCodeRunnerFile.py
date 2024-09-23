from simplegmail import Gmail
import csv

# Authenticate and create the Gmail service
gmail = Gmail()

def get_emails_from_sender(sender_email, subjects=None, after=None, before=None):
    query = f'from:{sender_email}'
    if after:
        query += f' after:{after}'
    if before:
        query += f' before:{before}'
    if subjects:
        subjects_query = ' OR '.join(f'subject:"{subject}"' for subject in subjects)
        query += f' ({subjects_query})'
    print(query)
    # Search for emails from the specific sender
    messages = gmail.get_messages(query=query)
    
    email_data = []
    for message in messages:
        full_body = message.plain if message.plain else message.snippet if message.snippet else ""
        # Extract the relevant part of the email body
        relevant_body = extract_relevant_part(full_body)
        email_data.append({
            'Subject': message.subject,
            'From': message.sender,
            'Date': message.date,
            'Body': relevant_body
        })
    
    return email_data

def extract_relevant_part(full_body):
    """Extract the relevant part of the email body before the system-generated notice."""
    delimiter = "For any concerns regarding this transaction, please contact"
    if delimiter in full_body:
        return full_body.split(delimiter)[0].strip()
    return full_body.strip()

def save_emails_to_csv(email_data, filename='emails.csv'):
    """Save the email data to a CSV file."""
    # Define the CSV column names
    fieldnames = ['Subject', 'From', 'Date', 'Body']
    
    # Write the email data to a CSV file
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(email_data)

def save_transaction_details(transaction_details, filename='categorized_emails.csv'):
    """Save the transaction details to a CSV file."""
    fieldnames = ['Date', 'Recipient', 'Category', 'Amount']
    
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        # Write the transaction details to the CSV file
        writer.writerow(transaction_details)

def analyze_email_content(email_body, categories):
    
    from groq import Groq

    prompt = f"""
    Extract the following details from the email content:
    - Date of transaction
    - Recipient
    - Amount
    - Category (from the provided list: {', '.join(categories)})
    and print it in the following format:
    
    Date of transaction:
    Recipient:
    Amount:
    Category:
    
    here is the Email content:
    {email_body}
    
    
    """
    client = Groq(api_key="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")
    completion = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": f"{prompt}"
            }
        ],
        temperature=1,
        max_tokens=1024,
        top_p=1,
        stream=True,
        stop=None,
    )

    response_text = ""
    for chunk in completion:
        if isinstance(chunk.choices[0].delta.content,str):
            response_text += chunk.choices[0].delta.content
    print(response_text)
    return chunk.choices[0].delta.content
    



def main():
    categories = ['Food', 'Transport', 'Utilities', 'Entertainment']  # Example categories
    sender_email = "alerts@axisbank.com"
    after_date = "2024/07/25"  # Format: YYYY/MM/DD
    before_date = "2024/07/29"  # Format: YYYY/MM/DD
    subjects = ["Debit notification from Axis Bank", "Credit notification from Axis Bank"] 
    emails = get_emails_from_sender(sender_email, subjects, after_date, before_date)
    print(emails)
    if emails:
        for email in emails:
            email_body = email['Body']
            transaction_details_str = analyze_email_content(email_body, categories)
            
            if transaction_details_str is None:
                continue  # Skip if the API request failed
            
            # Parse the transaction details
            transaction_details = {}
            for line in transaction_details_str.split('\n'):
                if 'Date of transaction:' in line:
                    transaction_details['Date'] = line.split('Date of transaction:')[-1].strip()
                elif 'Recipient:' in line:
                    transaction_details['Recipient'] = line.split('Recipient:')[-1].strip()
                elif 'Amount:' in line:
                    transaction_details['Amount'] = line.split('Amount:')[-1].strip()
                elif 'Category:' in line:
                    transaction_details['Category'] = line.split('Category:')[-1].strip()
            
            # Save the transaction details to the CSV file
            save_transaction_details(transaction_details)
            print(f"Transaction Details:\n{transaction_details}")
            print("="*50)

        print("Categorized emails saved to categorized_emails.csv.")
    else:
        print(f'No emails found from {sender_email} with subjects {", ".join(subjects)}.')

if __name__ == '__main__':
    # Initialize the CSV file with headers
    with open('categorized_emails.csv', mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ['Date', 'Recipient', 'Category', 'Amount']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

    main()
