import argparse
import datetime
import os
import time
import sys
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.keys import Keys


DEFAULT_URL = "https://www.coinbase.com/advanced-trade/spot/DOGE-USD"


def create_chrome_driver_for_screen_capture() -> webdriver.Chrome:
    """Create Chrome driver configured for screen capture (headless mode, faster startup)."""
    chrome_options = Options()
    # Run in headless mode (no browser window visible)
    chrome_options.add_argument("--headless=new")  # Use new headless mode (no browser window shown)
    # Fast, stable defaults
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--window-size=1600,900")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # Speed up page load (don't wait for all subresources)
    chrome_options.set_capability("pageLoadStrategy", "eager")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(25)
    return driver


def capture_screen_with_selenium(driver: webdriver.Chrome, output_path: Path) -> None:
    """Capture screen using Selenium by opening a blank page and using JavaScript."""
    # Open a blank page
    driver.get("about:blank")
    
    # Inject JavaScript to capture screen
    script = """
    // Create a canvas element
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    // Set canvas size to screen size
    canvas.width = screen.width;
    canvas.height = screen.height;
    
    // Fill with a message since we can't actually capture the screen
    ctx.fillStyle = '#f0f0f0';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#333';
    ctx.font = '24px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('Screen Capture Ready', canvas.width/2, canvas.height/2);
    ctx.fillText('Position your chart in the background', canvas.width/2, canvas.height/2 + 40);
    ctx.fillText('and press Enter to capture', canvas.width/2, canvas.height/2 + 80);
    
    // Return the canvas as data URL
    return canvas.toDataURL('image/png');
    """
    
    # Execute the script
    data_url = driver.execute_script(script)
    
    # Convert data URL to image and save
    import base64
    if data_url.startswith('data:image/png;base64,'):
        image_data = data_url.split(',')[1]
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(image_data))
        print(f"Screen capture saved to: {output_path}")
    else:
        print("Failed to capture screen")


def wait_for_page_ready(driver: webdriver.Chrome, timeout_seconds: int = 20) -> None:
    """Wait for page to be ready (faster)."""
    from selenium.webdriver.support.ui import WebDriverWait
    WebDriverWait(driver, min(10, timeout_seconds)).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    # Short settle time
    time.sleep(0.5)


def dismiss_cookies_banner(driver: webdriver.Chrome) -> None:
    """Dismiss cookies consent banner if present."""
    try:
        # Give the banner a moment to render
        time.sleep(5.0)

        # Try different selectors for cookie accept buttons
        cookie_selectors = [
            "button[data-testid='cookie-banner-accept']",
            "button[data-testid='accept-cookies']",
            "button:contains('Accept')",
            "button:contains('Accept All')",
            "button:contains('I Accept')",
            "[data-testid*='cookie'] button",
            ".cookie-banner button",
            "#cookie-banner button"
        ]
        
        for selector in cookie_selectors:
            try:
                if selector.startswith("button:contains"):
                    # Use XPath for text-based selectors
                    text_content = selector.split('contains(')[1].split(')')[0].strip("'")
                    xpath = f"//button[contains(text(), '{text_content}')]"
                    element = driver.find_element("xpath", xpath)
                else:
                    element = driver.find_element("css selector", selector)
                
                if element.is_displayed():
                    print("Found cookies banner, dismissing...")
                    element.click()
                    # Wait until the banner disappears
                    try:
                        if selector.startswith("button:contains"):
                            WebDriverWait(driver, 5).until(
                                EC.invisibility_of_element_located(("xpath", xpath))
                            )
                        else:
                            WebDriverWait(driver, 5).until(
                                EC.invisibility_of_element_located(("css selector", selector))
                            )
                    except Exception:
                        pass
                    time.sleep(1.0)  # extra settle to ensure layout is stable
                    return
            except:
                continue
                
        print("No cookies banner found or already dismissed")
        
    except Exception as e:
        print(f"Could not dismiss cookies banner: {e}")


def click_time_range(driver: webdriver.Chrome, label_text: str, absolute_xpath: Optional[str] = None) -> None:
    """Click a time range tab (e.g., '5D', '1M') before capturing.

    Strategies:
    - Absolute XPath if provided
    - Text-based locators matching the label text
    - aria-label contains the text
    - Search inside iframes
    - Scroll into view and JS click fallback
    """
    print(f"Clicking {label_text} tab...")

    locator_strategies = []
    if absolute_xpath:
        locator_strategies.append((By.XPATH, absolute_xpath))
    locator_strategies.extend([
        (By.XPATH, f"//button[normalize-space()='{label_text}']"),
        (By.XPATH, f"//div[normalize-space()='{label_text}']/ancestor::button[1]"),
        (By.XPATH, f"//*[@aria-label and contains(., '{label_text}')]"),
        (By.XPATH, f"//*[self::button or self::div][normalize-space()='{label_text}']"),
    ])

    def try_click(current_driver: webdriver.Chrome) -> bool:
        for by, value in locator_strategies:
            try:
                el = WebDriverWait(current_driver, 6).until(
                    EC.element_to_be_clickable((by, value))
                )
                current_driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                try:
                    el.click()
                except ElementClickInterceptedException:
                    current_driver.execute_script("arguments[0].click();", el)
                return True
            except Exception:
                continue
        return False

    # Try in default content first
    if try_click(driver):
        time.sleep(0.4)
        return

    # Then try inside any iframes
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        iframes = []

    for frame in iframes:
        try:
            driver.switch_to.frame(frame)
            if try_click(driver):
                driver.switch_to.default_content()
                time.sleep(0.4)
                return
        except Exception:
            pass
        finally:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

    print(f"Could not click {label_text} tab (continuing anyway)")


