#!/usr/bin/env python
# coding: utf-8

# In[1]:


import requests
import pandas as pd
import os
import re
from bs4 import BeautifulSoup as bs
import time 
from datetime import datetime , timezone

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

log = logging.getLogger(__name__)


# In[2]:


def get_base_request(base_url = 'https://www.himssconference.com/find-sessions/'):
    
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    }
    
    response = requests.get( base_url,  headers=headers)
    log.info({"Scraping Main Response" : response.status_code})
    
    return response


# In[3]:


def get_data_request(js_link):
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=604800',
        'Connection': 'keep-alive',
        'Origin': 'https://www.himssconference.com',
        'Referer': 'https://www.himssconference.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    
    
    now_utc = datetime.now(timezone.utc)
    ran = int(now_utc.timestamp() * 1000)  # ms since epoch, UTC
    tz = "UTC"  # timezone parameter in the URL
    
    params = {"ran" : str(ran),
             "dataType" : "schedule",
             "tz" : tz}
    
    
    detailed_response = requests.get(
        js_link.replace("/schedule.js" , "/async-data") ,
        headers=headers,
        params = params
    )
    log.info({"Scraping Data Response" : detailed_response.status_code})
    
    return detailed_response


# In[4]:


def process_speaker_session(speakers , base_session_data):
    
    data = []
    columns = [ "speaker_first_name" ,"speaker_last_name" ,"speaker_full_name" ,"speaker_title" ,"speaker_company_name" ,"speaker_about" ,"speaker_photo" ,"speaker_role" ]
    
    if speakers == []:
        data = [{col.replace("_" , " ").title() : None for col in columns} | base_session_data]

    else:
        for speaker in speakers:
            speaker_data = {col.replace("_" , " ").title() : speaker["_".join(col.split("_")[1:])] for col in columns} | base_session_data
            data.append(speaker_data)
        
    return data

def process_session(session):
    
    
    session_base_data = {'Session Title' :  session.get("title") ,
    'Session Desc' :  session.get("description") ,
    'Session Format' :  session.get("format") ,
    'Session Level' :  session.get("level") ,
    'Session Track' :  session.get("track") ,
    'Session Location' :  session.get("location") ,
    'Session Start' :  session.get("starts_at") ,
    'Session End' :  session.get("ends_at") ,
    'Event Location' :  session.get("event_location") ,
    'Session Target Audience' :  session.get("target_audience") ,
    'Session Topic Category' :  session.get("topic_category") ,
    'Session Range' :  session.get("range") ,
    'Session Timezone' :  session.get("timezone") }
    
        
    speakers_raw_data = session.get("speakers")
    
    speakers_rows_final_data = process_speaker_session(speakers_raw_data , session_base_data)
    return speakers_rows_final_data


# In[5]:


def process_all_sessions_response(detailed_response):
    
    j_data = detailed_response.json()
    data = j_data["data"]
    
    speakers = data.get("speakersById")
    sessions = list(data.get("sessionsById").values())
    days = data.get("tablesByDay")
    
    final_sessions_data = []
    for session in sessions:
        session_data = process_session(session)
        final_sessions_data.extend(session_data)
        
    log.info({"Data" : f"We have a total of {len(final_sessions_data)} data sessions"})
    
    return final_sessions_data


# In[10]:


def current_time_str():
    """Return current time as 'YYYY-MM-DD HH:MM'."""
    return datetime.now().strftime("%Y-%m-%d %H-%M")


# In[12]:


try:
    os.mkdir("data")
except:
    None


# In[14]:


def main():
    
    """Doing the full processing and scraping for the website."""
    t_start = time.time()
    for i in range(3):
        try:
            main_response = get_base_request()
            soup = bs(main_response.text , "lxml")
            js_link = [l.get("src") for l in soup.select("div.elementor-widget-container > script[type='text/javascript']") if l.has_attr("src")  and "https://api.sessionboard.com/embed" in l.get("src")][0]
            detailed_response = get_data_request(js_link)
            final_data = process_all_sessions_response(detailed_response)
            break
        except:
            None
            
    now_time = current_time_str()
    t_end = time.time()
    log.info({"Complete" : f"Finished scraping and processing data in {(t_end - t_start)/60} Minutes totally."})
    
    file_name = os.path.join(os.getcwd() , f"data/himssconference_sessions_data_{now_time}.xlsx")
    pd.DataFrame(final_data).to_excel(file_name)
    
    log.info({"Saving Data" : f"Done writing data into file {file_name}"})
    
    return final_data
    


# In[15]:


final_data = main()


# In[16]:


len(final_data)


# In[ ]:




