import os
import requests
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import urllib.parse

# ================= CREDENTIALS =================
BOT_TOKEN = "8067333157:AAGrEAEeYqKX4CFyT0nOzNvJYi69dSSSrQs"
API_ID = 30072361  
API_HASH = "89172ae56cce451a933e4aa2557c1721" 

DRIVE_FOLDER_ID = "1Wh0TObV5uqL8S7TBopGUbgfT63nwB9-7"
SERVICE_ACCOUNT_FILE = "credentials.json"

# ================= DRIVE SETUP =================
def get_drive_service():
    scopes = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    return build('drive', 'v3', credentials=creds)

app = Client("filevix_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= START COMMAND =================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    welcome_text = (
        "🚀 **Welcome to FileVix Pro Uploader!**\n\n"
        "Main aapki badi files (up to 2GB) seedha Google Drive me upload kar sakta hu aur unko automatic AI details ke sath Website par publish kar sakta hu.\n\n"
        "**Kaise use karein?**\n"
        "Bas mujhe koi bhi APK ya PDF file bhejein, aur main baaki ka sara kaam khud sambhal lunga! 🔥"
    )
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

# ================= DOCUMENT UPLOAD LOGIC =================
@app.on_message(filters.document)
async def handle_document(client, message):
    msg = await message.reply_text("⏳ Downloading file to server (0%)...")
    
    # 1. Names and Extensions
    original_name = message.document.file_name
    extension = ""
    if "." in original_name:
        extension = "." + original_name.split(".")[-1]
        
    caption = message.caption if message.caption else None
    final_name = (caption + extension) if caption else original_name
    
    # 2. Download File to Server (Railway)
    file_path = await message.download(
        progress=lambda current, total: update_progress(msg, current, total, "Downloading to server")
    )
    
    await msg.edit_text("⏳ Uploading to Google Drive...")
    
    # 3. Upload to Google Drive
    try:
        drive_service = get_drive_service()
        file_metadata = {'name': final_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(file_path, resumable=True)
        
        uploaded_file = drive_service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink'
        ).execute()
        
        file_id = uploaded_file.get('id')
        drive_link = uploaded_file.get('webViewLink')
        
        # Make file public
        drive_service.permissions().create(
            fileId=file_id, 
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
    except Exception as e:
        await msg.edit_text(f"❌ Google Drive Upload Failed: {str(e)}")
        if os.path.exists(file_path): os.remove(file_path)
        return
        
    # Delete from Railway server to save space
    if os.path.exists(file_path):
        os.remove(file_path)
        
    await msg.edit_text("✅ Drive Upload Done! Fetching AI Details & Publishing...")

    # 4. AI Logic 
    is_book = ".pdf" in original_name.lower() or ".epub" in original_name.lower()
    file_type = "book" if is_book else "app"
    base_name = final_name.rsplit('.', 1)[0].strip()
    
    thumbnail_url = ""
    screenshots = []
    
    # --- Image Fetching ---
    try:
        if is_book:
            itunes_res = requests.get(f"https://itunes.apple.com/search?term={urllib.parse.quote(base_name)}&entity=ebook&limit=1").json()
            if itunes_res.get("results"):
                thumb = itunes_res["results"][0].get("artworkUrl512") or itunes_res["results"][0].get("artworkUrl100")
                if thumb: thumbnail_url = thumb.replace("100x100bb", "1000x1000bb").replace("512x512bb", "1000x1000bb")
            
            if not thumbnail_url:
                gbooks_res = requests.get(f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(base_name)}&maxResults=1").json()
                if gbooks_res.get("items") and gbooks_res["items"][0].get("volumeInfo", {}).get("imageLinks"):
                    thumbnail_url = gbooks_res["items"][0]["volumeInfo"]["imageLinks"].get("thumbnail", "")
                    thumbnail_url = thumbnail_url.replace("http:", "https:").replace("&edge=curl", "").replace("zoom=1", "zoom=0")
            
            if not thumbnail_url: thumbnail_url = "https://placehold.co/500x500?text=No+Cover"
            screenshots.append(thumbnail_url)
        else:
            itunes_res = requests.get(f"https://itunes.apple.com/search?term={urllib.parse.quote(base_name)}&entity=software&limit=1").json()
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
    
    desc_prompt = f'Write a short, engaging, and SEO friendly book summary/description for the book named: "{base_name}". Return strictly in plain text without any markdown symbols like asterisks (**).' if is_book else f'Write 3 to 4 realistic Mod Features (like Premium Unlocked, Unlimited Money, No Ads, etc.) as bullet points, and then write a short, engaging, and SEO friendly description for the app named: {base_name}. Return strictly in plain text without any markdown symbols like asterisks (**).'
    cat_prompt = f'From this list [{cat_list_str}], pick exactly 1 most relevant category for the {type_text_display} named: {base_name}. Return ONLY the exact category name from the list, no extra text.'

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

    # 5. Firebase Publish
    firestore_url = "https://firestore.googleapis.com/v1/projects/filevix/databases/(default)/documents/files"
    
    screenshots_fb = [{"stringValue": s} for s in screenshots]
    
    payload = {
        "fields": {
            "title": {"stringValue": base_name},
            "type": {"stringValue": file_type},
            "status": {"stringValue": "live"},
            "thumbnailUrl": {"stringValue": thumbnail_url},
            "screenshots": {"arrayValue": {"values": screenshots_fb}},
            "downloadUrl": {"stringValue": drive_link},
            "description": {"stringValue": final_description},
            "categories": {"arrayValue": {"values": [{"stringValue": category}]}},
            "requiredAds": {"integerValue": "1"},
            "adType": {"stringValue": "monetag"},
            "downloads": {"integerValue": "0"},
            "createdAt": {"timestampValue": datetime.utcnow().isoformat() + "Z"},
            "botSecret": {"stringValue": "FileVixBot@2024!"}
        }
    }

    try:
        fb_res = requests.post(firestore_url, json=payload)
        if fb_res.status_code == 200:
            await msg.edit_text(f"✅ *Upload & Auto-Publish Successful!*\n\n🔗 *Drive Link:* {drive_link}", parse_mode=ParseMode.MARKDOWN)
        else:
            await msg.edit_text(f"⚠️ Drive Uploaded, but Website Publish Failed.\nError: {fb_res.text}\n\n🔗 *Drive Link:* {drive_link}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Publish Error: {str(e)}")

# ================= PROGRESS BAR HELPER =================
async def update_progress(message, current, total, text):
    percent = round((current / total) * 100)
    # Update message every 10% to avoid Telegram rate limits
    if percent % 10 == 0:
        try:
            await message.edit_text(f"⏳ {text} ({percent}%)...")
        except:
            pass

print("Bot is running...")
app.run()