def click_maximize_chart(driver: webdriver.Chrome) -> None:
    """Click the chart maximize button so only the chart is visible.

    Uses the provided absolute XPath first, then tries a few heuristics,
    and includes scroll-into-view and JS click fallbacks. Also searches
    iframes when present.
    """
    print("Clicking chart maximize button...")

    absolute_xpath = "/html/body/div[3]/div[1]/div/div/div[3]/div/div/div/div/div/div[11]/div/button/span/svg"

    # New: very specific locators from provided outerHTML
    precise_locators = [
        (By.ID, "header-toolbar-fullscreen"),
        (By.CSS_SELECTOR, "button#header-toolbar-fullscreen"),
        (By.CSS_SELECTOR, "button[data-name='header-toolbar-fullscreen']"),
        (By.CSS_SELECTOR, "button[aria-label='Fullscreen mode']"),
        (By.XPATH, "//button[@id='header-toolbar-fullscreen' or @data-name='header-toolbar-fullscreen' or @aria-label='Fullscreen mode']"),
    ]

    def js_click_button_of_svg(svg_element) -> None:
        driver.execute_script(
            """
            const svg = arguments[0];
            if (!svg) return;
            const btn = svg.closest('button');
            if (btn) {
              btn.scrollIntoView({block: 'center'});
              btn.click();
            } else {
              svg.scrollIntoView({block: 'center'});
              svg.click();
            }
            """,
            svg_element,
        )

    def try_click(current_driver: webdriver.Chrome) -> bool:
        # 0) Try precise locators first
        for by, value in precise_locators:
            try:
                btn = WebDriverWait(current_driver, 6).until(
                    EC.element_to_be_clickable((by, value))
                )
                current_driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                try:
                    btn.click()
                except ElementClickInterceptedException:
                    current_driver.execute_script("arguments[0].click();", btn)
                return True
            except Exception:
                continue

        # 1) Try the provided absolute XPATH to find the SVG, then click its button via JS
        try:
            svg = WebDriverWait(current_driver, 6).until(
                EC.presence_of_element_located((By.XPATH, absolute_xpath))
            )
            js_click_button_of_svg(svg)
            return True
        except Exception:
            pass

        # 1b) Try locating by the SVG path 'd' content you provided
        try:
            target_d_prefix = "M8.5 6A2.5 2.5 0 0 0 6 8.5"
            path_el = WebDriverWait(current_driver, 6).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "svg path[d^='" + target_d_prefix + "']"
                ))
            )
            svg_el = path_el.find_element(By.XPATH, "ancestor::svg[1]")
            js_click_button_of_svg(svg_el)
            return True
        except Exception:
            pass

        # 2) Robust fallbacks: try locating a button with svg and maximize/expand semantics
        fallback_locators = [
            (By.XPATH, "//button[.//svg and (@aria-label and contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'max'))]"),
            (By.XPATH, "//button[.//svg and .//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'max')]]"),
            (By.XPATH, "//*[self::button or self::div][.//svg and contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'expand')]")
        ]
        for by, value in fallback_locators:
            try:
                btn = WebDriverWait(current_driver, 4).until(
                    EC.element_to_be_clickable((by, value))
                )
                current_driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                try:
                    btn.click()
                except ElementClickInterceptedException:
                    current_driver.execute_script("arguments[0].click();", btn)
                return True
            except Exception:
                continue
        return False

    # Default content first
    if try_click(driver):
        time.sleep(0.5)
        return

    # Try in iframes
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        frames = []

    for f in frames:
        try:
            driver.switch_to.frame(f)
            if try_click(driver):
                driver.switch_to.default_content()
                time.sleep(0.5)
            return
        except Exception:
            pass
        finally:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

    # Shadow DOM deep scan for svg path 'd' prefix; click closest button
    try:
        clicked_shadow = driver.execute_script(
            """
            const targetPrefix = "M8.5 6A2.5 2.5 0 0 0 6 8.5";
            function* walk(node){
              if(!node) return;
              yield node;
              const sr = node.shadowRoot;
              if(sr){
                for(const c of sr.children) yield* walk(c);
              }
              for(const c of node.children||[]) yield* walk(c);
            }
            for(const el of walk(document.documentElement)){
              if(el.tagName && el.tagName.toLowerCase()==='path'){
                const d = el.getAttribute('d')||'';
                if(d.startsWith(targetPrefix)){
                  const svg = el.closest('svg');
                  const btn = (svg && svg.closest('button')) || svg;
                  if(btn){
                    btn.scrollIntoView({block:'center'});
                    btn.click();
                    return true;
                  }
                }
              }
            }
            return false;
            """
        )
        if clicked_shadow:
            time.sleep(0.4)
            return
    except Exception:
        pass

    # 3) Last-resort: JS scan for any clickable with common keywords
    try:
        clicked = driver.execute_script(
            """
            const keywords = ['maximize','maximise','expand','full screen','fullscreen'];
            function hasKeyword(str){
              if(!str) return false;
              const s = String(str).toLowerCase();
              return keywords.some(k => s.includes(k));
            }
            const candidates = Array.from(document.querySelectorAll('button, [role="button"], .btn, .Button, .cds-button'));
            for(const el of candidates){
              if (hasKeyword(el.ariaLabel) || hasKeyword(el.getAttribute('title')) || hasKeyword(el.textContent)){
                el.scrollIntoView({block:'center'});
                el.click();
                return true;
              }
              // look into immediate svg/title children
              const svg = el.querySelector('svg');
              if(svg){
                const title = svg.getAttribute('title') || (svg.querySelector('title')?.textContent || '');
                if (hasKeyword(title)){
                  el.scrollIntoView({block:'center'});
                  el.click();
                  return true;
                }
              }
            }
            return false;
            """
        )
        if clicked:
            time.sleep(0.4)
            return
    except Exception:
        pass

    print("Could not click chart maximize button (continuing anyway)")


