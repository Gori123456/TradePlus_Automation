import time
import threading
import win32gui
import win32con
import win32api
from pywinauto import mouse
from pywinauto.keyboard import send_keys

TRADEPLUS_CLASS = "WindowsForms10.Window.8.app.0.141b42a_r7_ad1"
BUTTON_CLASS    = "WindowsForms10.BUTTON.app.0.141b42a_r7_ad1"
COMBO_CLASS     = "WindowsForms10.COMBOBOX.app.0.141b42a_r7_ad1"
DATETIME_CLASS  = "WindowsForms10.SysDateTimePick32.app.0.141b42a_r7_ad1"


def click_center(rect):
    x = (rect[0] + rect[2]) // 2
    y = (rect[1] + rect[3]) // 2
    mouse.click(button='left', coords=(x, y))
    time.sleep(0.3)


def get_all_children(parent_hwnd):
    children = []
    def cb(hwnd, _):
        try:
            children.append((
                hwnd,
                win32gui.GetClassName(hwnd),
                win32gui.GetWindowText(hwnd),
                win32gui.GetWindowRect(hwnd),
                win32gui.IsWindowVisible(hwnd)
            ))
        except:
            pass
        return True
    win32gui.EnumChildWindows(parent_hwnd, cb, None)
    return children


def is_checked(hwnd):
    result = win32api.SendMessage(hwnd, win32con.BM_GETCHECK, 0, 0)
    return result == win32con.BST_CHECKED


