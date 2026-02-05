from flask import Flask, request, render_template, jsonify
from playwright.sync_api import sync_playwright
import time, os, uuid, random
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ==========================================
# HEADLESS CONTROL (EASY ACCESS)
# ==========================================
HEADLESS = True  # True = hidden browser | False = visible browser

# ==========================================
# CONFIGURATION
# ==========================================
SESSION_FILE = "fbsession.json"
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ==========================================
# HELPERS
# ==========================================
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

# ==========================================
# AUTOMATION ENGINE
# ==========================================
def perform_post(email, password, message, image_path=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )

        context = browser.new_context(
            storage_state=SESSION_FILE if os.path.exists(SESSION_FILE) else None,
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
            # ────────────────────────────────
            # NAVIGATE TO FACEBOOK
            # ────────────────────────────────
            print("🚀 Navigating to Facebook...")
            page.goto("https://www.facebook.com/", wait_until="load", timeout=95000)

            # ────────────────────────────────
            # LOGIN LOOP
            # ────────────────────────────────
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
                    return {"success": False, "message": "Login timeout"}
                time.sleep(3)

            print("✅ Logged in")
            context.storage_state(path=SESSION_FILE)

            # ────────────────────────────────
            # OPEN POST COMPOSER
            # ────────────────────────────────
            print("Opening post composer...")
            opened = False
            attempts = [
                lambda: page.get_by_text("What's on your mind", exact=False).first.click(),
                lambda: page.locator('[aria-label*="mind" i]').first.click(),
                lambda: page.get_by_role("textbox").first.click(),
                lambda: page.get_by_role("button", name="Create post").click(),
            ]

            for i, fn in enumerate(attempts, 1):
                try:
                    fn()
                    print(f"✅ Composer opened via method {i}")
                    opened = True
                    break
                except:
                    print(f"❌ Method {i} failed")

            if not opened:
                return {"success": False, "message": "Could not open composer"}

            try:
                page.locator('div[role="dialog"]').wait_for(state="visible", timeout=15000)
            except:
                print("⚠️ Dialog not clearly detected")

            time.sleep(2)
            random_mouse_move(page)

            # ────────────────────────────────
            # WAIT FOR POST EDITOR (ROBUST)
            # ────────────────────────────────
            editor_timeout = 15
            start_time = time.time()
            post_input = None

            while time.time() - start_time < editor_timeout:
                try:
                    post_input = page.locator(
                        'div[contenteditable="true"][data-lexical-editor="true"]'
                    ).first
                    if post_input.is_visible(timeout=1000):
                        print("✅ Lexical editor detected")
                        break
                except:
                    pass
                try:
                    post_input = page.locator(
                        'div[role="textbox"][contenteditable="true"]'
                    ).first
                    if post_input.is_visible(timeout=1000):
                        print("✅ Fallback editor detected")
                        break
                except:
                    pass
                time.sleep(0.5)

            if post_input is None:
                return {"success": False, "message": "Editor not detected in time"}

            # ────────────────────────────────
            # FOCUS AND TYPE MESSAGE
            # ────────────────────────────────
            page.evaluate("""
                (el) => {
                    el.focus();
                    const sel = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(el);
                    range.collapse(false);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    while (el.firstChild) el.removeChild(el.firstChild);
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true }));
                }
            """, arg=post_input.element_handle())

            time.sleep(random.uniform(0.8, 1.6))
            random_mouse_move(page)

            for ch in message:
                page.keyboard.type(ch, delay=random.uniform(55, 145))
                time.sleep(random.uniform(0.03, 0.12))

            page.evaluate("""
                (el) => {
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
                    el.dispatchEvent(new KeyboardEvent('keyup', { key: ' ', bubbles: true }));
                }
            """, arg=post_input.element_handle())

            time.sleep(random.uniform(1.5, 2.5))
            random_mouse_move(page)

            # ────────────────────────────────
            # IMAGE UPLOAD
            # ────────────────────────────────
            if image_path:
                print("Uploading image...")
                dialog = page.locator('div[role="dialog"]:visible').first
                if not dialog.is_visible(timeout=8000):
                    dialog = page
                file_input = dialog.locator('input[type="file"]').first
                try:
                    file_input.wait_for(state="attached", timeout=15000)
                    file_input.set_input_files(image_path, timeout=30000)
                    print("🖼 Image attached")
                except Exception as e:
                    print("❌ Image upload failed:", e)
                    page.screenshot(path="upload_error.png")
                time.sleep(random.uniform(4, 8))
                random_mouse_move(page)

            # ────────────────────────────────
            # NEXT → POST
            # ────────────────────────────────
            try:
                next_btn = page.get_by_text("Next", exact=True).first
                if next_btn.is_visible(timeout=3000):
                    print("Clicking 'Next'...")
                    next_btn.click()
                    time.sleep(2)
            except:
                pass

            post_btn = page.get_by_text("Post", exact=True).first
            post_btn.wait_for(state="visible", timeout=18000)
            post_btn.click(force=True)
            print("✨ Post successful")
            time.sleep(6)

            context.storage_state(path=SESSION_FILE)
            return {"success": True, "message": "Successfully posted!"}

        except Exception as e:
            page.screenshot(path="hang_debug.png")
            return {"success": False, "message": str(e)}

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
