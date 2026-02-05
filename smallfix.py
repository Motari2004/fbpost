from flask import Flask, request, render_template, jsonify
from playwright.sync_api import sync_playwright
import time, os, uuid, random
from werkzeug.utils import secure_filename

app = Flask(__name__)

# CONFIGURATION
SESSION_FILE = "fbsession.json"
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def is_logged_in(page):
    try:
        if page.get_by_text("What's on your mind", exact=False).is_visible(timeout=3000):
            return True
    except: pass
    return False

# ==========================================
# AUTOMATION ENGINE
# ==========================================

def perform_post(email, password, message, image_path=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        
        storage = SESSION_FILE if os.path.exists(SESSION_FILE) else None
        context = browser.new_context(
            storage_state=storage,
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        page = context.new_page()
        
        # REMOVED AGGRESSIVE BLOCKING: Letting FB load fully to prevent "Loading..." hangs
        page.set_default_timeout(60000)

        try:
            print("🚀 Navigating to Facebook...")
            # Using 'load' ensures all necessary UI scripts for the composer are ready
            page.goto("https://www.facebook.com/", wait_until="load", timeout=95000)

            # --- LOGIN CHECK ---
            login_confirmed = False
            start_loop = time.time()
            while not login_confirmed:
                if is_logged_in(page):
                    print("✅ Verified! Updating fbsession.json...")
                    context.storage_state(path=SESSION_FILE)
                    login_confirmed = True
                else:
                    try:
                        email_field = page.get_by_label("Email address or phone number")
                        if email_field.is_visible(timeout=2000):
                            print("📝 Entering credentials...")
                            email_field.fill(email)
                            page.get_by_label("Password").fill(password)
                            page.get_by_role("button", name="Log in").click()
                            time.sleep(5)
                    except: pass
                    if time.time() - start_loop > 300: return {"success": False, "message": "Login Timeout."}
                    time.sleep(3)

            # --- YOUR COMPOSER ATTEMPTS LOGIC ---
            print("Opening post composer...")
            composer_found = False
            composer_attempts = [
                lambda: page.get_by_text("What's on your mind", exact=False).first.click(timeout=15000),
                lambda: page.locator('[aria-label*="mind" i]').first.click(timeout=10000),
                lambda: page.get_by_role("textbox").first.click(timeout=10000),
                lambda: page.get_by_role("button", name="Create post").click(timeout=10000),
            ]

            for i, attempt in enumerate(composer_attempts, 1):
                try:
                    print(f"  Trying method {i}...")
                    attempt()
                    print(f"✅ Method {i} was successful!")
                    composer_found = True
                    break
                except: print(f"  Method {i} failed.")

            if not composer_found:
                return {"success": False, "message": "Failed to open composer"}

            # --- HANDLING THE "LOAD TOO MUCH" HANG ---
            print("⏳ Waiting for 'Create Post' dialog to stabilize...")
            # We wait for the specific dialog role to appear before trying to type
            try:
                page.locator('div[role="dialog"]').wait_for(state="visible", timeout=15000)
                print("✅ Dialog visible.")
            except:
                print("⚠️ Dialog didn't signal visibility, proceeding with caution...")

            time.sleep(5) # Crucial sleep to let FB finish loading icons inside the composer

            # Locate the editor box
            editor = page.locator('div[contenteditable="true"][role="textbox"]').first
            editor.wait_for(state="visible", timeout=20000)
            
            print("Typing message humanly...")
            editor.click()
            for char in message:
                page.keyboard.type(char, delay=random.uniform(40, 100))
            
            if image_path:
                print(f"Uploading image...")
                page.locator('input[type="file"]').first.set_input_files(image_path)
                print("Waiting for image preview...")
                time.sleep(12) # Longer wait for media processing

            # Handle Next/Post steps
            try:
                next_btn = page.get_by_text("Next", exact=True).first
                if next_btn.is_visible(timeout=3000):
                    print("Clicking 'Next'...")
                    next_btn.click()
                    time.sleep(3)
            except: pass

            print("Clicking 'Post'...")
            # Sometimes the button is disabled while it "loads too much"
            post_button = page.get_by_role("button", name="Post", exact=True).first
            post_button.wait_for(state="visible", timeout=10000)
            post_button.click()
            
            print("Finalizing...")
            time.sleep(15) 
            context.storage_state(path=SESSION_FILE)
            
            print("✨ Post Complete!")
            return {"success": True, "message": "Successfully posted!"}

        except Exception as e:
            print(f"❌ Error: {e}")
            page.screenshot(path="hang_debug.png")
            return {"success": False, "message": str(e)}
        finally:
            browser.close()

# Flask Interface (Maintained)
@app.route('/')
def index(): return render_template('index.html')

@app.route('/post', methods=['POST'])
def handle_post():
    email, pwd, msg = request.form.get('email'), request.form.get('password'), request.form.get('message')
    img = request.files.get('image')
    img_p = None
    if img:
        img_p = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f"{uuid.uuid4()}_{img.filename}"))
        img.save(img_p)
    res = perform_post(email, pwd, msg, img_p)
    if img_p and os.path.exists(img_p): os.remove(img_p)
    return jsonify(res)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)