# ══════════════════════════════════════════════
# SIMPLIFIED KEYBOARD POPUP DISMISSER
# ══════════════════════════════════════════════
def async_popup_killer(main_hwnd):
    """
    Runs on a parallel background thread. Watches the window tree instantly
    and forces an ENTER key stroke to clear the popup as soon as it surfaces.
    """
    print("[THREAD WATCHER] Scanning for dialog box contexts...")
    
    for attempt in range(35):  
        time.sleep(0.2)
        popup_hwnd = None
        
        all_app_children = get_all_children(main_hwnd)
        
        for hwnd, cls, title, rect, vis in all_app_children:
            if vis and ("information" in title.lower() or "confirm" in title.lower() or not title):
                if "#32770" in cls or "WindowsForms10.Window" in cls:
                    if rect[2] - rect[0] < 600 and rect[3] - rect[1] < 400:
                        popup_hwnd = hwnd
                        break
        
        if popup_hwnd:
            print(f"[THREAD WATCHER] Pop-up window identified: handle={popup_hwnd}. Dismissing via ENTER...")
            try:
                win32gui.ShowWindow(popup_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(popup_hwnd)
                time.sleep(0.15)
                
                send_keys("{ENTER}")
                print("[THREAD WATCHER] ✓ Pressed ENTER to dismiss the popup ✓")
                return True
            except Exception as e:
                print(f"[THREAD WATCHER] Keystroke injection missed, using close signal fallback: {e}")
                win32gui.PostMessage(popup_hwnd, win32con.WM_CLOSE, 0, 0)
                return True
                
    print("[THREAD WATCHER] Monitoring timed out.")
    return False


class PledgePage:

    def __init__(self, app):
        self.app = app
        self.main_hwnd = win32gui.FindWindow(TRADEPLUS_CLASS, "TradePlusX")
        if not self.main_hwnd:
            raise Exception("TradePlusX main window handle not found inside PledgePage!")

    def _get_pledge_win_hwnd(self):
        """Locates the open Margin - Pledge/Unpledge window frame."""
        for attempt in range(10):
            result = []
            def cb(hwnd, _):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if "pledge" in title.lower() or "unpledge" in title.lower():
                        result.append(hwnd)
                except: 
                    pass
                return True
            win32gui.EnumChildWindows(self.main_hwnd, cb, None)
            if result and win32gui.IsWindowVisible(result[0]):
                return result[0]
            time.sleep(0.5)
        raise Exception("Pledge Management window not found!")

    def click_manage_tab(self):
        """Locates and clicks on the 'Manage' view tab header panel element."""
        print("Clicking tab: 'Manage' (index 1)")
        all_children = get_all_children(self.main_hwnd)
        
        tab_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if "tabcontrol" in cls.lower() and vis:
                tab_rect = (rect[0] + 65, rect[1] + 10, rect[0] + 110, rect[1] + 25)
                break
                
        if not tab_rect:
            raise Exception("Could not find SysTabControl32 navigation panel frame!")
            
        click_center(tab_rect)
        time.sleep(1.2)
        print("  Tab 'Manage' activated.")

    def set_manage_action(self, action_value):
        """Dynamically locates the action dropdown inside the active Manage tab panel using Win32 API messages."""
        normalized_action = action_value.strip().lower()
        print(f"Setting action dropdown selection to: '{action_value}'")
        
        all_children = get_all_children(self.main_hwnd)
        target_hwnd = None
        action_combo_rect = None
        
        for hwnd, cls, title, rect, vis in all_children:
            if cls == COMBO_CLASS and vis:
                if (350 <= rect[0] <= 370) and (205 <= rect[1] <= 235):
                    target_hwnd = hwnd
                    action_combo_rect = rect
                    print(f"  ✓ Found target Action ComboBox via precise match: handle={hwnd}, rect={rect}")
                    break

        if not target_hwnd:
            print("  Precise combobox match missed. Executing fallback bounding query...")
            for hwnd, cls, title, rect, vis in all_children:
                if "combobox" in cls.lower() and vis and (350 <= rect[0] <= 370):
                    target_hwnd = hwnd
                    action_combo_rect = rect
                    break

        if not target_hwnd or not action_combo_rect:
            raise Exception("Failed to locate the Action selection ComboBox inside the active Manage tab wrapper panel!")

        click_center(action_combo_rect)
        time.sleep(0.3)

        CB_FINDSTRINGEXACT = 0x0158
        CB_SETCURSEL       = 0x014E
        CBN_SELCHANGE      = 1
        WM_COMMAND         = 0x0111

        search_term = "Pledge"
        if normalized_action in ["un-pledge", "un pledge", "unpledge"]:
            search_term = "Un Pledge"
        elif normalized_action in ["un re-pledge", "un re pledge", "un repledge"]:
            search_term = "Un Re-Pledge"

        print(f"  [WIN32 CB] Searching internal memory structure for string layout exact match: '{search_term}'")
        
        matched_idx = win32api.SendMessage(target_hwnd, CB_FINDSTRINGEXACT, -1, search_term)
        
        if matched_idx == -1:
            if "un re" in search_term.lower():
                matched_idx = 2
            elif "un" in search_term.lower():
                matched_idx = 1
            else:
                matched_idx = 0
            print(f"    ⚠ Memory layout query missed. Deploying structural target fallback index: {matched_idx}")

        win32api.SendMessage(target_hwnd, CB_SETCURSEL, matched_idx, 0)
        time.sleep(0.2)

        parent_form_hwnd = win32gui.GetParent(target_hwnd)
        control_id = win32gui.GetDlgCtrlID(target_hwnd)
        notification_message = (CBN_SELCHANGE << 16) | (control_id & 0xFFFF)
        win32api.SendMessage(parent_form_hwnd, WM_COMMAND, notification_message, target_hwnd)
        
        send_keys("{ENTER}")
        time.sleep(0.5)
        print(f"  Dropdown action successfully configured to selection index {matched_idx} ✓")

    def set_manage_date(self, pledge_win_hwnd, date_value):
        """Targets and modifies cross-process date constraints safely using virtual memory and windows messages."""
        print(f"Setting Control Center style date to: '{date_value}'")
        time.sleep(0.3)
        
        all_children = get_all_children(pledge_win_hwnd)
        date_hwnd = None
        date_rect = None

        for hwnd, cls, title, rect, vis in all_children:
            if cls == DATETIME_CLASS and vis:
                if 550 < rect[0] < 650:
                    date_hwnd = hwnd
                    date_rect = rect
                    break

        if not date_hwnd:
            print("  WARNING: Manage panel date picker not found by coordinate — scanning entire frame...")
            for hwnd, cls, title, rect, vis in get_all_children(self.main_hwnd):
                if cls == DATETIME_CLASS and vis and (550 < rect[0] < 650):
                    date_hwnd = hwnd
                    date_rect = rect
                    break

        if not date_hwnd:
            raise Exception("Manage view core Date picker selection target could not be isolated!")

        parts = date_value.split("/")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])

        import ctypes
        import ctypes.wintypes

        PROCESS_ALL_ACCESS = 0x1F0FFF
        MEM_COMMIT_RESERVE = 0x3000
        PAGE_READWRITE     = 0x04
        DTM_SETSYSTEMTIME  = 0x1002

        st_bytes = ctypes.create_string_buffer(16)
        ctypes.memmove(st_bytes,
            ctypes.c_uint16(year).value.to_bytes(2, 'little') +
            ctypes.c_uint16(month).value.to_bytes(2, 'little') +
            ctypes.c_uint16(0).value.to_bytes(2, 'little') +     
            ctypes.c_uint16(day).value.to_bytes(2, 'little') +
            ctypes.c_uint16(0).value.to_bytes(2, 'little') +     
            ctypes.c_uint16(0).value.to_bytes(2, 'little') +     
            ctypes.c_uint16(0).value.to_bytes(2, 'little') +     
            ctypes.c_uint16(0).value.to_bytes(2, 'little'),      
            16)

        pid = ctypes.wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(date_hwnd, ctypes.byref(pid))
        hProc = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)

        try:
            remote_mem = ctypes.windll.kernel32.VirtualAllocEx(hProc, None, 16, MEM_COMMIT_RESERVE, PAGE_READWRITE)
            try:
                ctypes.windll.kernel32.WriteProcessMemory(hProc, remote_mem, st_bytes, 16, None)
                click_center(date_rect)
                time.sleep(0.1)
                
                ctypes.windll.user32.SendMessageW(date_hwnd, DTM_SETSYSTEMTIME, 0, remote_mem)
                time.sleep(0.2)
                
                send_keys("{RIGHT}{UP}{DOWN}{ENTER}")
                time.sleep(0.3)
                print(f"  ✓ Date value set to '{date_value}' smoothly via memory write pipeline configuration.")
            finally:
                ctypes.windll.kernel32.VirtualFreeEx(hProc, remote_mem, 0, 0x8000)
        finally:
            ctypes.windll.kernel32.CloseHandle(hProc)

    def set_checkbox_state(self, pledge_win_hwnd, checkbox_title, target_state):
        """Locates specific checkbox labels and toggles state configuration parameters."""
        print(f"  Processing checkbox: '{checkbox_title}' -> Target: {target_state}")
        all_children = get_all_children(pledge_win_hwnd)

        target_hwnd = None
        target_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip().lower() == checkbox_title.lower():
                target_hwnd = hwnd
                target_rect = rect
                break

        if not target_hwnd:
            for hwnd, cls, title, rect, vis in get_all_children(self.main_hwnd):
                if cls == BUTTON_CLASS and vis and title.strip().lower() == checkbox_title.lower():
                    target_hwnd = hwnd
                    target_rect = rect
                    break

        if not target_hwnd:
            raise Exception(f"Target checkbox control labeled '{checkbox_title}' not found!")

        current_state = is_checked(target_hwnd)
        if current_state != target_state:
            click_center(target_rect)
            time.sleep(0.3)
            print(f"    Checkbox '{checkbox_title}': CHANGED TO {target_state}")
        else:
            print(f"    Checkbox '{checkbox_title}': ALREADY IN TARGET STATE ({current_state})")

    def click_pledge_fetch_button(self, pledge_win_hwnd):
        """Clicks the Fetch data processing confirmation button."""
        print("Clicking the 'Fetch' button...")
        all_children = get_all_children(pledge_win_hwnd)

        btn_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Fetch":
                if rect[0] > 900 and rect[1] > 350:
                    btn_rect = rect
                    break

        if not btn_rect:
            for hwnd, cls, title, rect, vis in get_all_children(self.main_hwnd):
                if cls == BUTTON_CLASS and vis and title.strip() == "Fetch":
                    if rect[0] > 900 and rect[1] > 350:
                        btn_rect = rect
                        break

        if not btn_rect:
            raise Exception("Manage Workspace data query Fetch button layout not located!")

        click_center(btn_rect)
        print("  Fetch button clicked successfully ✓")

    def click_pledge_save_button(self, pledge_win_hwnd):
        """Dynamically targets and triggers the grid execution 'Save' button control element."""
        print("Clicking the 'Save' button...")
        all_children = get_all_children(pledge_win_hwnd)
        
        btn_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Save":
                btn_rect = rect
                break
                
        if not btn_rect:
            for hwnd, cls, title, rect, vis in get_all_children(self.main_hwnd):
                if cls == BUTTON_CLASS and vis and title.strip() == "Save":
                    btn_rect = rect
                    break
                    
        if not btn_rect:
            raise Exception("Core execution grid layout 'Save' process button not found!")
            
        click_center(btn_rect)
        print("  Save button clicked successfully. Launching confirmation handlers...")

    def close_slip_printing_tab(self):
        """Locates and targets the 'Slip printing' preview window frame and closes it cleanly via Win32."""
        print("Searching for newly generated 'Slip printing' report window context...")
        time.sleep(1.0)
        
        report_hwnd = None
        def find_report_cb(hwnd, _):
            nonlocal report_hwnd
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "slip" in title.lower() or "printing" in title.lower():
                        report_hwnd = hwnd
            except:
                pass
            return True
            
        win32gui.EnumWindows(find_report_cb, None)
        
        if report_hwnd:
            print(f"  [REPORT TAB] Found open report viewer handle={report_hwnd}. Sending native close command...")
            win32gui.PostMessage(report_hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            print("  [REPORT TAB] Slip printing frame detached successfully ✓")
        else:
            print("  ⚠ Notice: 'Slip printing' window frame handle was not caught by systemic window sweeps.")

    def close_window(self):
        """Closes the Margin - Pledge/Unpledge window pane natively via WM_CLOSE."""
        print("Closing Pledge Management window...")
        try:
            hwnd = self._get_pledge_win_hwnd()
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            print("  Pledge Management window closed successfully ✓")
        except Exception as e:
            print(f"  ⚠ Failed to close Pledge window: {e}")

    def process(self, tab_name, manage_action=None, manage_date=None, 
                items_sold_by_client=None, with_epn_blk=None, click_fetch=False):
        """Main orchestrated business automation pipeline execution path."""
        pledge_win_hwnd = self._get_pledge_win_hwnd()

        if tab_name.strip().lower() == "manage":
            self.click_manage_tab()
            
            if manage_action is not None:
                self.set_manage_action(manage_action)
                
            if manage_date is not None:
                self.set_manage_date(pledge_win_hwnd, manage_date)
                
            if with_epn_blk is not None:
                self.set_checkbox_state(pledge_win_hwnd, "With EPN-BLK", with_epn_blk)
                
            if items_sold_by_client is not None:
                self.set_checkbox_state(pledge_win_hwnd, "Items Sold By Client", items_sold_by_client)
                
            if click_fetch:
                # STEP 1: Spawn thread killer to handle baseline data warnings
                killer_thread = threading.Thread(target=async_popup_killer, args=(self.main_hwnd,), daemon=True)
                killer_thread.start()
                
                # STEP 2: Trigger data fetch query sequence
                self.click_pledge_fetch_button(pledge_win_hwnd)
                time.sleep(10.0)
                
                # Enforce a strict 3-second delay after fetching data before moving to save
                print("  [WAIT CONTROL] Fetch cycle finalized. Waiting exactly 3 seconds before executing Save...")
                time.sleep(10.0)
                
                # STEP 3: Trigger the Save pipeline
                save_killer = threading.Thread(target=async_popup_killer, args=(self.main_hwnd,), daemon=True)
                save_killer.start()
                
                # Trigger the physical Save button click event node
                self.click_pledge_save_button(pledge_win_hwnd)
                
                # Allow time for report rendering processing to serialize
                time.sleep(3.5)
                
                # STEP 4: Close the newly spawned text preview document context frame
                self.close_slip_printing_tab()
                time.sleep(1.0)

        # FIXED CALIBRATION: Closes the main module tab cleanly before completing execution block tasks
        print("Finishing Pledge Management workflow routine segment layout...")
        self.close_window()

        print("PledgePage.process() completed successfully.")