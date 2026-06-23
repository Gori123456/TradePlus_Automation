import subprocess
import pyautogui
import pygetwindow as gw
import time
import sys

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
CRM_EXE_PATH = r"C:\CRM\crm.exe"
ERROR_TITLE  = "User Error"
LOGIN_TITLE  = "Login"
USERNAME     = "jating"
PASSWORD     = "qwer1234"
TIME_VALUE   = "2200"        # Entering 2200 for 10:00 PM
LAUNCH_WAIT  = 10
# ─────────────────────────────────────────

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2

def launch_crm():
    print(f"[*] Launching CRM: {CRM_EXE_PATH}")
    subprocess.Popen(CRM_EXE_PATH)
    time.sleep(LAUNCH_WAIT)

def dismiss_popup():
    try:
        wins = gw.getWindowsWithTitle(ERROR_TITLE)
        if wins:
            wins[0].activate()
            time.sleep(0.5)
            pyautogui.press("enter")
            print("[✓] Popup dismissed.")
            return True
    except: pass
    return False

def clear_and_type(value):
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    time.sleep(0.2)
    pyautogui.typewrite(value, interval=0.05)

def type_in_spinner(value):
    """
    Forces the spinner to accept the value by 
    selecting all, deleting, and typing slowly.
    """
    # Select all existing numbers
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.press("delete")
    time.sleep(0.2)
    
    # Type the time digits
    print(f"[*] Typing digits: {value}")
    pyautogui.typewrite(value, interval=0.1)
    
    # Crucial: Press 'Enter' or 'Tab' to 'lock in' the value in a spinner
    time.sleep(0.3)
    pyautogui.press("enter") 

def auto_login():
    launch_crm()

    # Handle Popup
    for _ in range(5):
        if dismiss_popup(): break
        time.sleep(1)

    # Find Login Window
    win = None
    for _ in range(10):
        wins = gw.getWindowsWithTitle(LOGIN_TITLE)
        if wins:
            win = wins[0]
            break
        time.sleep(1)

    if not win:
        print("[✗] Login window not found!")
        sys.exit(1)

    win.activate()
    time.sleep(1)

    # 1. USERNAME
    print("[*] Entering Username...")
    # Click User field based on your image (relative position)
    pyautogui.click(win.left + 150, win.top + 130) 
    clear_and_type(USERNAME)

    # 2. PASSWORD
    print("[*] Tabbing to Password...")
    pyautogui.press("tab")
    time.sleep(0.5)
    clear_and_type(PASSWORD)

    # 3. TIME IN (The Spinner)
    print("[*] Tabbing to Time field...")
    # In some apps, you need to Tab twice to get past the internal controls
    pyautogui.press("tab") 
    time.sleep(0.5)
    
    # If it's still not focused, try one more click or tab
    type_in_spinner(TIME_VALUE)

    # 4. SUBMIT
    print("[*] Finalizing Login...")
    # Using Tab to navigate to the 'Login' button is safer than coordinates
    # Based on your UI, Login is likely 2 tabs away from Time
    pyautogui.press("tab")
    time.sleep(0.2)
    pyautogui.press("tab")
    time.sleep(0.2)
    pyautogui.press("enter")
    
    print("[✓] Automation sequence complete.")

if __name__ == "__main__":
    auto_login()