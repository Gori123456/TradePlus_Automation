import ctypes
import json
import os
import sys
import time
import win32api
import win32con
import win32gui
from datetime import datetime
from pywinauto import mouse
from pywinauto import Application
from pywinauto.keyboard import send_keys

# ══════════════════════════════════════════════
# FILE DEPENDENCY IMPORTS
# ══════════════════════════════════════════════
from core.launcher import start_application
from pages.login_page import LoginPage
from pages.main_page import MainPage
from pages.share_payout_page import SharePayoutPage
from pages.pledge_page import PledgePage
from pages.control_center_page import ControlCenterPage

# ══════════════════════════════════════════════
# AUTOMATED TERMINAL LOG RECORDER (TEE OUTPUT)
# ══════════════════════════════════════════════
class TerminalLogger:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_folder_path = os.path.join(BASE_DIR, "log")
capture_folder_path = os.path.join(BASE_DIR, "Capture_Data")

if not os.path.exists(log_folder_path):
    os.makedirs(log_folder_path)

if not os.path.exists(capture_folder_path):
    os.makedirs(capture_folder_path)

log_filename = f"log_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.txt"
log_file_fullpath = os.path.join(log_folder_path, log_filename)

log_file_stream = open(log_file_fullpath, "w", encoding="utf-8")
sys.stdout = TerminalLogger(sys.__stdout__, log_file_stream)
sys.stderr = TerminalLogger(sys.__stderr__, log_file_stream)

print(f"========================================================")
print(f"Log Session Started At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Console output path: {log_file_fullpath}")
print(f"Screenshot storage path: {capture_folder_path}")
print(f"========================================================")


# ══════════════════════════════════════════════
# ENTIRE WINDOW SCREENSHOT UTILITY
# ══════════════════════════════════════════════
def take_entire_window_screenshot(filename_prefix):
    try:
        time.sleep(1.5) 
        main_hwnd = win32gui.FindWindow("WindowsForms10.Window.8.app.0.141b42a_r7_ad1", "TradePlusX")
        if main_hwnd:
            win32gui.ShowWindow(main_hwnd, win32con.SW_SHOWMAXIMIZED)
            time.sleep(0.5)
            win32gui.BringWindowToTop(main_hwnd)
            time.sleep(0.5)
            
            app_ctx = Application(backend="win32").connect(handle=main_hwnd)
            master_win = app_ctx.window(handle=main_hwnd)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_filename = f"{filename_prefix}_{timestamp}.png"
            save_path = os.path.join(capture_folder_path, save_filename)
            
            img = master_win.capture_as_image()
            img.save(save_path)
            print(f"  ✓ Entire maximized application window screenshot saved: {save_filename}")
        else:
            print(f"  ⚠ Main TradePlusX handle not found. Cannot capture screenshot for '{filename_prefix}'.")
    except Exception as e:
        print(f"  ⚠ Failed to capture entire window screenshot for '{filename_prefix}': {e}")


REPORT_WINDOW_KEYWORDS = [
    "file import report", "obligation", "comparison", "money sheet", 
    "reconciliation", "mismatch", "accumulation", "bill reconcil", "slip printing"
]


def _find_close_button_in_window(report_hwnd):
    candidates = []
    def _enum(hwnd, _):
        try:
            raw_title = win32gui.GetWindowText(hwnd).strip()
            clean = raw_title.replace("&", "").lower()  
            cls   = win32gui.GetClassName(hwnd)
            if clean == "close" and "button" in cls.lower():
                rect = win32gui.GetWindowRect(hwnd)
                candidates.append((hwnd, rect))
        except:
            pass
        return True

    try:
        win32gui.EnumChildWindows(report_hwnd, _enum, None)
    except:
        pass

    if not candidates:
        return None, None
    candidates.sort(key=lambda c: c[1][0], reverse=True)
    return candidates[0]


