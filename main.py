import os
import json
import requests
import asyncio
import urllib.parse
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ================= TELEGRAM CREDENTIALS (SECURE WAY) =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")

# ================= DRIVE FOLDERS (Added back) =================
# Books (PDFs) ke liye folder
DRIVE_FOLDER_BOOKS = "1Wh0TObV5uqL8S7TBopGUbgfT63nwB9-7"
# Apps/Games (APKs) ke liye folder
DRIVE_FOLDER_APPS = "1WFPmfn2vYilb5E0wji1nvt-gOXxrn7YF"

# ================= WEBHOOK URLs (Added back) =================
APP_WEBHOOK_URL = "https://api.telebotcreator.com/new-webhook?data=gAAAAABqjzqyLNDavnrkBzracrX7a4WEF48wEVVGItXK2234EB2ROq_oEKo1ytLDQfhEGKDUio828gkayIVKI7_sXaeEC1CdTI7efWde1QDYdGGObh75dwSknt16LxwLjzAykqavOU4UFoXDOZeWRJsUKSFOSbD1flwXpPHZcSYpINz7IyqxqcvRLCeeU2oFFbX1NAYC0KvFUb25YiI-QMZxwEX9WAhxFA%3D%3D" 
BOOK_WEBHOOK_URL = "https://api.telebotcreator.com/new-webhook?data=gAAAAABqj9SrqSkD8sQnaW3Tx12hEwvoEv4Kw3yGmZABailfSsXmYlgJcf5YIdMEJj81-QADwB6CxF1AhVL6KsWERs8Eby7Z9F2HbGyBsdak57LWs6eHHkNZnOGxXJWlUCPuPpnB73mKTaHed1Kd2CpY3vH6NeMiHEN_or5F-RqprsxtxiZ8XiG_wldjhhpzRk51y62N3yS5vEpqmQJ6-8YI-fgLUApLwg%3D%3D" 

# ================= DRIVE SETUP (SECURE OAUTH 2.0) =================
def get_drive_service():
    scopes = ['https://www.googleapis.com/auth/drive']
    token_data = os.environ.get("GOOGLE_TOKEN_JSON")
    
    if token_data:
        creds_dict = json.loads(token_data)
        creds = Credentials.from_authorized_user_info(creds_dict, scopes)
    else:
        creds = Credentials.from_authorized_user_file('token.json', scopes)
        
    return build('drive', 'v3', credentials=creds)

app = Client(":memory:", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# ================= START COMMAND =================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    welcome_text = (
        "🚀 **Welcome to FileVix Pro Uploader!**\n\n"
        "Main aapki badi files (up to 2GB) seedha Google Drive me upload kar sakta hu aur unko automatic AI details ke sath Website par publish kar sakta hu.\n\n"
        "**Kaise use karein?**\n"
        "Bas mujhe koi bhi APK ya PDF file bhejein, aur main baaki ka sara kaam khud sambhal lunga!\n\n"
        "*(Tip: Agar Book upload kar rahe hain, toh caption me pehli line me Book Name aur dusri line me Author Name likhein)* 🔥"
    )
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