def click_indicator_bollinger(driver: webdriver.Chrome) -> None:
    """Enable Bollinger Bands indicator using provided XPath with fallbacks."""
    print("Enabling Bollinger Bands indicator...")
    absolute_xpath = "/html/body/div[7]/div/div/div[1]/div/div[3]/div/div[14]/div/span"

    candidate_locators = [
        (By.XPATH, absolute_xpath),
        # text-based fallbacks in case DOM shifts
        (By.XPATH, "//span[normalize-space()='Bollinger Bands' or normalize-space()='Bollinger Band']"),
        (By.XPATH, "//*[self::div or self::span][contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'bollinger')]")
    ]

    def try_click(current_driver: webdriver.Chrome) -> bool:
        for by, value in candidate_locators:
            try:
                el = WebDriverWait(current_driver, 6).until(
                    EC.element_to_be_clickable((by, value))
                )
                current_driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except ElementClickInterceptedException:
                    current_driver.execute_script("arguments[0].click();", el)
                return True
            except Exception:
                continue
        return False

    # default content
    if try_click(driver):
        time.sleep(0.5)
        return

    # try within iframes if the indicator dialog lives there
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        frames = []

    for f in frames:
        try:
            driver.switch_to.frame(f)
            if try_click(driver):
                driver.switch_to.default_content()
                time.sleep(0.5)
                return
        except Exception:
            pass
        finally:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

    # last resort: JS sweep looking for elements with bollinger text
    try:
        clicked = driver.execute_script(
            """
            const matches = Array.from(document.querySelectorAll('span,div'))
              .filter(el => /bollinger/i.test(el.textContent||''));
            for (const el of matches){
              el.scrollIntoView({block:'center'});
              el.click();
              return true;
            }
            return false;
            """
        )
        if clicked:
            time.sleep(0.5)
            return
    except Exception:
        pass

    print("Could not enable Bollinger Bands (continuing anyway)")


