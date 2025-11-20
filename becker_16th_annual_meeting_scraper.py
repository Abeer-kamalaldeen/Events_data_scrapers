#!/usr/bin/env python
# coding: utf-8

# In[8]:


import requests
import pandas as pd
import os
import re
from bs4 import BeautifulSoup as bs
import time 
from datetime import datetime , timezone


# In[9]:


import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

log = logging.getLogger(__name__)


# In[10]:


def parse_session(soup):
    

    # If it's wrapped in that paragraph div, use it as root; otherwise use whole soup
    root = soup.select_one("div.paragraph.mt-medium.mb-medium.standard-text") or soup

    def get_text(selector: str):
        el = root.select_one(selector)
        return el.get_text(strip=True) if el else None

    # Basic fields
    name = get_text(".session.more-info-data.field-name")
    date_time_raw = get_text(".session.more-info-data.field-date_and_time")
    description = get_text(".session.more-info-data.field-description")
    session_type = get_text(".session.more-info-data.field-type_id")

    # Parse date / time from "Monday, April 13, 2026, 8:00 AM - 8:40 AM"
    date = start_time = end_time = None
    if date_time_raw:
        parts = [p.strip() for p in date_time_raw.split(",")]
        # Last part is time range, the rest is the date
        if len(parts) >= 2:
            time_part = parts[-1]
            date = ", ".join(parts[:-1])
        else:
            time_part = parts[0]

        if "-" in time_part:
            st, et = time_part.split("-", 1)
            start_time = st.strip()
            end_time = et.strip()

    # Speakers (links)
    speaker_links = root.select(".session.more-info-data.field-speakersLinks a")

    # Speaker images (will match by index)
    speaker_imgs = root.select(".session.more-info-data.field-speakersImages img")

    speakers = []
    for idx, a in enumerate(speaker_links):
        full_text = a.get_text(strip=True)
        href = a.get("href")

        # Split "Name, Title..." into name + title
        if "," in full_text:
            name_part, title_part = full_text.split(",", 1)
            speaker_name = name_part.strip()
            title = title_part.strip()
        else:
            speaker_name = full_text
            title = None

        # Normalize URL if it's relative
        if href and href.startswith("/"):
            href = "https://conferences.beckershospitalreview.com" + href

        img_url = img_alt = None
        if idx < len(speaker_imgs):
            img = speaker_imgs[idx]
            src = img.get("src")
            if src and src.startswith("//"):
                src = "https:" + src
            img_url = src
            img_alt = img.get("alt")

        speaker_additional_data = get_speaker_data(href)
        
        speakers.append(
            {
                "name": speaker_name,
                "title": title,
                "profile_url": href,
                "image_url": img_url,
                "image_alt": img_alt,
            } | speaker_additional_data
        )

    address = get_text(".session.more-info-data.field-location_address.mb-large") 
    
    final_data = []
    if speakers == [] :
        speakers = [{"" : ""}]
        
    for speaker in speakers:
        data = {
                "name": name,
                "date_time_raw": date_time_raw,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "session_type": session_type,
                "description": description,
                "address" : address
            } | speaker
        
        
        final_data.append(data)

    return final_data


