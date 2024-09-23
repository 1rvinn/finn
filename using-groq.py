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
    fieldnames = ['Date', 'Time', 'Recipient','Type', 'Amount', 'Category']
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        # Write the transaction details to the CSV file
        writer.writerow(transaction_details)

def analyze_email_content(email_body, categories):
    
    from groq import Groq

    prompt = f"""
    Extract the following details from the email content:
    - Date of transaction 
    - Time of transacttion
    - Recipient (The person/firm/account number the transaction has been done with. The recipient/transferrer of the money. The body mentions details about the recipient after 'Info-'. Extract only the name)
    - Type of transaction (credit/debit)
    - Amount (The amount paid, NO $/₹ only the decimal value. Ex: 54.23. In case of a 'Debit' transaction, add a minus '-' sign in front of the amount. In case of a 'Credit' transaction, add a plus '+' sign.)
    - Category (from the provided list: {', '.join(f'{key}: {value}' for key, value in categories.items())})
    and print it in the following format:
    '
    Date of transaction:
    Time:
    Recipient:
    Type of transaction:
    Amount:
    Category:
    '
    here is the Email content:
    {email_body}
    import notes: 
    1. just print the given format and absolutely NOTHING else
    2. if it says 'isthara' or 'vendify', put category as food
    3. if it mentions a the name of a particular person, put it as personal
    
    """
    client = Groq(api_key="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")
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
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
    return response_text
    



def main():
    categories_dict = {'Food': 'Receipt seems to be from a restaurant or generally related to food purchase', 'Travel' : 'Anything travel related, planes ubers, taxis, bike rental', 'Software' : 'Software subscription or license purchase', 'Personal' : 'Monetary transaction with a friend/relative', 'Subscription' : 'Money spent on buying an online subscription - music, online streaming platforms etc'}  # Example categories
    sender_email = "alerts@axisbank.com"
    after_date = input('after date (Format: YYYY/MM/DD): ')
    before_date = input('before date (Format: YYYY/MM/DD): ')
    subjects = ["Debit notification from Axis Bank", "Credit notification from Axis Bank"] 
    emails = get_emails_from_sender(sender_email, subjects, after_date, before_date)
    print(emails)
    if emails:
        for email in emails:
            email_body = email['Body']
            transaction_details_str = analyze_email_content(email_body, categories_dict)
            
            if transaction_details_str is None:
                continue  # Skip if the API request failed
            
            # Parse the transaction details
            transaction_details = {}
            for line in transaction_details_str.split('\n'):
                if 'Date of transaction:' in line:
                    transaction_details['Date'] = line.split('Date of transaction:')[-1].strip()
                elif 'Time:' in line:
                    transaction_details['Time'] = line.split('Time:')[-1].strip()
                elif 'Recipient:' in line:
                    transaction_details['Recipient'] = line.split('Recipient:')[-1].strip()
                elif 'Type of transaction:' in line:
                    transaction_details['Type'] = line.split('Type of transaction:')[-1].strip()
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
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt

    csv=pd.read_csv("categorized_emails.csv")
    df = pd.DataFrame(csv)
    print(df)
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(15,7.79))
    pie1=ax.pie(df['Category'].value_counts(), labels=df['Category'].value_counts().index)
    ax.set_title("Category wise spending", fontweight='bold')
    plt.suptitle(f"Total: {df["Amount"].sum()}")
    ax.legend(df['Category'].value_counts().index, loc = 'upper right')


    plt.show()
    print("total")

if __name__ == '__main__':
    # Initialize the CSV file with headers
    with open('categorized_emails.csv', mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ['Date', 'Time', 'Recipient','Type', 'Amount', 'Category']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

    main()