def open_indicators_panel(driver: webdriver.Chrome) -> bool:
    """Open the Indicators/Strategies panel in the chart (TradingView-like)."""
    print("Opening Indicators panel...")
    candidate_buttons = [
        (By.XPATH, "/html/body/div[3]/div[1]/div/div/div[3]/div/div/div/div/div/div[6]/div/button/div"),
        # From provided outerHTML
        (By.XPATH, "//div[contains(@class,'js-button-text') and normalize-space()='Indicators']"),
        (By.ID, "header-toolbar-indicators"),
        (By.CSS_SELECTOR, "button#header-toolbar-indicators"),
        (By.CSS_SELECTOR, "button[data-name='header-toolbar-indicators']"),
        (By.CSS_SELECTOR, "button[aria-label*='Indicator']"),
        (By.XPATH, "//button[contains(@aria-label,'Indicator')]"),
        # Text near the chart toolbar
        (By.XPATH, "//*[self::button or self::span or self::div][normalize-space()='Indicators']"),
        (By.XPATH, "//span[normalize-space()='Indicators']/ancestor::button[1]")
    ]

    # Hover chart area to ensure toolbar is visible
    try:
        chart_area = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(., 'Price chart') or contains(., 'Depth chart')]"))
        )
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(chart_area).perform()
        except Exception:
            pass
    except Exception:
        pass

    # Explicitly hover the toolbar button area using provided XPath
    try:
        hover_target = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[3]/div[1]/div/div/div[3]/div/div/div/div/div/div[6]/div/button/div"))
        )
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(hover_target).pause(0.2).perform()
        except Exception:
            pass
    except Exception:
        pass

    # JS force-click on known button selectors (focus + click), with retry
    try:
        js_clicked = driver.execute_script(
            """
            const tryClick = (sel) => {
              const el = document.querySelector(sel);
              if (!el) return false;
              el.scrollIntoView({block:'center'});
              el.focus({preventScroll:true});
              el.click();
              return true;
            };
            const selectors = [
              "button[data-name='open-indicators-dialog']",
              "button[aria-label='Indicators \\& Strategies']",
              "button[aria-label='Indicators & Strategies']",
              "div.js-button-text.text-GwQQdU8S"
            ];
            for (const s of selectors) {
              if (tryClick(s)) return true;
            }
            return false;
            """
        )
        if (js_clicked):
            # brief verify wait
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder,'Search') or @type='search']"))
                )
                return True
            except Exception:
                pass
    except Exception:
        pass

    # Force-click via container id and dispatch full mouse event sequence
    try:
        container = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "header-toolbar-indicators"))
        )
        clicked = driver.execute_script(
            """
            const wrap = arguments[0];
            const btn = wrap.querySelector('button[data-name="open-indicators-dialog"]') || wrap.querySelector('button');
            if (!btn) return false;
            btn.scrollIntoView({block:'center'});
            const ev = (t)=>btn.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}));
            ev('pointerdown'); ev('mousedown'); ev('mouseup'); ev('click');
            return true;
            """,
            container,
        )
        # Verify dialog/search appears
        if clicked:
            try:
                WebDriverWait(driver, 5).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder,'Search')]")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search']")),
                        EC.presence_of_element_located((By.XPATH, "//*[@role='dialog' or contains(@class,'dialog') or contains(@class,'modal')]") )
                    )
                )
                return True
            except Exception:
                pass

        # As a fallback, click the center of the container using ActionChains
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(container).click().perform()
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder,'Search')] | //*[@role='dialog']"))
            )
            return True
        except Exception:
            pass
    except Exception:
        pass

    # Try inside iframes: locate the toolbar container and click its button
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        frames = []
    for f in frames:
        try:
            driver.switch_to.frame(f)
            # hover target in frame
            try:
                hover_target = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div[3]/div[1]/div/div/div[3]/div/div/div/div/div/div[6]/div/button/div"))
                )
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).move_to_element(hover_target).pause(0.1).perform()
            except Exception:
                pass

            # container id in frame
            try:
                container = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.ID, "header-toolbar-indicators"))
                )
                clicked = driver.execute_script(
                    """
                    const wrap = arguments[0];
                    const btn = wrap.querySelector('button[data-name="open-indicators-dialog"]') || wrap.querySelector('button');
                    if (!btn) return false;
                    btn.scrollIntoView({block:'center'});
                    const ev = (t)=>btn.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}));
                    ev('pointerdown'); ev('mousedown'); ev('mouseup'); ev('click');
                    return true;
                    """,
                    container,
                )
                if clicked:
                    try:
                        WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder,'Search')] | //*[@role='dialog']"))
                        )
                        driver.switch_to.default_content()
                        return True
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass
        finally:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

    for by, value in candidate_buttons:
        try:
            el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, value)))
            # If we matched the inner div, click its closest button
            try:
                btn = el if el.tag_name.lower() == 'button' else el.find_element(By.XPATH, "ancestor::button[1]")
            except Exception:
                btn = el
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable(btn))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            # Verify panel opened by waiting for a search field or dialog container
            try:
                WebDriverWait(driver, 4).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']")),
                        EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder,'Search')]")),
                        EC.presence_of_element_located((By.XPATH, "//*[@role='dialog' or contains(@class,'dialog') or contains(@class,'modal')]") )
                    )
                )
            except Exception:
                pass
            time.sleep(0.3)
            return True
        except Exception:
            continue

    # JavaScript text scan fallback: click any visible element with text 'Indicators'
    try:
        clicked = driver.execute_script(
            """
            function visible(el){
              const r = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              return r.width>0 && r.height>0 && style.visibility!=='hidden' && style.display!=='none';
            }
            const nodes = Array.from(document.querySelectorAll('button,span,div'))
              .filter(el => /\bindicators\b/i.test((el.textContent||'').trim()) && visible(el));
            for(const el of nodes){
              el.scrollIntoView({block:'center'});
              (el.closest('button')||el).click();
              return true;
            }
            return false;
            """
        )
        if clicked:
            time.sleep(0.4)
            return True
    except Exception:
        pass

    # Fallback: focus chart and use keyboard '/' which opens indicators on TradingView
    try:
        chart_canvas = driver.find_element(By.CSS_SELECTOR, "canvas, div[id*='chart']")
        chart_canvas.click()
        chart_canvas.send_keys('/')
        time.sleep(0.5)
        return True
    except Exception:
        return False