def parse_speaker(soup):
    
    # Main container for the speaker block
    container = soup.select_one("div.row") or soup.select_one("div.col-sm-12") or soup

    # Text part may be in col-sm-8 or col-sm-12 or directly on container
    text_block = (
        container.select_one(".col-sm-8")
        or container.select_one(".col-sm-12")
        or container
    )

    def get_text(selector: str):
        el = text_block.select_one(selector)
        return el.get_text(strip=True) if el else None

    full_name = get_text(".speaker.more-info-data.field-contact_fullName")
    designations = get_text(".speaker.more-info-data.field-contact_c_2684829")
    job_title = get_text(".speaker.more-info-data.field-contact_job_title")
    company = get_text(".speaker.more-info-data.field-contact_company")

    # Speaking-at sessions (could be multiple <a>)
    speaking_at = []
    for a in text_block.select(".speaker.more-info-data.field-speakingAtLinks a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        # Normalize relative URL
        if href and href.startswith("/"):
            href = "https://conferences.beckershospitalreview.com" + href

        speaking_at.append(
            {
                "title": title,
                "url": href,
            }
        )

    # Optional: split designations like "MD, PhD" into a list
    designations_list = None
    if designations:
        designations_list = [d.strip() for d in designations.split(",") if d.strip()]

    # Image (col-sm-4 or anywhere inside container)
    img_el = container.select_one("img")
    image_url = image_alt = None
    if img_el:
        src = img_el.get("src")
        if src and src.startswith("//"):
            src = "https:" + src
        image_url = src
        image_alt = img_el.get("alt")

    
    return {
        "speaker_full_name": full_name,
        "speaker_designations": designations,
        "speaker_designations_list": designations_list,
        "speaker_job_title": job_title,
        "speaker_company": company,
        "speaker_speaking_at": speaking_at,
        "speaker_image_url": image_url,
        "speaker_image_alt": image_alt,
    }


# In[11]:


base_website_url = "https://conferences.beckershospitalreview.com"

def get_main_page_res(main_url = 'https://conferences.beckershospitalreview.com/april-annual-meeting-2026/agenda'):
    
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
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
    

    
    main_response_cc = requests.get(main_url,
                            headers=headers)
    
    if main_response_cc.status_code != 200:
        
        main_response = requests.get(main_url,
                            headers=headers,
                                    cookies = dict(main_response_cc.cookies) )
        
    else:
        main_response = main_response_cc
    
    message = f"Response {main_response.status_code}"
    print(message)
    log.info({"message" : message})
    
    return main_response


def get_session_speaker_response(url):
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=1, i',
        'referer': 'https://conferences.beckershospitalreview.com/april-annual-meeting-2026/agenda',
        'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'x-ajax-request': 'true',
        'x-requested-with': 'XMLHttpRequest',
    }
    
    session_response = requests.get(
        url,
        headers=headers,
    )
    
    message = f"Response {session_response.status_code}"
    print(message)
    log.info({"message" : message})
    
    return session_response



def get_session_data(session_url):
    
    session_data = {}
    for i in range(3):
        try:
            session_response = get_session_speaker_response(session_url)
            soup = bs(session_response.text , "lxml")
            session_data = parse_session(soup)
            break
        except Exception as e:
            log.warning({"WARNING" : "error getting session data or request",
                        "error" : e})
            None
            
    return session_data


def get_speaker_data(speaker_url):
    
    speaker_data = {}
    for i in range(3):
        try:
            speaker_response = get_session_speaker_response(speaker_url)
            soup = bs(speaker_response.text , "lxml")
            speaker_data = parse_speaker(soup)
            break
        except Exception as e:
            log.warning({"WARNING" : "error getting session data or request",
                        "error" : e})
            None
            
    return speaker_data


# In[12]:


def current_time_str():
    """Return current time as 'YYYY-MM-DD HH:MM'."""
    return datetime.now().strftime("%Y-%m-%d %H-%M")

try:
    os.mkdir("data")
except:
    None


# In[ ]:


def full_scraping():

    main_response = get_main_page_res()
    soup = bs(main_response.text , "lxml")
    
    details_urls = [base_website_url + a.get("href") if ".beckershospitalreview.com" not in a.get("href") else a.get("href") for a in soup.select("a[class='show-details']")]
    sessions_urls = [base_website_url + a.get("href") if ".beckershospitalreview.com" not in a.get("href") else a.get("href") for a in soup.select("a[title='Session Details']")]
    all_urls_sessions_only = list(set([url for url in details_urls + sessions_urls if "/session/" in url]))
    speakers_urls = list(set([url for url in details_urls + sessions_urls if "speaker/" in url])) 
    
    all_sessions_data = []
    
    message = f"We have {len(all_sessions_data)} sessions to scrape"
    log.info({"message" : message})
    
    for s , session_url in enumerate(all_urls_sessions_only):
        print("==================================")
        print(f"session {s} out of {len(all_urls_sessions_only)}")
        t1 = time.time()
        session_data = get_session_data(session_url)
        all_sessions_data.extend(session_data)
        t2 = time.time()
        print(t2 - t1)
    
    df = pd.DataFrame(all_sessions_data)
    now_time = current_time_str()
    df["last_scraping_time"] = now_time
    
    return df
    


# In[ ]:


def main():
    """Doing the full processing and scraping for the website."""
    t_start = time.time()
    for i in range(3):
        try:
            df = full_scraping()
            break
        except:
            None
            
    now_time = current_time_str()
    t_end = time.time()
    log.info({"Complete" : f"Finished scraping and processing data in {(t_end - t_start)/60} Minutes totally."})
    
    file_name = f"data\\Becker's 16th Annual Meeting_data_{now_time}.xlsx"
    df.to_excel(file_name)
    
    log.info({"Saving Data" : f"Done writing data into file {file_name}"})
    
    return df
    
    
main()

