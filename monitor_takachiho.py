import os
import re
import sys
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = os.getenv("TARGET_URL", "https://eipro.jp/takachiho1/eventCalendars/index")
TARGET_DATE = os.getenv("TARGET_DATE", "2026-06-04")  # 6/4
TARGET_TEXTS = [s.strip() for s in os.getenv("TARGET_TEXTS", "○,空き,予約可,会員登録せずに予約").split(",") if s.strip()]
NG_TEXTS = [s.strip() for s in os.getenv("NG_TEXTS", "×,締め切り,完売,砂時計").split(",") if s.strip()]
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN")
SCREENSHOT_PATH = os.getenv("SCREENSHOT_PATH", "takachiho.png")

def pushover(title: str, message: str, priority: int = 1):
    if not PUSHOVER_USER_KEY or not PUSHOVER_APP_TOKEN:
        print("Pushover secrets not set; skip push notification.")
        return
    resp = requests.post("https://api.pushover.net/1/messages.json", data={
        "token": PUSHOVER_APP_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "title": title,
        "message": message,
        "url": URL,
        "url_title": "打開高千穗划船預約頁",
        "priority": priority,
    }, timeout=20)
    print(f"Pushover status: {resp.status_code} {resp.text[:200]}")
    resp.raise_for_status()

def try_go_to_date(page):
    """Best-effort navigation for common FullCalendar implementations."""
    target = TARGET_DATE
    js = f"""
    (() => {{
      const d = '{target}';
      try {{
        if (window.jQuery) {{
          const $ = window.jQuery;
          if ($('#calendar').length && $('#calendar').fullCalendar) {{ $('#calendar').fullCalendar('gotoDate', d); return 'jquery-fullcalendar'; }}
          if ($('.calendar').length && $('.calendar').fullCalendar) {{ $('.calendar').fullCalendar('gotoDate', d); return 'jquery-fullcalendar-class'; }}
        }}
        const els = document.querySelectorAll('.fc, #calendar, .calendar');
        for (const el of els) {{
          if (el._calendar && el._calendar.gotoDate) {{ el._calendar.gotoDate(d); return 'fullcalendar-v4'; }}
        }}
        if (window.calendar && window.calendar.gotoDate) {{ window.calendar.gotoDate(d); return 'window-calendar'; }}
      }} catch(e) {{ return 'error:' + e.message; }}
      return 'not-found';
    }})()
    """
    try:
        mode = page.evaluate(js)
        print("gotoDate mode:", mode)
        page.wait_for_timeout(2500)
    except Exception as e:
        print("gotoDate failed:", e)

    # Fallback: if target month/date not shown, click next buttons up to 8 times.
    y, m, d = TARGET_DATE.split("-")
    visible_markers = [f"{int(m)}/{int(d)}", f"{int(m)}月{int(d)}日", f"{y}-{m}-{d}", f"{y}/{int(m)}/{int(d)}"]
    try:
        text = page.locator("body").inner_text(timeout=5000)
        if any(v in text for v in visible_markers):
            return
    except Exception:
        pass

    next_selectors = ["button.fc-next-button", ".fc-next-button", "text=＞", "text=>", "text=次", "text=翌"]
    for _ in range(8):
        clicked = False
        for sel in next_selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=2000)
                    clicked = True
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                continue
        if not clicked:
            break
        try:
            text = page.locator("body").inner_text(timeout=5000)
            if any(v in text for v in visible_markers):
                break
        except Exception:
            pass

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Checking {TARGET_DATE} at {URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1400}, locale="ja-JP", timezone_id="Asia/Tokyo")
        try:
            page.goto(URL, wait_until="networkidle", timeout=60000)
        except PlaywrightTimeoutError:
            print("Page load timeout; continue with current content.")
        page.wait_for_timeout(3000)
        try_go_to_date(page)
        try:
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            print(f"Screenshot saved: {SCREENSHOT_PATH}")
        except Exception as e:
            print("screenshot failed:", e)
        body_text = page.locator("body").inner_text(timeout=15000)
        html = page.content()
        browser.close()

    combined = body_text + "\n" + html
    print("--- PAGE TEXT SAMPLE ---")
    print(body_text[:3000])

    # Conservative detection: if available-like text appears and not only obvious sold-out state.
    hit_available = any(t in combined for t in TARGET_TEXTS)
    hit_ng = any(t in combined for t in NG_TEXTS)

    # Stronger target-date heuristic: target date appears near availability terms.
    date_patterns = [TARGET_DATE, TARGET_DATE.replace("-", "/"), f"{int(TARGET_DATE[5:7])}/{int(TARGET_DATE[8:10])}", f"{int(TARGET_DATE[5:7])}月{int(TARGET_DATE[8:10])}日"]
    near_target = False
    for dp in date_patterns:
        for m in re.finditer(re.escape(dp), combined):
            window = combined[max(0, m.start()-800): m.end()+1200]
            if any(t in window for t in TARGET_TEXTS):
                near_target = True
                break
        if near_target:
            break

    # If the site does not expose date text clearly, fall back to available terms after navigation.
    available = near_target or (hit_available and not hit_ng)

    if available:
        msg = f"高千穗划船 {TARGET_DATE} 疑似有名額釋出，請立刻打開預約頁確認：{URL}"
        print("AVAILABLE:", msg)
        pushover("高千穗划船可能有名額！", msg, priority=1)
        return 0
    else:
        print(f"No availability detected for {TARGET_DATE}. available_terms={hit_available}, ng_terms={hit_ng}, near_target={near_target}")
        return 0

if __name__ == "__main__":
    sys.exit(main())
