from flask import Flask, request, render_template, jsonify, send_from_directory
from playwright.sync_api import sync_playwright
import time, os, uuid, random, json
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)

# ==========================================
# HEADLESS CONTROL
# ==========================================
HEADLESS = True  # True = hidden browser | False = visible browser

# ==========================================
# CONFIGURATION
# ==========================================
SESSION_JSON_ENV = os.getenv("FB_SESSION_JSON")  # JSON string of session if exists
SESSION_STATE = None
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "uploads")
SCREENSHOT_FOLDER = os.path.join(tempfile.gettempdir(), "screenshots")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ==========================================
# HELPERS
# ==========================================
captured_screenshots = []

def random_mouse_move(page):
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        for _ in range(random.randint(2, 4)):
            x = random.randint(80, vp["width"] - 80)
            y = random.randint(80, vp["height"] - 80)
            page.mouse.move(x, y, steps=random.randint(10, 20))
            time.sleep(random.uniform(0.3, 0.9))
    except:
        pass

def is_logged_in(page):
    try:
        return page.get_by_text("What's on your mind", exact=False).is_visible(timeout=4000)
    except:
        return False

def save_screenshot(page, name):
    filename = f"{int(time.time())}_{name}.png"
    path = os.path.join(SCREENSHOT_FOLDER, filename)
    try:
        page.screenshot(path=path, full_page=True)
        print(f"📸 Screenshot saved: {path}")
        captured_screenshots.append(filename)
    except Exception as e:
        print(f"⚠️ Failed to save screenshot {name}: {e}")

