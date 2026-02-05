from flask import Flask, request, render_template, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import random
import os
import sys
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Folders
SESSION_DIR = os.path.join(os.getcwd(), "fb_session")
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def random_mouse_move(page):
    if not page.viewport_size:
        return
    w = page.viewport_size['width']
    h = page.viewport_size['height']
    for _ in range(random.randint(2, 5)):
        x = random.randint(80, w - 80)
        y = random.randint(80, h - 80)
        page.mouse.move(x, y, steps=random.randint(10, 20))
        time.sleep(random.uniform(0.4, 1.1))

def is_logged_in(page):
    HOME_SVG_PATH = (
        "M9.464 1.286C10.294.803 11.092.5 12 .5c.908 0 1.707.303 2.537.786.795.462 "
        "1.7 1.142 2.815 1.977l2.232 1.675c1.391 1.042 2.359 1.766 2.888 2.826.53 "
        "1.059.53 2.268.528 4.006v4.3c0 1.355 0 2.471-.119 3.355-.124.928-.396 "
        "1.747-1.052 2.403-.657.657-1.476.928-2.404 1.053-.884.119-2 .119-3.354 "
        ".119H7.93c-1.354 0-2.471 0-3.355-.119-.928-.125-1.747-.396-2.403-1.053"
        "-.656-.656-.928-1.475-1.053-2.403C1 18.541 1 17.425 1 16.07v-4.3c0-1.738"
        "-.002-2.947.528-4.006.53-1.06 1.497-1.784 2.888-2.826L6.65 3.263c1.114"
        "-.835 2.02-1.515 2.815-1.977zM10.5 13A1.5 1.5 0 0 0 9 14.5V21h6v-6.5"
        "a1.5 1.5 0 0 0-1.5-1.5h-3z"
    )

    try:
        page.locator(f'svg path[d="{HOME_SVG_PATH}"]').wait_for(state="visible", timeout=10000)
        return True
    except:
        pass

    try:
        if page.get_by_text("What's on your mind", exact=False).is_visible(timeout=6000):
            return True
    except:
        pass

    try:
        if page.locator('div[role="feed"]').is_visible(timeout=6000):
            return True
    except:
        pass

    return False

def perform_post(message, image_path=None, email=None, password=None):
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,  # Change to False for debugging
            viewport={'width': 1280, 'height': 800},
            locale='en-US',
            timezone_id='Africa/Nairobi',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True,
        )

        page = context.new_page()
        logged_in = False

        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=45000)

            if is_logged_in(page):
                logged_in = True
                print("Already logged in")
            elif email and password:
                print("Logging in...")
                page.get_by_label("Email address or phone number").fill(email)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Log in").click()

                start = time.time()
                while time.time() - start < 90:
                    if is_logged_in(page):
                        logged_in = True
                        print("Login successful")
                        break
                    time.sleep(1.5)

            if not logged_in:
                return {"success": False, "message": "Login failed - please check credentials or complete manually"}

            time.sleep(random.uniform(3, 6))
            random_mouse_move(page)

            # Open composer
            composer_found = False
            attempts = [
                lambda: page.get_by_text("What's on your mind", exact=False).first.click(timeout=20000),
                lambda: page.locator('[aria-label*="mind" i]').first.click(timeout=15000),
                lambda: page.get_by_role("textbox").first.click(timeout=15000),
                lambda: page.get_by_role("button", name="Create post").click(timeout=15000),
            ]

            for attempt in attempts:
                try:
                    attempt()
                    composer_found = True
                    break
                except:
                    pass

            if not composer_found:
                return {"success": False, "message": "Could not open composer"}

            time.sleep(random.uniform(1.5, 3.5))
            random_mouse_move(page)

            # Type message
            post_input = page.locator('div[contenteditable="true"][data-lexical-editor="true"]').first
            if not post_input.is_visible(timeout=10000):
                post_input = page.locator('div[role="textbox"][contenteditable="true"]').first

            page.evaluate("(el) => { el.focus(); while(el.firstChild) el.removeChild(el.firstChild); }", arg=post_input.element_handle())

            for char in message:
                page.keyboard.type(char, delay=random.uniform(55, 145))
                time.sleep(random.uniform(0.03, 0.13))

            page.evaluate("(el) => { el.dispatchEvent(new InputEvent('input', {bubbles:true})); }", arg=post_input.element_handle())

            time.sleep(random.uniform(1.5, 3.0))

            # Upload image if provided
            if image_path:
                composer_dialog = page.locator('div[role="dialog"]:has-text("Create post"):visible').first
                if not composer_dialog.is_visible(timeout=8000):
                    composer_dialog = page

                file_input = composer_dialog.locator('input[type="file"]').first

                try:
                    file_input.wait_for(state="attached", timeout=15000)
                    file_input.set_input_files(image_path, timeout=30000)
                    print("Image attached")
                    time.sleep(random.uniform(6, 12))
                except Exception as e:
                    return {"success": False, "message": f"Image upload failed: {str(e)}"}

            # Click Next
            next_button = page.get_by_text("Next", exact=True).first
            if next_button.is_enabled(timeout=12000):
                next_button.click(force=True)
                time.sleep(random.uniform(3, 6))
            else:
                return {"success": False, "message": "Next button not found"}

            # Click Post
            post_button = page.get_by_text("Post", exact=True).first
            if post_button.is_enabled(timeout=18000):
                post_button.click(force=True)
                time.sleep(random.uniform(4, 8))
                return {"success": True, "message": "Posted successfully!"}
            else:
                return {"success": False, "message": "Post button not found"}

        except Exception as e:
            return {"success": False, "message": str(e)}

        finally:
            context.close()



@app.route('/check_connection')
def check_connection():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            viewport={'width': 1280, 'height': 800},
            locale='en-US',
            timezone_id='Africa/Nairobi',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
            if is_logged_in(page):
                return jsonify({"connected": True})
        except:
            pass
        finally:
            context.close()
    return jsonify({"connected": False})




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/post', methods=['POST'])
def post():
    message = request.form.get('message', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    image_file = request.files.get('image')

    if not message:
        return jsonify({"success": False, "message": "Message is required"}), 400

    image_path = None
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(f"{uuid.uuid4()}_{image_file.filename}")
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(image_path)

    result = perform_post(message, image_path, email or None, password or None)

    # Clean up uploaded file after posting
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)