# ================= DOCUMENT UPLOAD LOGIC =================
@app.on_message(filters.document)
async def handle_document(client, message):
    msg = await message.reply_text("⏳ Downloading file to server (0%)...")
    
    # 1. Extensions
    original_name = message.document.file_name
    extension = ""
    if "." in original_name:
        extension = "." + original_name.split(".")[-1]
    
    # ================= CAPTION & AUTHOR LOGIC =================
    raw_caption = message.caption if message.caption else ""
    parsed_book_name = ""
    parsed_author_name = ""
    is_caption_provided = False

    if raw_caption:
        is_caption_provided = True
        lines = [line.strip() for line in raw_caption.split('\n') if line.strip()]
        if len(lines) > 1:
            parsed_author_name = lines[-1]
            parsed_book_name = " ".join(lines[:-1])
        else:
            parsed_book_name = lines[0] if lines else ""

    temp_name = parsed_book_name if parsed_book_name else original_name

    # ================= AUTOMATIC RENAME & FOLDER LOGIC =================
    is_book = ".pdf" in original_name.lower() or ".epub" in original_name.lower()
    
    if temp_name.lower().endswith(extension.lower()):
        base_name_without_ext = temp_name[:-len(extension)].strip()
    else:
        base_name_without_ext = temp_name.rsplit('.', 1)[0].strip()
    
    if not is_caption_provided:
        base_name_without_ext = base_name_without_ext.replace("_", " ").replace("-", " ").replace(".", " ")
        base_name_without_ext = " ".join(base_name_without_ext.split())

    if is_book:
        drive_file_name = f"{base_name_without_ext} @BooksBunch{extension}"
        target_folder_id = DRIVE_FOLDER_BOOKS
    else:
        drive_file_name = f"{base_name_without_ext} @FullModApk{extension}"
        target_folder_id = DRIVE_FOLDER_APPS
        
    website_title = base_name_without_ext

    # 2. Download File to Server
    file_path = await message.download(
        progress=lambda current, total: update_progress(msg, current, total, "Downloading to server")
    )
    
    await msg.edit_text("⏳ Uploading to Google Drive...")
    
    # 3. Upload to Google Drive
    try:
        drive_service = get_drive_service()
        file_metadata = {'name': drive_file_name, 'parents': [target_folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        
        uploaded_file = drive_service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink'
        ).execute()
        
        file_id = uploaded_file.get('id')
        drive_link = uploaded_file.get('webViewLink')
        
        drive_service.permissions().create(
            fileId=file_id, 
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
    except Exception as e:
        await msg.edit_text(f"❌ Google Drive Upload Failed: {str(e)}")
        if os.path.exists(file_path): os.remove(file_path)
        return
        
    if os.path.exists(file_path):
        os.remove(file_path)
        
    await msg.edit_text("✅ Drive Upload Done! Fetching AI Details & Publishing...")

    # 4. AI Logic
    file_type = "book" if is_book else "app"
    ai_search_name = base_name_without_ext 
    
    ai_query_string = ai_search_name
    if is_book and parsed_author_name:
        ai_query_string += f" {parsed_author_name}"
        
    thumbnail_url = ""
    screenshots = []
    
    # --- Image Fetching ---
    try:
        if is_book:
            itunes_res = requests.get(f"https://itunes.apple.com/search?term={urllib.parse.quote(ai_query_string)}&entity=ebook&limit=1").json()
            if itunes_res.get("results"):
                thumb = itunes_res["results"][0].get("artworkUrl512") or itunes_res["results"][0].get("artworkUrl100")
                if thumb: thumbnail_url = thumb.replace("100x100bb", "1000x1000bb").replace("512x512bb", "1000x1000bb")
            
            if not thumbnail_url:
                gbooks_res = requests.get(f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(ai_query_string)}&maxResults=1").json()
                if gbooks_res.get("items") and gbooks_res["items"][0].get("volumeInfo", {}).get("imageLinks"):
                    thumbnail_url = gbooks_res["items"][0]["volumeInfo"]["imageLinks"].get("thumbnail", "")
                    thumbnail_url = thumbnail_url.replace("http:", "https:").replace("&edge=curl", "").replace("zoom=1", "zoom=0")
            
            if not thumbnail_url: thumbnail_url = "https://placehold.co/500x500?text=No+Cover"
            screenshots.append(thumbnail_url)
        else:
            itunes_res = requests.get(f"https://itunes.apple.com/search?term={urllib.parse.quote(ai_search_name)}&entity=software&limit=1").json()
            if itunes_res.get("results"):
                item = itunes_res["results"][0]
                thumb = item.get("artworkUrl512") or item.get("artworkUrl100")
                if thumb: thumbnail_url = thumb.replace("100x100bb", "1000x1000bb").replace("512x512bb", "1000x1000bb")
                
                screen_urls = item.get("screenshotUrls", [])
                for s in screen_urls[:5]:
                    screenshots.append(s.replace("392x696bb", "1000x1000bb").replace("406x722bb", "1000x1000bb"))
            
            if not thumbnail_url: thumbnail_url = "https://placehold.co/500x500?text=No+Icon"
    except Exception as e:
        print("Image fetch error:", e)

    # --- AI Text Fetching ---
    valid_cats_app = "Art & Design, Auto & Vehicles, Beauty, Business, Communication, Dating, Education, Emulator, Entertainment, Events, Finance, Food & Drink, Health & Fitness, House & Home, Libraries, Lifestyle, Maps & Navigation, Medical, Music, News & Magazines, NSFW, Parenting, Personalization, Photography, Productivity, Shopping, Social, Sport, Tools, Travel & Local, Video Players & Editors, Weather, Utilities, Hacking, Graphics & Design, Navigation, Photo & Video"
    valid_cats_book = "SelfHelp, Sexuality, NoFap, Psychology, NonFiction, Spirituality, Philosofy, Inspirational, Productivity, Business, Addiction, Biography, Science, Money, Fiction, SemenRetention, LeaderShip, Management, Entrepreneurship, Celibacy, Brahmacharya"
    
    cat_list_str = valid_cats_book if is_book else valid_cats_app
    type_text_display = "book" if is_book else "app"
    
    # Prompt me explicitly limit mention kardi taki AI thoda chota generate kare
    if is_book:
        desc_prompt = f'Write a short, engaging, and SEO friendly book summary/description for the book named: "{ai_search_name}"'
        if parsed_author_name: desc_prompt += f' written by {parsed_author_name}'
        desc_prompt += '. Keep it under 650 characters. Return strictly in plain text without any markdown symbols like asterisks (**).'
        
        cat_prompt = f'From this list [{cat_list_str}], pick exactly 1 most relevant category for the book named: "{ai_search_name}"'
        if parsed_author_name: cat_prompt += f' by {parsed_author_name}'
        cat_prompt += '. Return ONLY the exact category name from the list, no extra text.'
    else:
        desc_prompt = f'Write 3 to 4 realistic Mod Features (like Premium Unlocked, Unlimited Money, No Ads, etc.) as bullet points, and then write a short, engaging, and SEO friendly description for the app named: {ai_search_name}. Keep it under 650 characters. Return strictly in plain text without any markdown symbols like asterisks (**).'
        cat_prompt = f'From this list [{cat_list_str}], pick exactly 1 most relevant category for the {type_text_display} named: {ai_search_name}. Return ONLY the exact category name from the list, no extra text.'

    raw_desc = "Generated description."
    category = "Books" if is_book else "Apps"

    try:
        res_desc = requests.get(f"https://prexzyapis.com/ai/aiserv?prompt={urllib.parse.quote(desc_prompt)}").json()
        raw_desc = res_desc.get("response") or res_desc.get("answer") or raw_desc
    except: pass

    try:
        res_cat = requests.get(f"https://prexzyapis.com/ai/aiserv?prompt={urllib.parse.quote(cat_prompt)}").json()
        cat_ans = res_cat.get("response") or res_cat.get("answer") or ""
        if cat_ans:
            category = "".join(c for c in cat_ans if c.isalnum() or c in " &").strip()
    except: pass

    final_description = raw_desc if is_book else f"⭐ Mod Features & Details:\n\n{raw_desc}"
    
    # 🔥 YAHAN HUA HAI MAX 735 CHARACTERS WALA CHANGE 🔥
    # Agar AI ne thoda bada description de diya, toh usko 735 character tak cut kar denge
    if len(final_description) > 735:
        # Cut karne ke baad end me "..." laga denge taaki incomplete na lage
        final_description = final_description[:732] + "..."

    # 5. Firebase Publish
    firestore_url = "https://firestore.googleapis.com/v1/projects/filevix/databases/(default)/documents/files"
    
    screenshots_fb = [{"stringValue": s} for s in screenshots]
    
    payload = {
        "fields": {
            "title": {"stringValue": website_title},
            "type": {"stringValue": file_type},
            "status": {"stringValue": "live"},
            "thumbnailUrl": {"stringValue": thumbnail_url},
            "screenshots": {"arrayValue": {"values": screenshots_fb}},
            "downloadUrl": {"stringValue": drive_link},
            "description": {"stringValue": final_description},
            "categories": {"arrayValue": {"values": [{"stringValue": category}]}},
            "requiredAds": {"integerValue": "3"},
            "adType": {"stringValue": "adsgram"},
            "downloads": {"integerValue": "0"},
            "createdAt": {"timestampValue": datetime.utcnow().isoformat() + "Z"},
            "botSecret": {"stringValue": "FileVixBot@2024!"}
        }
    }
    
    if parsed_author_name:
        payload["fields"]["author"] = {"stringValue": parsed_author_name}

    try:
        fb_res = requests.post(firestore_url, json=payload)
        
        if fb_res.status_code == 200:
            doc_id = fb_res.json().get('name').split('/')[-1]
            await msg.edit_text(f"✅ *Upload & Auto-Publish Successful!*\n\n🔗 *Drive Link:* {drive_link}", parse_mode=ParseMode.MARKDOWN)
            
            target_webhook = BOOK_WEBHOOK_URL if is_book else APP_WEBHOOK_URL
            
            if target_webhook:
                webhook_payload = {
                    "title": website_title,
                    "profilePicture": thumbnail_url,
                    "description": final_description,
                    "category": category,
                    "downloadLink": f"https://filevix.blogspot.com/?id={doc_id}",
                    "author": parsed_author_name
                }
                try:
                    requests.post(target_webhook, json=webhook_payload)
                except Exception as e:
                    print(f"Webhook Failed: {e}")
            
        else:
            await msg.edit_text(f"⚠️ Drive Uploaded, but Website Publish Failed.\nError: {fb_res.text}\n\n🔗 *Drive Link:* {drive_link}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Publish Error: {str(e)}")

# ================= PROGRESS BAR HELPER =================
async def update_progress(message, current, total, text):
    percent = round((current / total) * 100)
    if percent % 10 == 0:
        try:
            await message.edit_text(f"⏳ {text} ({percent}%)...")
        except:
            pass

print("Bot is running smoothly with OAuth 2.0...")
app.run()