# ==========================================
# AUTOMATION ENGINE
# ==========================================
def perform_post(email, password, message, image_path=None):
    global captured_screenshots
    global SESSION_STATE

    captured_screenshots = []

    # Load session from ENV if available
    storage_state = None
    if SESSION_STATE:
        storage_state = SESSION_STATE
    elif SESSION_JSON_ENV:
        storage_state = json.loads(SESSION_JSON_ENV)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )
        context = browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            # -------------------------
            # LOGIN
            # -------------------------
            print("🚀 Navigating to Facebook...")
            page.goto("https://www.facebook.com/", wait_until="load", timeout=95000)

            start = time.time()
            while not is_logged_in(page):
                try:
                    email_box = page.get_by_label("Email address or phone number")
                    if email_box.is_visible(timeout=2000):
                        print("📝 Logging in...")
                        email_box.fill(email)
                        page.get_by_label("Password").fill(password)
                        page.get_by_role("button", name="Log in").click()
                        time.sleep(6)
                except:
                    pass
                if time.time() - start > 300:
                    return {"success": False, "message": "Login timeout", "screenshots": captured_screenshots}
                time.sleep(3)

            print("✅ Logged in")
            SESSION_STATE = context.storage_state()  # update global session
            save_screenshot(page, "logged_in")

            # -------------------------
            # OPEN COMPOSER
            # -------------------------
            print("Opening post composer...")
            composer_found = False
            attempts = [
                lambda: page.get_by_text("What's on your mind", exact=False).first.click(timeout=20000),
                lambda: page.locator('[aria-label*="mind" i]').first.click(timeout=15000),
                lambda: page.get_by_role("textbox").first.click(timeout=15000),
                lambda: page.get_by_role("button", name="Create post").click(timeout=15000),
            ]
            start_time = time.time()
            while not composer_found and time.time() - start_time < 50:
                for i, fn in enumerate(attempts, 1):
                    try:
                        fn()
                        print(f"✅ Composer opened via method {i}")
                        composer_found = True
                        break
                    except:
                        pass
                if not composer_found:
                    time.sleep(2)

            if not composer_found:
                return {"success": False, "message": "Could not open composer", "screenshots": captured_screenshots}

            print("Composer opened")
            time.sleep(random.uniform(1.5, 3.5))
            random_mouse_move(page)
            save_screenshot(page, "composer_opened")

            # -------------------------
            # FOCUS & TYPE MESSAGE
            # -------------------------
            post_input = page.locator('div[contenteditable="true"][data-lexical-editor="true"]').first
            try:
                post_input.wait_for(state="visible", timeout=15000)
            except:
                post_input = page.locator('div[role="textbox"][contenteditable="true"]').first
                post_input.wait_for(state="visible", timeout=15000)

            page.evaluate("""
                (el) => {
                    el.focus();
                    while (el.firstChild) el.removeChild(el.firstChild);
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true }));
                }
            """, arg=post_input.element_handle())

            time.sleep(random.uniform(0.9, 1.8))
            random_mouse_move(page)

            for char in message:
                page.keyboard.type(char, delay=random.uniform(55, 145))
                time.sleep(random.uniform(0.035, 0.125))

            page.evaluate("""
                (el) => {
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, arg=post_input.element_handle())
            save_screenshot(page, "message_typed")
            time.sleep(random.uniform(1.5, 3.0))
            random_mouse_move(page)

            # -------------------------
            # IMAGE UPLOAD
            # -------------------------
            if image_path:
                print("Uploading image...")
                composer_dialog = page.locator(
                    'div[role="dialog"]:has-text("Create post"):visible, div[role="dialog"]:visible'
                ).first

                if not composer_dialog.is_visible(timeout=8000):
                    composer_dialog = page

                file_input = composer_dialog.locator('input[type="file"]').first
                try:
                    file_input.wait_for(state="attached", timeout=15000)
                    file_input.set_input_files(image_path, timeout=30000)
                    print("🖼 Image attached")
                    save_screenshot(page, "image_attached")
                except Exception as e:
                    print(f"Could not attach image: {e}")
                    save_screenshot(page, "upload_error")

                time.sleep(random.uniform(6.0, 12.0))
                random_mouse_move(page)

            # -------------------------
            # NEXT → POST
            # -------------------------
            time.sleep(random.uniform(2.0, 4.5))
            random_mouse_move(page)

            try:
                next_button = page.get_by_text("Next", exact=True).first
                if not next_button.is_visible(timeout=12000):
                    next_button = page.locator('span:has-text("Next")').locator('xpath=..').first

                if next_button.is_enabled(timeout=8000):
                    print("Clicking 'Next'...")
                    next_button.click(force=True)
                    save_screenshot(page, "next_clicked")
                    time.sleep(random.uniform(2.5, 5.0))
                    random_mouse_move(page)
            except:
                print("No 'Next' button found, continuing...")

            post_button = page.get_by_text("Post", exact=True).first
            if not post_button.is_visible(timeout=18000):
                post_button = page.locator('span:has-text("Post")').locator('xpath=..').first

            if post_button.is_enabled(timeout=12000):
                print("Clicking 'Post'...")
                post_button.click(force=True)
                save_screenshot(page, "post_clicked")
                print("Posted successfully! ✓")
                time.sleep(random.uniform(4, 10))
            else:
                print("Failed to find 'Post' button")
                save_screenshot(page, "no_post_button")
                return {"success": False, "message": "Could not find Post button", "screenshots": captured_screenshots}

            SESSION_STATE = context.storage_state()  # save session globally
            return {"success": True, "message": "Successfully posted!", "screenshots": captured_screenshots}

        except Exception as e:
            save_screenshot(page, "exception")
            return {"success": False, "message": str(e), "screenshots": captured_screenshots}

        finally:
            browser.close()

# ==========================================
# FLASK ROUTES
# ==========================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/post", methods=["POST"])
def handle_post():
    email = request.form.get("email")
    password = request.form.get("password")
    message = request.form.get("message")

    img = request.files.get("image")
    img_path = None
    if img:
        img_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            secure_filename(f"{uuid.uuid4()}_{img.filename}")
        )
        img.save(img_path)

    result = perform_post(email, password, message, img_path)

    if img_path and os.path.exists(img_path):
        os.remove(img_path)

    return jsonify(result)

@app.route("/screenshots/<filename>")
def serve_screenshot(filename):
    return send_from_directory(SCREENSHOT_FOLDER, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
