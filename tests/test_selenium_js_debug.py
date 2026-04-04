"""Quick test: does 'return' prefix break IIFE injection in Selenium?"""

import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--window-size=1920,1080")
d = webdriver.Chrome(options=opts)
d.get(
    "file:///Users/famat/PycharmProjects/SIDE/demodsl/examples/effects_showcase_page.html"
)

time.sleep(1)

# --- Test 1: IIFE WITHOUT 'return' prefix (like Playwright does) ---
script_iife = """
(() => {
    const overlay = document.createElement('div');
    overlay.id = '__test_no_return';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(255,0,0,0.5);z-index:99999;pointer-events:none;';
    document.body.appendChild(overlay);
})()
"""
try:
    d.execute_script(script_iife)
    exists = d.execute_script("return !!document.getElementById('__test_no_return')")
    print(f"Test 1 (no return prefix): element exists = {exists}")
except Exception as e:
    print(f"Test 1 (no return prefix): ERROR = {e}")

# Clean
d.execute_script("document.getElementById('__test_no_return')?.remove()")

# --- Test 2: IIFE WITH 'return' prefix (what our evaluate_js does) ---
try:
    d.execute_script(f"return {script_iife}")
    exists = d.execute_script("return !!document.getElementById('__test_no_return')")
    print(f"Test 2 (with 'return' prefix): element exists = {exists}")
except Exception as e:
    print(f"Test 2 (with 'return' prefix): ERROR = {type(e).__name__}: {str(e)[:300]}")

# --- Test 3: Check what the actual SpotlightEffect sends ---
spot_script = """
        (() => {
            const overlay = document.createElement('div');
            overlay.id = '__demodsl_spotlight';
            overlay.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: radial-gradient(circle at center, transparent 30%, rgba(0,0,0,0.8) 70%);
                z-index: 99999; pointer-events: none;
            `;
            document.body.appendChild(overlay);
        })()
    """
# Without return
try:
    d.execute_script(spot_script)
    exists = d.execute_script("return !!document.getElementById('__demodsl_spotlight')")
    print(f"Test 3a (spotlight, no return): element exists = {exists}")
except Exception as e:
    print(f"Test 3a ERROR: {e}")

d.execute_script("document.getElementById('__demodsl_spotlight')?.remove()")

# With return (what our provider does)
try:
    d.execute_script(f"return {spot_script}")
    exists = d.execute_script("return !!document.getElementById('__demodsl_spotlight')")
    print(f"Test 3b (spotlight, with return): element exists = {exists}")
except Exception as e:
    print(f"Test 3b ERROR: {type(e).__name__}: {str(e)[:300]}")

# --- Test 4: Screenshot comparison ---

d.execute_script("""
(() => {
    const overlay = document.createElement('div');
    overlay.id = '__test_visible';
    overlay.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:500px;height:200px;background:linear-gradient(90deg,#ff0000,#00ff00,#0000ff);z-index:99999;border-radius:20px;display:flex;align-items:center;justify-content:center;font-size:48px;color:white;font-weight:bold;';
    overlay.textContent = 'EFFECT VISIBLE!';
    document.body.appendChild(overlay);
})()
""")
time.sleep(0.5)
d.save_screenshot("/tmp/test_effect_visible.png")
print("Test 4: Screenshot saved to /tmp/test_effect_visible.png")
exists = d.execute_script("return !!document.getElementById('__test_visible')")
print(f"Test 4: rainbow banner exists = {exists}")

d.quit()
print("\nDone!")
