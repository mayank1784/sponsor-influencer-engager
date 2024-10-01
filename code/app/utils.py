# importing libraries
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from app.models import Campaign, AdRequest, AdRequestStatus, Influencer, CampaignStatus
from app import db


# instagram URL
URL = "https://www.instagram.com/{}/"

# function to convert follower count strings to integers
def convert_to_int(count_str):
    count_str = count_str.lower()
    if 'k' in count_str or 'K' in count_str:
        return int(float(count_str.replace('k', '')) * 1000)
    elif 'm' in count_str or 'M' in count_str:
        return int(float(count_str.replace('m', '')) * 1000000)
    elif 'b' in count_str or 'B' in count_str:
        return int(float(count_str.replace('b', '')) * 1000000000)
    else:
        return int(count_str)

# parse function
def parse_data(s):
    try:
        # splitting the content 
        s = s.split("-")[0]
        
        # again splitting the content 
        s = s.split(" ")
        
        # getting followers count and converting to int
        followers = convert_to_int(s[0])
        
        # returning followers count
        return followers
    except (IndexError, ValueError):
        # Handle case where parsing fails
        return 0

# scrape function
def scrape_data(username):
    try:
        # getting the request from url
        r = requests.get(URL.format(username), timeout=5)
        r.raise_for_status()  # Raise an error for bad status codes
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return 0
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error occurred: {e}")
        return 0
    except requests.exceptions.Timeout as e:
        print(f"Timeout error occurred: {e}")
        return 0
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return 0

    try:
        # converting the text
        s = BeautifulSoup(r.text, "html.parser")
        
        # finding meta info
        meta = s.find("meta", property="og:description")
        if meta is None:
            print("Meta description not found")
            return 0
        
        # calling parse method
        return parse_data(meta.attrs['content'])
    except Exception as e:
        print(f"An error occurred while parsing: {e}")
        return 0

def complete_old_campaigns():
    try:
        now = datetime.now()
        campaigns_to_update = Campaign.query.filter(Campaign.end_date < now, Campaign.status != CampaignStatus.COMPLETED).all()
        for campaign in campaigns_to_update:
            campaign_id = campaign.id
            url = f'http://127.0.0.1:5000/api/campaigns/{campaign_id}/complete'
            
            response = requests.put(url, headers={'Content-Type': 'application/json'})
            
            if response.status_code == 200:
                continue
            
            elif response.status_code != 200:
                continue
            
            else:
                continue
        return
    
    except Exception as e:
        return

def calculate_reach(influencer_id):
    try:
        influencer = Influencer.query.filter(Influencer.id == influencer_id).first()
        if influencer:
            # Define the statuses to consider
            relevant_statuses = [AdRequestStatus.ACCEPTED, AdRequestStatus.NEGOTIATING, AdRequestStatus.COMPLETED, AdRequestStatus.ABANDONED]
            ads_count = AdRequest.query.filter(
                AdRequest.influencer_id == influencer_id,
                AdRequest.status.in_(relevant_statuses)
            ).count()
            influencer.reach = ads_count
            
            # Commit the transaction to save changes
            db.session.commit()
            return
        else:
            return
    except Exception as e:
        return