def close_any_open_report_tabs(context_label="REPORT INTERCEPT", wait_for_render=True):
    if wait_for_render:
        time.sleep(4.0)

    main_hwnd = win32gui.FindWindow("WindowsForms10.Window.8.app.0.141b42a_r7_ad1", "TradePlusX")
    report_windows = []

    def _check(hwnd):
        try:
            if hwnd == main_hwnd: return
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if any(kw in title for kw in REPORT_WINDOW_KEYWORDS):
                    rect = win32gui.GetWindowRect(hwnd)
                    report_windows.append((hwnd, win32gui.GetWindowText(hwnd), rect))
        except: pass

    win32gui.EnumWindows(lambda hwnd, _: [_check(hwnd), True][1], None)
    if main_hwnd:
        try: win32gui.EnumChildWindows(main_hwnd, lambda hwnd, _: [_check(hwnd), True][1], None)
        except: pass

    seen = set()
    unique_reports = [e for e in report_windows if not (e[0] in seen or seen.add(e[0]))]

    if not unique_reports:
        print(f"  [{context_label}] No report viewer windows detected. Continuing ✓")
        return

    print(f"  [{context_label}] {len(unique_reports)} report window(s) found — closing now...")

    for hwnd, title, rect in unique_reports:
        print(f"  [{context_label}] Closing: '{title}'")
        take_entire_window_screenshot("Report_AutoClose")
        time.sleep(0.5)

        closed = False
        BM_CLICK = 0x00F5
        close_btn, close_btn_rect = _find_close_button_in_window(hwnd)
        if close_btn:
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.4)
                win32api.SendMessage(close_btn, BM_CLICK, 0, 0)
                time.sleep(2.0)
                if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    closed = True
                else:
                    cx = (close_btn_rect[0] + close_btn_rect[2]) // 2
                    cy = (close_btn_rect[1] + close_btn_rect[3]) // 2
                    mouse.click(button='left', coords=(cx, cy))
                    time.sleep(2.0)
                    closed = True
            except: pass

        if not closed:
            try:
                win32api.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(2.0)
                if not win32gui.IsWindow(hwnd): closed = True
            except: pass

        if not closed:
            mouse.click(button='left', coords=(rect[2] - 14, rect[1] + 14))
            time.sleep(2.0)

    if main_hwnd:
        cc_hwnd = None
        try:
            win32gui.EnumChildWindows(main_hwnd, lambda h, _: [exec('nonlocal cc_hwnd\nif "control center" in win32gui.GetWindowText(h).lower() and win32gui.IsWindowVisible(h): cc_hwnd=h'), True][1], None)
        except: pass
        if cc_hwnd:
            try:
                win32gui.ShowWindow(cc_hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(cc_hwnd)
                time.sleep(1.5)
            except: pass


# ══════════════════════════════════════════════
# CONFIGURATION LOADERS & LAUNCHER
# ══════════════════════════════════════════════
config_path = os.path.join(BASE_DIR, "config.json")
actions_path = os.path.join(BASE_DIR, "payout_workflow.json")

with open(config_path, "r") as f:
    config_data = json.load(f)

with open(actions_path, "r") as f:
    workflow_data = json.load(f)

should_auto_close = workflow_data.get("auto_close", False)
pipeline = workflow_data.get("execution_pipeline", [])

app = start_application(config_data["application_path"])
time.sleep(6)

main_hwnd = win32gui.FindWindow("WindowsForms10.Window.8.app.0.141b42a_r7_ad1", "TradePlusX")
if main_hwnd:
    win32gui.ShowWindow(main_hwnd, win32con.SW_SHOWMAXIMIZED)
    time.sleep(1.0)

login_page = LoginPage(app)
print("Application Started")
login_page.login(config_data["username"], config_data["password"])
print("Login Completed")
time.sleep(6)

main_page = MainPage(app)
print("Starting Configured Workflows Sequence...")

try:
    # ══════════════════════════════════════════════
    # DYNAMIC PIPELINE RUNNER (LOOPS IN EXACT ORDER)
    # ══════════════════════════════════════════════
    for step_idx, step_cfg in enumerate(pipeline):
        if not step_cfg.get("enabled", False):
            continue

        module_type = step_cfg.get("module", "").lower()
        print(f"\n[PIPELINE STEP {step_idx + 1}] Processing Module: {module_type.upper()}")

        # ── ROUTINE 1: CONTROL CENTER ──
        if module_type == "control_center":
            while True:
                close_any_open_report_tabs(context_label=f"PRE-FLIGHT CC", wait_for_render=False)
                main_page.click_submenu_by_index("Utilities", step_cfg["index"], "Control Center")
                time.sleep(3.0)
                
                imports_w = step_cfg.get("file_imports", {})
                process_w = step_cfg.get("processes", {})
                others_w  = step_cfg.get("others", {})
                
                page = ControlCenterPage(app)
                status = page.process(
                    date               = step_cfg.get("date"),
                    click_file_imports = imports_w.get("enabled", False),
                    imports_product    = imports_w.get("product") if imports_w.get("enabled") else None,
                    imports_type       = imports_w.get("type") if imports_w.get("enabled") else None,
                    check_bse_cash     = imports_w.get("check_bse_cash", False) if imports_w.get("enabled") else False,
                    check_nse_cash     = imports_w.get("check_nse_cash", False) if imports_w.get("enabled") else False,
                    bse_files_workflow = imports_w.get("bse_files_workflow", {}),
                    nse_files_workflow = imports_w.get("nse_files_workflow", {}),
                    
                    click_processes    = process_w.get("enabled", False),
                    product            = process_w.get("product") if process_w.get("enabled") else None,
                    for_date           = process_w.get("for_date") if process_w.get("enabled") else None,
                    click_fetch        = process_w.get("click_fetch", False) if process_w.get("enabled") else False,
                    
                    click_others       = others_w.get("enabled", False),
                    exchange           = others_w.get("exchange") if others_w.get("enabled") else None,
                    settlement         = others_w.get("settlement") if others_w.get("enabled") else None,
                    exchange_obligation_reconciliation = others_w.get("exchange_obligation_reconciliation", False) if others_w.get("enabled") else False,
                    unprocess_bills    = others_w.get("unprocess_bills", False) if others_w.get("enabled") else False,
                    raw_workflow_config = step_cfg
                )
                
                if status == "RESTART":
                    print(f"\n[LOOP OVERRIDE] Restart requested. Retrying Control Center block...")
                    time.sleep(3.0)
                    continue
                
                print("Finishing Control Center Suite. Closing context safely...")
                try:
                    page.close_window()
                    time.sleep(2.0)
                except Exception as e:
                    print(f"  ⚠ Handshake warning closing CC window: {e}")

                close_any_open_report_tabs(context_label=f"POST-STEP CC", wait_for_render=True)
                time.sleep(1.0)
                take_entire_window_screenshot(f"Control_Center_Step_{step_idx + 1}")
                break

        # ── ROUTINE 2: DEMAT AUTO ENTRIES ──
        # ── ROUTINE 2: DEMAT AUTO ENTRIES ──
        elif module_type == "demat_auto_entries":
            target_name = step_cfg.get("target_process_name", "Demat Auto Entries")
            print(f"Executing Demat Auto Entries -> Target: '{target_name}'...")
            main_page.click_submenu_by_index("Utilities", step_cfg["index"], target_name)
            time.sleep(2.5)
            
            page = SharePayoutPage(app)
            page.process(
                step_cfg["date"],
                step_cfg["settlement_name"],
                step_cfg["target_process_name"]
            )
            time.sleep(1.5)
            
            print("Cleaning up any generated report preview window contexts to release main window frame hook locks...")
            close_any_open_report_tabs(context_label=f"POST-STEP DEMAT", wait_for_render=True)
            
            # ==============================================================================
            # CRITICAL AUTOMATION FIX: ADD REST BUFFER TO RE-ENABLE WINDOW FRAME INTERACTION
            # ==============================================================================
            print("  [REST buffer] Allowing main window frame controls to unlock and re-enable active focus...")
            time.sleep(3.0) 
            
            take_entire_window_screenshot(f"Demat_Auto_Entries_Step_{step_idx + 1}")
            
        # ── ROUTINE 3: PLEDGE MANAGEMENT ──
        elif module_type == "pledge_management":
            print(f"Executing Pledge Management...")
            main_page.click_submenu_by_index("Utilities", step_cfg["index"], "Pledge Management")
            time.sleep(2.5)
            
            page = PledgePage(app)
            page.process(
                tab_name              = step_cfg["tab_name"],
                manage_action         = step_cfg.get("manage_action"),
                manage_date           = step_cfg.get("manage_date"),
                items_sold_by_client  = step_cfg.get("items_sold_by_client"),
                with_epn_blk          = step_cfg.get("with_epn_blk"),
                click_fetch           = step_cfg.get("click_fetch", False)
            )
            print("Stabilizing workspace context...")
            time.sleep(2.0)
            take_entire_window_screenshot(f"Pledge_Management_Step_{step_idx + 1}")

    print("\nAll enabled automation pipeline tasks completed successfully.")

    # ══════════════════════════════════════════════
    # MASTER APPLICATION SYSTEM CLOSE & CONFIRMATION
    # ══════════════════════════════════════════════
    if should_auto_close:
        print("Initializing Master Shutdown routine...")
        time.sleep(1.5)
        main_hwnd = win32gui.FindWindow("WindowsForms10.Window.8.app.0.141b42a_r7_ad1", "TradePlusX")
        if main_hwnd:
            win32gui.PostMessage(main_hwnd, win32con.WM_SYSCOMMAND, win32con.SC_CLOSE, 0)
            time.sleep(3.0)
            popup_hwnd = None
            def find_confirmation_box(hwnd, extra):
                global popup_hwnd
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                if "are you sure" in title.lower() or "exception" in title.lower() or "#32770" in cls:
                    if win32gui.IsWindowVisible(hwnd) and hwnd != main_hwnd: popup_hwnd = hwnd
                return True
            win32gui.EnumWindows(find_confirmation_box, None)
            if popup_hwnd:
                send_keys("{ENTER}")
                time.sleep(1.5)
            if win32gui.IsWindow(main_hwnd):
                import subprocess
                subprocess.run("taskkill /f /im TradePlusX.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

except Exception as e:
    print(f"\nERROR OCCURRED DURING WORKFLOW RUN: {e}")
    import traceback
    traceback.print_exc()
    input("\nPress Enter to Exit...")
finally:
    print(f"\nClosing log file handle session. Goodbye.")
    log_file_stream.close()
print("\nProgram Finished")
time.sleep(1.0)