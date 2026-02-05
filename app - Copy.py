from flask import Flask, request, render_template, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import random
import os
import hashlib
import uuid
from werkzeug.utils import secure_filename

# ==========================================
# GLOBAL SETTINGS
# ==========================================
IS_RENDER = os.environ.get("RENDER", "False").lower() == "true"
HEADLESS = True if IS_RENDER else False 
BASE_SESSION_DIR = os.path.join(os.getcwd(), "fb_sessions")
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")

app = Flask(__name__)
os.makedirs(BASE_SESSION_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- HUMAN SIMULATION UTILS ---

def random_mouse_move(page):
    if not page.viewport_size: return
    w, h = page.viewport_size['width'], page.viewport_size['height']
    for _ in range(random.randint(2, 4)):
        page.mouse.move(random.randint(50, w-50), random.randint(50, h-50), steps=15)
        time.sleep(random.uniform(0.3, 0.7))

def get_user_session_dir(email):
    """Isolates browser data for many users using email hashing."""
    user_id = hashlib.md5(email.strip().lower().encode()).hexdigest()
    path = os.path.join(BASE_SESSION_DIR, user_id)
    os.makedirs(path, exist_ok=True)
    return path

def is_logged_in(page):
    """Your robust login detection logic."""
    HOME_SVG_PATH = "M9.464 1.286C10.294.803 11.092.5 12 .5c.908 0 1.707.303 2.537.786"
    try:
        if page.locator(f'svg path[d^="{HOME_SVG_PATH}"]').is_visible(timeout=5000):
            return True
        if page.get_by_text("What's on your mind", exact=False).is_visible(timeout=3000):
            return True
    except: pass
    return False

# --- CORE AUTOMATION ---

def perform_fb_action(email, password, message, image_path=None):
    user_data_dir = get_user_session_dir(email)
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=HEADLESS,
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36',
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            print(f"Navigating to Facebook for {email}...")
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded")

            # Handle Login
            if not is_logged_in(page):
                print("Session expired or missing. Logging in with provided credentials...")
                page.get_by_label("Email address or phone number").fill(email)
                page.get_by_label("Password").fill(password)
                
                # Using your specific role-based click
                page.get_by_role("button", name="Log in").click()
                page.wait_for_load_state("networkidle")
                
                # Final check after login
                time.sleep(5)
                if not is_logged_in(page):
                    return {"success": False, "message": "Login failed. Check credentials or 2FA."}

            # Human-like movement
            time.sleep(random.uniform(2, 4))
            random_mouse_move(page)

            # --- OPEN COMPOSER ---
            composer_found = False
            composer_attempts = [
                lambda: page.get_by_text("What's on your mind", exact=False).first.click(timeout=10000),
                lambda: page.locator('[aria-label*="mind" i]').first.click(timeout=10000)
            ]

            for attempt in composer_attempts:
                try:
                    attempt()
                    composer_found = True
                    break
                except: continue

            if not composer_found:
                return {"success": False, "message": "Could not open composer box."}

            # --- TYPE MESSAGE ---
            # Focus lexical editor
            post_input = page.locator('div[contenteditable="true"][role="textbox"]').first
            post_input.wait_for(state="visible")
            post_input.click()
            
            for char in message:
                page.keyboard.type(char, delay=random.uniform(50, 120))

            # --- ATTACH IMAGE ---
            if image_path:
                page.locator('input[type="file"]').first.set_input_files(image_path)
                time.sleep(7)

            # --- FINAL POST ---
            # Handle the 'Next' button if present
            try:
                next_btn = page.get_by_text("Next", exact=True).first
                if next_btn.is_enabled(timeout=5000):
                    next_btn.click()
                    time.sleep(2)
            except: pass

            post_btn = page.get_by_text("Post", exact=True).first
            if post_btn.is_enabled(timeout=10000):
                post_btn.click()
                time.sleep(10) # Wait for upload finish
                return {"success": True, "message": "Post successfully shared!"}
            
            return {"success": False, "message": "Post button was disabled."}

        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            context.close()

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/post', methods=['POST'])
def handle_post():
    email = request.form.get('email')
    password = request.form.get('password')
    message = request.form.get('message')
    image_file = request.files.get('image')

    if not all([email, password, message]):
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    img_path = None
    if image_file:
        filename = secure_filename(f"{uuid.uuid4()}_{image_file.filename}")
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(img_path)

    result = perform_fb_action(email, password, message, img_path)

    if img_path and os.path.exists(img_path):
        os.remove(img_path)

    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))