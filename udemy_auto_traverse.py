"""Udemy course traversal helper (Playwright).

- Opens a dedicated persistent Chromium profile so you can sign in normally.
- Waits for video lessons to finish, then clicks Next when available.
- Waits for video lessons to finish.
- For every non-video lesson (reading, quiz, practice test, assignment, etc.),
  immediately attempts to click Next/Continue.
- If Udemy requires an activity to be completed before advancing, stops safely.
- Does not bypass authentication, paywalls, or course restrictions.

Install:  py -m pip install playwright
          py -m playwright install chromium
Run:      py udemy_auto_traverse.py
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------- Configuration ----------------------------
COURSE_URL = "https://www.udemy.com/course/fnb-financial-literacy/learn/lecture/39234726#overview"  # Optional: paste the URL of the Udemy course curriculum/first lesson.
PROFILE_DIR = Path(__file__).resolve().parent / "udemy_browser_profile"
LOG_FILE = Path(__file__).resolve().parent / "udemy_traversal.log"
NON_VIDEO_SETTLE_SECONDS = 2  # Brief wait for non-video lesson controls to render.
NAVIGATION_TIMEOUT_MS = 15_000
POLL_SECONDS = 2
MAX_IDLE_SECONDS = 180       # Stop if the page does not become recognizable.
AUTO_START_VIDEO = True
# ----------------------------------------------------------------------

NEXT_PATTERNS = re.compile(r"^(next|continue|next lecture|next lesson|complete and continue)$", re.I)
BLOCKING_PATTERNS = re.compile(r"quiz|practice test|assignment|coding exercise|exam|assessment", re.I)


def log(message: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def visible(locator) -> bool:
    try:
        return locator.count() > 0 and locator.first.is_visible()
    except Exception:
        return False


def lesson_title(page) -> str:
    # Prefer visible lesson headings; fall back to the document title/URL.
    for selector in ["h1", "[data-purpose*='lecture-title']", "[data-purpose*='curriculum-item-link']"]:
        loc = page.locator(selector)
        if visible(loc):
            try:
                text = loc.first.inner_text(timeout=1500).strip()
                if text:
                    return text[:180]
            except Exception:
                pass
    try:
        return (page.title() or page.url)[:180]
    except Exception:
        return page.url[:180]


def detect_blocking_activity(page) -> bool:
    """Compatibility helper: identify activity-like pages for logging only.

    These activities are not treated as a reason to pause. The main loop tries
    the normal Next/Continue control for every non-video lesson.
    """
    try:
        for selector in ["h1", "h2", "[data-purpose*='assessment']", "[data-purpose*='quiz']"]:
            loc = page.locator(selector)
            if visible(loc):
                try:
                    if BLOCKING_PATTERNS.search(loc.first.inner_text(timeout=1000)):
                        return True
                except Exception:
                    pass
        return False
    except Exception:
        return False


def find_next_button(page):
    # Accessible names first, then common Udemy data-purpose selectors.
    for name in ["Next", "Continue", "Next lecture", "Next lesson", "Complete and continue"]:
        try:
            loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I))
            if visible(loc) and not loc.first.is_disabled():
                return loc.first
        except Exception:
            pass
    for selector in [
        "button[data-purpose*='go-to-next']",
        "button[data-purpose*='next-lecture']",
        "a[data-purpose*='go-to-next']",
        "[data-purpose='go-to-next-lecture']",
    ]:
        loc = page.locator(selector)
        if visible(loc):
            try:
                if not loc.first.is_disabled():
                    return loc.first
            except Exception:
                return loc.first
    # Text-based fallback, deliberately restricted to buttons/links.
    for tag in ["button", "a"]:
        loc = page.locator(tag).filter(has_text=re.compile(r"^(Next|Continue|Next lecture|Next lesson)$", re.I))
        if visible(loc):
            try:
                if not loc.first.is_disabled():
                    return loc.first
            except Exception:
                return loc.first
    return None


def get_video_state(page):
    """Returns (found_video, ended, paused, current_time, duration)."""
    try:
        return page.evaluate("""() => {
          const v = document.querySelector('video');
          if (!v) return {found:false};
          return {found:true, ended:!!v.ended, paused:!!v.paused,
                  currentTime:Number(v.currentTime||0), duration:Number(v.duration||0)};
        }""")
    except Exception:
        return {"found": False}


def start_video_if_needed(page) -> None:
    state = get_video_state(page)
    if not state.get("found") or not state.get("paused") or state.get("ended"):
        return
    # Clicking the native video element may toggle playback; only try when clearly paused.
    try:
        video = page.locator("video").first
        if video.is_visible():
            video.click(timeout=1500)
            log("Tried to start paused video. Verify playback in the browser.")
    except Exception:
        log("Could not start video automatically; please press Play manually.")


def wait_for_video_end(page, title: str) -> bool:
    log(f"Video lesson detected: {title}")
    if AUTO_START_VIDEO:
        start_video_if_needed(page)
    started_at = time.time()
    last_report = 0
    while True:
        state = get_video_state(page)
        if not state.get("found"):
            log("Video element disappeared before completion; re-checking lesson type.")
            return False
        if state.get("ended"):
            log("Video playback ended.")
            return True
        # Some lessons expose a completion button after the video reaches its end.
        duration = state.get("duration", 0) or 0
        current = state.get("currentTime", 0) or 0
        if duration > 0 and current >= duration - 1.5:
            return True
        if time.time() - last_report >= 30:
            if duration > 0:
                log(f"Video progress: {int(current)} / {int(duration)} seconds")
            else:
                log("Waiting for video playback; duration is not available yet.")
            last_report = time.time()
        # Do not impose a fixed timeout on a long lesson. User can stop with Ctrl+C.
        time.sleep(POLL_SECONDS)


def click_next_and_confirm(page, previous_url: str, previous_title: str) -> bool:
    button = find_next_button(page)
    if button is None:
        log("No usable Next/Continue button found. Stopping for manual review.")
        return False
    try:
        label = (button.inner_text(timeout=1000) or "Next").strip().replace("\n", " ")
    except Exception:
        label = "Next"
    log(f"Clicking navigation control: {label}")
    try:
        button.click(timeout=NAVIGATION_TIMEOUT_MS)
    except Exception as exc:
        log(f"Could not click Next: {exc}. Stopping for manual review.")
        return False
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except PlaywrightTimeoutError:
        pass
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            if page.url != previous_url or lesson_title(page) != previous_title:
                log(f"Moved to lesson: {lesson_title(page)}")
                return True
        except Exception:
            pass
        time.sleep(1)
    log("Clicked Next, but lesson change could not be verified. Stopping to avoid repeated clicks.")
    return False


def prepare_non_video_lesson(page, title: str) -> None:
    """Briefly allow navigation controls to render; do not spend time on content."""
    if detect_blocking_activity(page):
        log(f"Non-video activity detected; attempting to skip: {title}")
    else:
        log(f"Non-video lesson detected; attempting to skip: {title}")
    page.wait_for_timeout(NON_VIDEO_SETTLE_SECONDS * 1000)


def main() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log("Starting Udemy course traversal helper.")
    log(f"Persistent browser profile: {PROFILE_DIR}")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="msedge",
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(5000)
        if COURSE_URL.strip():
            page.goto(COURSE_URL.strip(), wait_until="domcontentloaded")
        else:
            page.goto("https://www.udemy.com/", wait_until="domcontentloaded")
        print("\nSign in to Udemy in the opened browser if needed, then open the course lesson.")
        print("Video lessons will be watched to completion; all non-video lessons will be skipped when Udemy permits.")
        print("When the lesson page is ready, return to this terminal and press Enter.")
        input("Ready? ")

        visited = set()
        try:
            while True:
                try:
                    page.wait_for_timeout(1000)
                    current_url = page.url
                    title = lesson_title(page)
                    key = (current_url, title)
                    if key in visited:
                        log("This lesson appears to have been visited already; stopping to avoid a loop.")
                        break
                    visited.add(key)
                    log(f"Current lesson: {title} | {current_url}")

                    video_state = get_video_state(page)
                    if video_state.get("found"):
                        completed = wait_for_video_end(page, title)
                        if not completed:
                            # Video element disappeared; give the page a moment to settle and re-evaluate.
                            page.wait_for_timeout(2000)
                            if get_video_state(page).get("found"):
                                continue
                    else:
                        prepare_non_video_lesson(page, title)

                    if not click_next_and_confirm(page, current_url, title):
                        print("\nTraversal paused. Inspect the browser; if needed, update the selectors/configuration in the script.")
                        break
                    # Let the next lesson render before detecting its type.
                    page.wait_for_timeout(2500)
                except KeyboardInterrupt:
                    log("Stopped by user.")
                    break
        finally:
            context.close()
            log("Browser session closed.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user.")