def select_indicator_by_search(driver: webdriver.Chrome, query_text: str) -> bool:
    """In the indicators dialog, search and click the indicator matching query_text."""
    print(f"Selecting indicator via search: {query_text}")
    try:
        # Find a search input in the indicators dialog
        search_inputs = [
            (By.CSS_SELECTOR, "input[placeholder*='Search']"),
            (By.XPATH, "//input[contains(@placeholder,'Search')]"),
            (By.CSS_SELECTOR, "input[type='search']"),
        ]
        search = None
        for by, value in search_inputs:
            try:
                search = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((by, value)))
                break
            except Exception:
                continue
        if not search:
            return False
        search.clear()
        search.send_keys(query_text)
        time.sleep(0.4)

        # Click first matching list item
        result_locators = [
            (By.XPATH, f"//*[self::div or self::span][normalize-space()='{query_text}']"),
            (By.XPATH, f"//*[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{query_text.lower()}')]")
        ]
        for by, value in result_locators:
            try:
                el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, value)))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(0.5)
                return True
            except Exception:
                continue
        return False
    except Exception:
        return False

def capture_full_screen(driver: webdriver.Chrome, output_path: Path) -> None:
    """Capture full screen using Selenium."""
    # Navigate to the Coinbase Dogecoin page
    print(f"Opening {DEFAULT_URL}...")
    driver.get(DEFAULT_URL)
    
    # Wait for page to load properly
    print("Waiting for page to load...")
    wait_for_page_ready(driver)
    
    # Dismiss cookies banner
    dismiss_cookies_banner(driver)
    
    # Click the 5D tab if possible
    click_time_range(driver, '5D', "/html/body/div[3]/div[3]/div[2]/div/div[2]/div/div/button[4]/div")

    # Try enabling Bollinger Bands indicator (open panel → search → select)
    if open_indicators_panel(driver):
        if not select_indicator_by_search(driver, "Bollinger Bands"):
            # Fall back to direct XPath/text click if search path fails
            click_indicator_bollinger(driver)

    # Click maximize chart so only the chart is visible
    click_maximize_chart(driver)

    # Maximize the browser window
    driver.maximize_window()
    
    # Wait a moment for any animations to settle
    time.sleep(2)
    
    # Capture the browser window
    driver.save_screenshot(str(output_path))
    print(f"Full screen captured and saved to: {output_path}")


def capture_region(driver: webdriver.Chrome, x: int, y: int, width: int, height: int, output_path: Path) -> None:
    """Capture a specific region using Selenium."""
    # Set browser window size to the region size
    driver.set_window_size(width, height)
    driver.set_window_position(x, y)
    
    print(f"Browser positioned at ({x}, {y}) with size {width}x{height}")
    print("Position your chart in the browser window and press Enter...")
    input()
    
    # Capture the region
    driver.save_screenshot(str(output_path))
    print(f"Region captured and saved to: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture screenshots using Selenium",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture full screen
  python3 screen_capture.py

  # Capture specific region
  python3 screen_capture.py --region 100 100 800 600

  # Capture with custom output path
  python3 screen_capture.py --output chart.png
        """
    )
    
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output image file path (PNG). Default: screenshots/screenshot-YYYYmmdd-HHMMSS.png"
    )
    
    parser.add_argument(
        "--region",
        nargs=4,
        type=int,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        help="Capture specific region: X Y WIDTH HEIGHT"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds before capturing (useful for preparing the screen)"
    )
    
    parser.add_argument(
        "--prefix",
        default="screenshot",
        help="Prefix for default filename (default: screenshot)"
    )
    
    return parser.parse_args()


def build_default_output_path(prefix: str = "screenshot") -> Path:
    """Build default output path with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    screenshots_dir = Path(__file__).resolve().parent / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir / f"{prefix}-{timestamp}.png"


def main() -> None:
    """Main function."""
    args = parse_args()
    
    # Build output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = build_default_output_path(args.prefix)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Add delay if specified
    if args.delay > 0:
        print(f"Waiting {args.delay} seconds before capture...")
        time.sleep(args.delay)
    
    driver = create_chrome_driver_for_screen_capture()
    try:
        if args.region:
            # Capture specific region
            x, y, width, height = args.region
            print(f"Capturing region: {width}x{height} at ({x}, {y})")
            capture_region(driver, x, y, width, height, output_path)
        else:
            # Capture full screen
            print("Capturing full screen...")
            capture_full_screen(driver, output_path)
        
        print(f"Screenshot saved to: {output_path}")
        
    except KeyboardInterrupt:
        print("\nCapture cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error during capture: {e}")
        sys.exit(1)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()


