import time
import win32gui
import win32con
import win32api
import win32clipboard
import re
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
    time.sleep(0.5)  # Paced stabilization buffer following cursor clicks


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


def _strip_date_from_filename(filename):
    return re.sub(r'_\d{8}_', '_', filename)


def _filename_matches(config_fn, grid_fn):
    config_lower = config_fn.lower().strip()
    grid_lower   = grid_fn.lower().strip()

    if config_lower in grid_lower or grid_lower in config_lower:
        return True

    config_stripped = _strip_date_from_filename(config_lower)
    grid_stripped   = _strip_date_from_filename(grid_lower)

    if config_stripped in grid_stripped or grid_stripped in config_stripped:
        return True

    date_re = re.compile(r'^\d{8}$')

    def get_non_date_parts(fn):
        stem = fn.rsplit('.', 1)[0]
        parts = stem.split('_')
        return [p for p in parts if not date_re.match(p)]

    config_parts = get_non_date_parts(config_lower)
    grid_parts   = get_non_date_parts(grid_lower)

    if config_parts and grid_parts:
        return config_parts == grid_parts

    return False


def _normalize_to_dd_mm_yyyy(date_str):
    """
    Converts any incoming date string from JSON (supporting YYYY/MM/DD or YYYY-MM-DD)
    into the standard DD/MM/YYYY format required by TradePlus applications.
    """
    if not date_str:
        return date_str
    
    date_clean = date_str.strip().replace("-", "/")
    parts = date_clean.split("/")
    
    # If the string starts with a 4-digit year (YYYY/MM/DD), re-order it to DD/MM/YYYY
    if len(parts) == 3 and len(parts[0]) == 4:
        year, month, day = parts[0], parts[1], parts[2]
        return f"{day}/{month}/{year}"
        
    return date_str


class ControlCenterPage:

    def __init__(self, app):
        self.app = app
        self.main_hwnd = win32gui.FindWindow(TRADEPLUS_CLASS, "TradePlusX")
        if not self.main_hwnd:
            raise Exception("TradePlusX main window not found!")

    def _get_control_center_hwnd(self):
        max_attempts = 600
        print("Waiting for Control Center window to initialize and render (Timeout: 10 min)...")

        for attempt in range(max_attempts):
            result = []
            def cb(hwnd, _):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if "control" in title.lower() and "center" in title.lower():
                        result.append((hwnd, title))
                except:
                    pass
                return True
            win32gui.EnumChildWindows(self.main_hwnd, cb, None)

            for hwnd, title in result:
                if win32gui.IsWindowVisible(hwnd):
                    print(f"  ✓ Control Center window located on attempt {attempt+1}: handle={hwnd}")
                    return hwnd
            time.sleep(0.2)  # Slightly longer sweep sleep context

        raise Exception("Control Center window failed to load within 10-minute timeout!")

    def handle_special_settlement_popup(self, cc_hwnd, date_value):
        time.sleep(0.5)  
        popup_hwnd = None
        for wait_step in range(6):
            time.sleep(0.1)
            def find_settlement_box(hwnd, _):
                nonlocal popup_hwnd
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd).lower()
                        if "settlement" in title or "create" in title:
                            if hwnd != self.main_hwnd:
                                popup_hwnd = hwnd
                except: pass
                return True
            win32gui.EnumWindows(find_settlement_box, None)
            if popup_hwnd:
                break

        if popup_hwnd:
            print("  [SETTLEMENT ALERT] 'Create Settlement' dialog discovered. Dismissing with ENTER...")
            win32gui.SetForegroundWindow(popup_hwnd)
            time.sleep(0.3)
            send_keys("{ENTER}")
            time.sleep(0.5)
            try:
                win32gui.SetForegroundWindow(self.main_hwnd)
                time.sleep(0.3)
            except:
                pass
            return True
        return False

    def dismiss_center_msgbox(self, cc_hwnd, date_value):
        # Normalize date context explicitly
        date_value = _normalize_to_dd_mm_yyyy(date_value)
        
        if self.handle_special_settlement_popup(cc_hwnd, date_value):
            return "RESTART"
            
        time.sleep(0.4)  
        popup_hwnd = None

        def find_box(hwnd, _):
            nonlocal popup_hwnd
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    cls   = win32gui.GetClassName(hwnd)
                    if ("are you sure" in title or "information" in title or "#32770" in cls or "windowsforms" in cls.lower()):
                        if hwnd != self.main_hwnd:
                            popup_hwnd = hwnd
            except:
                pass
            return True

        win32gui.EnumWindows(find_box, None)

        if popup_hwnd:
            print("  [ALERT INTERCEPT] Modal target dialog identified. Extracting text strings...")
            try:
                win32gui.SetForegroundWindow(popup_hwnd)
                time.sleep(0.3)
            except:
                pass

            dialog_children = get_all_children(popup_hwnd)
            dialog_text_combined = ""
            
            for hwnd, cls, title, rect, vis in dialog_children:
                if title.strip():
                    dialog_text_combined += " " + title.lower().strip()

            print(f"  [ALERT INTERCEPT] Inspected Text Content: {dialog_text_combined!r}")

            if "mis match found" in dialog_text_combined:
                print("\n[CRITICAL STOP] Mismatch flag triggered inside dialog text panel.")
                raise Exception("Pipeline stopped: 'mis match found' string discovered in popup message box.")
            
            elif "mis match not found" in dialog_text_combined:
                print("  ✓ Verification matched: 'mis match not found' confirmed. Proceeding with clearing the box...")
            
            elif "mis match" in dialog_text_combined:
                print("\n[CRITICAL STOP] Undefined status rule trace context matched.")
                raise Exception("Pipeline stopped: Dialog contains an ambiguous mismatch notification state.")

            yes_rect = None
            for hwnd, cls, title, rect, vis in dialog_children:
                title_clean = title.strip().lower()
                if vis and ("yes" in title_clean or "ok" in title_clean or "button" in cls.lower()):
                    yes_rect = rect
                    break

            if yes_rect:
                print(f"  ✓ Clicking validation button node element directly at: {yes_rect}")
                click_center(yes_rect)
            else:
                print("  WARNING: Dynamic click vector missed. Delivering direct keyboard ENTER stroke sequence...")
                send_keys("{ENTER}")
            time.sleep(0.5)
        return "SUCCESS"

    def get_clipboard_text(self):
        try:
            win32clipboard.OpenClipboard()
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return str(data).strip()
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return ""

    def _clear_clipboard(self):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except:
            pass
        time.sleep(0.1)

    def _close_report_popup(self):
        BM_CLICK = 0x00F5
        REPORT_TITLE_KEYWORDS = [
            "file import report",
            "obligation", "comparison", "money sheet",
            "reconciliation", "mismatch", "accumulation", "bill reconcil"
        ]

        report_hwnd = None
        def _find_report(hwnd, _):
            nonlocal report_hwnd
            try:
                if hwnd == self.main_hwnd:
                    return True
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if any(kw in title for kw in REPORT_TITLE_KEYWORDS):
                        report_hwnd = hwnd
            except:
                pass
            return True

        win32gui.EnumWindows(_find_report, None)

        if not report_hwnd:
            return  

        print(f"  [REPORT POPUP] Found: '{win32gui.GetWindowText(report_hwnd)}' handle={report_hwnd}")
        time.sleep(0.5)

        close_btn_hwnd = None
        close_btn_rect = None

        def _find_close_btn(hwnd, _):
            nonlocal close_btn_hwnd, close_btn_rect
            try:
                raw_title = win32gui.GetWindowText(hwnd).strip()
                clean = raw_title.replace("&", "").lower()
                cls   = win32gui.GetClassName(hwnd)
                if clean == "close" and "button" in cls.lower():
                    rect = win32gui.GetWindowRect(hwnd)
                    print(f"  [REPORT POPUP]   Close btn: handle={hwnd} raw_title={raw_title!r} rect={rect}")
                    if close_btn_rect is None or rect[0] > close_btn_rect[0]:
                        close_btn_hwnd = hwnd
                        close_btn_rect = rect
            except:
                pass
            return True

        try:
            win32gui.EnumChildWindows(report_hwnd, _find_close_btn, None)
        except:
            pass

        try:
            win32gui.SetForegroundWindow(report_hwnd)
            time.sleep(0.3)
        except:
            pass

        if close_btn_hwnd:
            print(f"  [REPORT POPUP] Sending BM_CLICK to &Close handle={close_btn_hwnd}")
            try:
                win32api.SendMessage(close_btn_hwnd, BM_CLICK, 0, 0)
                time.sleep(0.5)
            except Exception as e:
                print(f"  [REPORT POPUP] BM_CLICK error: {e}")

            if win32gui.IsWindow(report_hwnd) and win32gui.IsWindowVisible(report_hwnd):
                cx = (close_btn_rect[0] + close_btn_rect[2]) // 2
                cy = (close_btn_rect[1] + close_btn_rect[3]) // 2
                print(f"  [REPORT POPUP] Still open — mouse clicking &Close at ({cx}, {cy})")
                mouse.click(button='left', coords=(cx, cy))
                time.sleep(0.5)
        else:
            print(f"  [REPORT POPUP] &Close button not found — sending WM_CLOSE to handle={report_hwnd}")
            try:
                win32api.PostMessage(report_hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(0.5)
            except Exception as e:
                print(f"  [REPORT POPUP] WM_CLOSE error: {e}")

        cc_hwnd_refocus = None
        def _find_cc(hwnd, _):
            nonlocal cc_hwnd_refocus
            try:
                if win32gui.IsWindowVisible(hwnd) and "control center" in win32gui.GetWindowText(hwnd).lower():
                    cc_hwnd_refocus = hwnd
            except:
                pass
            return True

        try:
            win32gui.EnumChildWindows(self.main_hwnd, _find_cc, None)
        except:
            pass

        if cc_hwnd_refocus:
            try:
                win32gui.ShowWindow(cc_hwnd_refocus, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(cc_hwnd_refocus)
                time.sleep(0.4)
                print("  [REPORT POPUP] Control Center re-focused. Continuing workflow ✓")
            except:
                pass

    def scan_and_process_data_grid(self, cc_hwnd, files_workflow_config, date_value, current_segment=None):
        if not files_workflow_config:
            print("  No file workflow config loaded. Skipping grid processing.")
            return "SUCCESS"

        print("\nStarting File Imports grid scan...")
        time.sleep(1.0)

        GRID_TOP   = 262
        HEADER_H   = 25
        ROW_H      = 20
        FILENAME_X = 340 + 250   

        def click_filename_cell(row_idx):
            y = GRID_TOP + HEADER_H + (row_idx * ROW_H) + (ROW_H // 2)
            print(f"  [GRID] Clicking filename cell row {row_idx} at ({FILENAME_X}, {y})")
            mouse.click(button='left', coords=(FILENAME_X, y))
            time.sleep(0.5)

        MAX_ROWS = 12
        previous_key = None
        consecutive_skipped_duplicates = 0

        for row_idx in range(MAX_ROWS):
            click_filename_cell(row_idx)

            self._clear_clipboard()
            send_keys("^c")
            time.sleep(0.4)

            current_row_filename = self.get_clipboard_text()
            
            if not current_row_filename:
                print(f"  Row {row_idx}: [BLANK / END OF GRID]. Done Extraction Loop.")
                break

            send_keys("{LEFT}")
            time.sleep(0.2)
            
            self._clear_clipboard()
            send_keys("^c")
            time.sleep(0.4)
            row_description = self.get_clipboard_text().strip()

            send_keys("{RIGHT}")
            time.sleep(0.2)

            seg_prefix = current_segment if current_segment else "BSE"
            combined_table_key = f"{seg_prefix}_Cash_{row_description}"
            print(f"  Row {row_idx}: '{current_row_filename}' parsed as mapping key: '{combined_table_key}'")

            if combined_table_key == previous_key:
                consecutive_skipped_duplicates += 1
                if consecutive_skipped_duplicates >= 2:
                    print(f"  [GRID BREAK] Detected duplicate dynamic values ('{combined_table_key}'). Breaking loop.")
                    break
            else:
                consecutive_skipped_duplicates = 0

            previous_key = combined_table_key

            match_found = False
            target_enabled = False
            for config_key, enabled_status in files_workflow_config.items():
                if config_key.strip().lower() == combined_table_key.lower():
                    match_found = True
                    target_enabled = enabled_status
                    break

            if not match_found:
                print(f"    -> '{combined_table_key}' Not in JSON config. Skipping.")
                time.sleep(0.3)
                continue

            if not target_enabled:
                print(f"    -> '{combined_table_key}' is FALSE in JSON. Skipping.")
                time.sleep(0.3)
                continue

            print(f"    -> '{combined_table_key}' is TRUE — checking import status...")
            time.sleep(0.3)

            send_keys("{RIGHT}")
            time.sleep(0.3)
            send_keys("{DOWN}")
            time.sleep(0.3)
            send_keys("{HOME}")
            time.sleep(0.4)

            is_already_success = False
            all_app_children = get_all_children(self.main_hwnd)
            for hwnd, cls, title, rect, vis in all_app_children:
                if vis and ("success" in title.lower() or "imported successfully" in title.lower()):
                    is_already_success = True
                    break

            if is_already_success:
                print(f"    -> Already imported. Skipping.")
                send_keys("{ESCAPE}")
                time.sleep(0.3)
                continue

            print(f"    -> [PENDING] Triggering import for row {row_idx}...")
            send_keys("{DOWN}")
            time.sleep(0.3)
            send_keys("{ENTER}")

            print(f"    -> Waiting for import pipeline...")
            time.sleep(7.5)

            msg_status = self.dismiss_center_msgbox(cc_hwnd, date_value)
            if msg_status == "RESTART":
                return "RESTART"

            self._close_report_popup()
            time.sleep(0.8)

            try:
                win32gui.SetForegroundWindow(cc_hwnd)
                time.sleep(0.4)
            except:
                pass

            print(f"    -> Import complete for row {row_idx}. Continuing to next file...")

        return "SUCCESS"
    
    def process_processes_grid_selection(self, cc_hwnd, target_settlement):
        if not target_settlement:
            print("  [PROCESSES GRID] No target settlement specified. Skipping.")
            return

        target_clean = target_settlement.strip()[:2].lower()  
        print(f"\n[PROCESSES GRID] Scanning for settlement prefix: '{target_clean}' (from '{target_settlement}')...")
        time.sleep(3.5)

        GRID_TOP       = 199   
        HEADER_H       = 22    
        ROW_H          = 28    
        CHECKBOX_X     = 370   
        SETTLEMENT_X   = 447   

        def row_centre_y(row_idx):
            return GRID_TOP + HEADER_H + (row_idx * ROW_H) + (ROW_H // 2)

        try:
            win32gui.ShowWindow(self.main_hwnd, win32con.SW_SHOWMAXIMIZED)
            win32gui.SetForegroundWindow(self.main_hwnd)
            time.sleep(0.8)
        except Exception as fe:
            print(f"  [PROCESSES GRID] Focus: {fe}")

        anchor_y = row_centre_y(0)
        print(f"  [PROCESSES GRID] Anchoring focus at Settlement ({SETTLEMENT_X}, anchor_y)")
        mouse.click(button='left', coords=(SETTLEMENT_X, anchor_y))
        time.sleep(1.5)

        MAX_ROWS     = 12
        matched_rows = []

        for row_idx in range(MAX_ROWS):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.CloseClipboard()
            except:
                pass
            time.sleep(0.1)

            send_keys("^c")
            time.sleep(0.5)

            cell_text = self.get_clipboard_text().lower().strip()
            print(f"  [PROCESSES GRID] Row {row_idx}: '{cell_text}'")

            if not cell_text:
                print("  [PROCESSES GRID] Empty cell — end of data.")
                break

            if target_clean in cell_text:
                print(f"  ✓ Match at row {row_idx}")
                matched_rows.append(row_idx)

            send_keys("{DOWN}")
            time.sleep(0.3)

        if not matched_rows:
            print(f"  [PROCESSES GRID] CRITICAL: '{target_clean}' not found in {MAX_ROWS} rows.")
            return

        print(f"  [PROCESSES GRID] Matched rows: {matched_rows}")

        for row_idx in matched_rows:
            chk_y = row_centre_y(row_idx)
            print(f"  [PROCESSES GRID] Clicking checkbox row {row_idx}: ({CHECKBOX_X}, chk_y)")

            mouse.click(button='left', coords=(SETTLEMENT_X, chk_y))
            time.sleep(0.4)

            mouse.click(button='left', coords=(CHECKBOX_X, chk_y))
            time.sleep(0.6)

            print(f"  [PROCESSES GRID] ✓ Checkbox clicked for row {row_idx}")

        print(f"  [PROCESSES GRID] All {len(matched_rows)} checkbox(es) clicked ✓")
        time.sleep(0.5)

        print("  [PROCESSES GRID] Locating Proceed button...")
        all_children = get_all_children(cc_hwnd)
        proceed_rect = None

        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Proceed" and rect[0] > 1000:
                proceed_rect = rect
                break

        if proceed_rect:
            print(f"  [PROCESSES GRID] Clicking Proceed at {proceed_rect}")
            click_center(proceed_rect)
            
            print("  [MONITOR] Proceed triggered. Locating process log panel frame...")
            
            log_panel_rect = None
            for hwnd, cls, title, rect, vis in all_children:
                if cls == TRADEPLUS_CLASS and vis and (840 <= rect[0] <= 850) and (180 <= rect[1] <= 190):
                    log_panel_rect = rect
                    break
            
            if not log_panel_rect:
                log_panel_rect = (846, 183, 1174, 654)

            console_x = (log_panel_rect[0] + log_panel_rect[2]) // 2
            console_y = (log_panel_rect[1] + log_panel_rect[3]) // 2
            
            print("  [MONITOR] Entering dynamic evaluation loop. Waiting for process completion tokens...")
            check_interval = 5.0  
            
            while True:
                try:
                    mouse.click(button='left', coords=(console_x, console_y))
                    time.sleep(0.3)
                    
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.CloseClipboard()
                    time.sleep(0.1)
                    
                    send_keys("^a")
                    time.sleep(0.2)
                    send_keys("^c")
                    time.sleep(0.4)
                    
                    console_content = self.get_clipboard_text().lower()
                    
                    if "process completed" in console_content:
                        print("  [MONITOR] ✓ 'Process Completed' string detected in console layout. Progressing pipeline updates.")
                        break
                except Exception as monitor_err:
                    print(f"  [MONITOR WARNING] Extraction polling skip trace context: {monitor_err}")
                
                time.sleep(check_interval)
            
            self.dismiss_center_msgbox(cc_hwnd, date_value=None)
            self._close_report_popup()
        else:
            print("  ⚠ [PROCESSES GRID] ERROR: Proceed button not found!")

    def set_control_center_date(self, cc_hwnd, date_value):
        # Normalize incoming config input to standard Application format (DD/MM/YYYY)
        date_value = _normalize_to_dd_mm_yyyy(date_value)
        print(f"Setting Control Center date to: '{date_value}'")
        time.sleep(0.5)
        
        all_children = get_all_children(cc_hwnd)
        date_hwnd = None
        date_rect = None
        
        for hwnd, cls, title, rect, vis in all_children:
            if cls == DATETIME_CLASS and vis:
                if 220 <= rect[0] <= 240 and 115 <= rect[1] <= 130:
                    date_hwnd = hwnd
                    date_rect = rect
                    break
                    
        if not date_hwnd:
            for hwnd, cls, title, rect, vis in all_children:
                if cls == DATETIME_CLASS and vis and rect[0] < 300:
                    date_hwnd = hwnd
                    date_rect = rect
                    break

        if not date_hwnd:
            raise Exception("Primary Date Picker workspace element could not be isolated!")

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
            ctypes.c_uint16(year).value.to_bytes(2,'little') +
            ctypes.c_uint16(month).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(day).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little'),
            16)
            
        pid = ctypes.wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(date_hwnd, ctypes.byref(pid))
        hProc = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        try:
            remote_mem = ctypes.windll.kernel32.VirtualAllocEx(hProc, None, 16, MEM_COMMIT_RESERVE, PAGE_READWRITE)
            try:
                ctypes.windll.kernel32.WriteProcessMemory(hProc, remote_mem, st_bytes, 16, None)
                click_center(date_rect)
                time.sleep(0.3)
                
                ctypes.windll.user32.SendMessageW(date_hwnd, DTM_SETSYSTEMTIME, 0, remote_mem)
                time.sleep(0.5)
                
                send_keys("{RIGHT}{UP}{DOWN}{ENTER}")
                time.sleep(0.5)
            finally:
                ctypes.windll.kernel32.VirtualAllocEx(hProc, remote_mem, 0, 0x8000)
        finally:
            ctypes.windll.kernel32.CloseHandle(hProc)

    def click_proceed_button(self, cc_hwnd):
        print("Clicking primary 'Proceed' button...")
        all_children = get_all_children(cc_hwnd)
        btn_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Proceed" and rect[0] < 350:
                btn_rect = rect
                break
        if not btn_rect:
            raise Exception("Primary Proceed button not found!")
        click_center(btn_rect)
        time.sleep(1.0)

    def click_processes_button(self, cc_hwnd):
        print("Clicking sidebar 'Processes' navigation button...")
        all_children = get_all_children(cc_hwnd)
        btn_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Processes" and rect[0] < 350:
                btn_rect = rect
                break
        if not btn_rect:
            raise Exception("Sidebar Processes menu option missing!")
        click_center(btn_rect)
        time.sleep(1.0)

    def set_product_selection(self, cc_hwnd, product_name):
        normalized_name = product_name.strip().capitalize()
        print(f"Setting Product Selection Dropdown to: '{normalized_name}'")
        all_children = get_all_children(parent_hwnd=cc_hwnd)
        product_combo_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == COMBO_CLASS and vis and (380 < rect[0] < 420) and (140 < rect[1] < 185):
                product_combo_rect = rect
                break
        if not product_combo_rect:
            raise Exception("Product selection dropdown element not found!")
        click_center(product_combo_rect)
        time.sleep(0.4)
        send_keys("{HOME}")
        time.sleep(0.3)
        if normalized_name == "Commodity":
            send_keys("{DOWN}")
            time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.8)

    def set_process_for_date(self, cc_hwnd, for_date_value):
        # Normalize dynamic workspace input execution strings 
        for_date_value = _normalize_to_dd_mm_yyyy(for_date_value)
        print(f"Setting Processes workspace 'For :' date to: '{for_date_value}'")
        all_children = get_all_children(cc_hwnd)
        date_ctrl = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == DATETIME_CLASS and vis and (650 < rect[0] < 700):
                date_ctrl = (hwnd, rect)
                break
        if not date_ctrl:
            raise Exception("Workspace 'For :' date picker element not found!")
        date_hwnd, date_rect = date_ctrl
        parts = for_date_value.split("/")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        import ctypes
        import ctypes.wintypes
        PROCESS_ALL_ACCESS = 0x1F0FFF
        MEM_COMMIT_RESERVE = 0x3000
        PAGE_READWRITE     = 0x04
        DTM_SETSYSTEMTIME  = 0x1002
        st_bytes = ctypes.create_string_buffer(16)
        ctypes.memmove(st_bytes,
            ctypes.c_uint16(year).value.to_bytes(2,'little') +
            ctypes.c_uint16(month).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(day).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little') +
            ctypes.c_uint16(0).value.to_bytes(2,'little'),
            16)
        pid = ctypes.wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(date_hwnd, ctypes.byref(pid))
        hProc = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        try:
            remote_mem = ctypes.windll.kernel32.VirtualAllocEx(hProc, None, 16, MEM_COMMIT_RESERVE, PAGE_READWRITE)
            try:
                ctypes.windll.kernel32.WriteProcessMemory(hProc, remote_mem, st_bytes, 16, None)
                click_center(date_rect)
                time.sleep(0.3)
                ctypes.windll.user32.SendMessageW(date_hwnd, DTM_SETSYSTEMTIME, 0, remote_mem)
                time.sleep(0.5)
            finally:
                remote_mem_freed = ctypes.windll.kernel32.VirtualFreeEx(hProc, remote_mem, 0, 0x8000)
        finally:
            ctypes.windll.kernel32.CloseHandle(hProc)

    def click_process_fetch_button(self, cc_hwnd):
        print("Clicking workspace 'Fetch' button...")
        all_children = get_all_children(cc_hwnd)
        fetch_btn_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Fetch" and rect[0] > 350:
                fetch_btn_rect = rect
                break
        if not fetch_btn_rect:
            raise Exception("Workspace Fetch button element not found!")
        click_center(fetch_btn_rect)
        time.sleep(1.0)

    def click_others_button(self, cc_hwnd):
        print("Clicking 'Others' button...")
        all_children = get_all_children(cc_hwnd)
        others_btn_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Others" and rect[0] < 350:
                others_btn_rect = rect
                break
        if not others_btn_rect:
            raise Exception("Could find 'Others' button inside Control Center layout!")
        click_center(others_btn_rect)
        time.sleep(1.0)

    def set_others_exchange(self, cc_hwnd, exchange_name):
        target = exchange_name.strip().upper()
        if target not in ["BSE", "NSE"]:
            raise ValueError(f"Invalid Exchange selection: '{exchange_name}'. Must be 'BSE' or 'NSE'.")
        print(f"Setting Others Tab Exchange to: '{target}'")
        all_children = get_all_children(cc_hwnd)
        exchange_combo_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == COMBO_CLASS and vis and (410 < rect[0] < 440) and (160 < rect[1] < 185):
                exchange_combo_rect = rect
                break
        if not exchange_combo_rect:
            raise Exception("Exchange dropdown box not found under Others view scope!")
        click_center(exchange_combo_rect)
        time.sleep(0.4)
        send_keys("{HOME}")
        time.sleep(0.3)
        if target == "NSE":
            send_keys("{DOWN}")
            time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.8)

    def set_others_settlement(self, cc_hwnd, settlement_name):
        prefix_target = settlement_name.strip()[:2].upper()
        print(f"Selecting Settlement option using prefix tracking: '{prefix_target}' (from '{settlement_name}')")
        
        all_children = get_all_children(cc_hwnd)
        target_hwnd = None
        settlement_combo_rect = None
        
        for hwnd, cls, title, rect, vis in all_children:
            if cls == COMBO_CLASS and vis and (410 < rect[0] < 440) and (210 < rect[1] < 245):
                target_hwnd = hwnd
                settlement_combo_rect = rect
                break
        if not target_hwnd or not settlement_combo_rect:
            raise Exception("Settlement dropdown box not found under Others view scope!")
            
        click_center(settlement_combo_rect)
        time.sleep(0.5)

        CB_SELECTSTRING = 0x014D
        CBN_SELCHANGE   = 1
        WM_COMMAND      = 0x0111

        matched_idx = win32api.SendMessage(target_hwnd, CB_SELECTSTRING, -1, prefix_target)
        
        if matched_idx != -1:
            print(f"  [WIN32 CB] Prefix match successfully found at selection index: {matched_idx}")
            time.sleep(0.2)
            
            parent_form_hwnd = win32gui.GetParent(target_hwnd)
            control_id = win32gui.GetDlgCtrlID(target_hwnd)
            notification_message = (CBN_SELCHANGE << 16) | (control_id & 0xFFFF)
            win32api.SendMessage(parent_form_hwnd, WM_COMMAND, notification_message, target_hwnd)
            time.sleep(0.3)
            
            send_keys("{ESC}")
        else:
            print(f"  ⚠ Prefix scan missed for '{prefix_target}'. Attempting manual sequence fallback typing...")
            send_keys("^a")
            time.sleep(0.1)
            send_keys("{BACKSPACE}")
            time.sleep(0.1)
            send_keys(settlement_name)
            time.sleep(0.4)
            send_keys("{ENTER}")
            
        time.sleep(0.8)

    def select_exchange_obligation_reconciliation_option(self, cc_hwnd):
        print("Selecting 'Exchange Obligation Reconciliation' option row...")
        all_children = get_all_children(cc_hwnd)
        radio_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Exchange Obligation Reconciliation":
                radio_rect = rect
                break
        if not radio_rect:
            raise Exception("Could not find the 'Exchange Obligation Reconciliation' option control check layout!")
        click_center(radio_rect)
        time.sleep(0.6)

    def select_unprocess_bills_option(self, cc_hwnd):
        print("Selecting 'Un Process Bills' option row...")
        all_children = get_all_children(cc_hwnd)
        radio_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Un Process Bills":
                radio_rect = rect
                break
        if not radio_rect:
            raise Exception("Could not find the 'Un Process Bills' option check layout!")
        click_center(radio_rect)
        time.sleep(0.6)

    def click_others_workspace_proceed(self, cc_hwnd):
        print("Clicking workspace final execution 'Proceed' button...")
        all_children = get_all_children(cc_hwnd)
        proceed_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Proceed" and rect[0] > 1000:
                proceed_rect = rect
                break
        if not proceed_rect:
            raise Exception("Could not find bottom-right workspace Proceed button!")
        click_center(proceed_rect)
        time.sleep(1.0)

        self._dismiss_others_proceed_popup()
        self._close_report_popup()

    def _dismiss_others_proceed_popup(self):
        print("  [OTHERS PROCEED] Checking for post-Proceed dialog box...")
        time.sleep(0.6)  

        popup_hwnd = None
        def _find_dialog(hwnd, _):
            nonlocal popup_hwnd
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if hwnd == self.main_hwnd:
                    return True
                cls   = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd).lower()
                if (cls == "#32770"
                        or "information" in title
                        or "are you sure" in title
                        or "windowsforms" in cls.lower()):
                    popup_hwnd = hwnd
            except:
                pass
            return True

        win32gui.EnumWindows(_find_dialog, None)

        if not popup_hwnd:
            print("  [OTHERS PROCEED] No dialog detected. Continuing ✓")
            return

        print(f"  [OTHERS PROCEED] Dialog found: '{win32gui.GetWindowText(popup_hwnd)}' handle={popup_hwnd}")
        time.sleep(0.4)

        btn_hwnd = None
        btn_rect  = None

        def _find_ok(hwnd, _):
            nonlocal btn_hwnd, btn_rect
            try:
                raw   = win32gui.GetWindowText(hwnd).strip()
                clean = raw.replace("&", "").lower()
                cls   = win32gui.GetClassName(hwnd)
                if clean in ("ok", "yes") and "button" in cls.lower() and win32gui.IsWindowVisible(hwnd):
                    btn_hwnd = hwnd
                    btn_rect  = win32gui.GetWindowRect(hwnd)
            except:
                pass
            return True

        try:
            win32gui.EnumChildWindows(popup_hwnd, _find_ok, None)
        except:
            pass

        try:
            win32gui.SetForegroundWindow(popup_hwnd)
            time.sleep(0.3)
        except:
            pass

        if btn_hwnd:
            print(f"  [OTHERS PROCEED] Clicking OK/Yes button handle={btn_hwnd}")
            try:
                win32api.SendMessage(btn_hwnd, 0x00F5, 0, 0)  
                time.sleep(0.5)
                print("  [OTHERS PROCEED] Dialog dismissed via BM_CLICK ✓")
                return
            except Exception as e:
                print(f"  [OTHERS PROCEED] BM_CLICK failed: {e}")

        print("  [OTHERS PROCEED] Sending {ENTER} to dismiss dialog...")
        send_keys("{ENTER}")
        time.sleep(0.5)
        print("  [OTHERS PROCEED] Dialog dismissed via ENTER ✓")

    def click_file_imports_button(self, cc_hwnd):
        print("Clicking sidebar 'File Imports' navigation button...")
        all_children = get_all_children(cc_hwnd)
        btn_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis and title.strip() == "File Imports" and rect[0] < 350:
                btn_rect = rect
                break
        if not btn_rect:
            raise Exception("Sidebar File Imports menu option missing!")
        click_center(btn_rect)
        
        max_wait = 150
        print("Waiting for File Imports workspace view to fully render and open...")
        for attempt in range(max_wait):
            time.sleep(0.1)
            current_children = get_all_children(cc_hwnd)
            workspace_ready = False
            for hwnd, cls, title, rect, vis in current_children:
                if cls == COMBO_CLASS and vis and (380 < rect[0] < 410) and (140 < rect[1] < 155):
                    workspace_ready = True
                    break
            if workspace_ready:
                print(f"  ✓ File Imports workspace active and verified (attempt {attempt+1})")
                time.sleep(0.5)  
                return
        print("  WARNING: Workspace controls did not show up within threshold, continuing anyway...")

    def set_imports_product(self, cc_hwnd, product_name):
        print(f"Setting Imports Workspace Product to: '{product_name}'")
        all_children = get_all_children(cc_hwnd)
        combo_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == COMBO_CLASS and vis and (380 < rect[0] < 410) and (140 < rect[1] < 155):
                combo_rect = rect
                break
        if not combo_rect:
            raise Exception("File Imports configuration product combobox missing!")
        click_center(combo_rect)
        time.sleep(0.4)
        send_keys("{HOME}")
        time.sleep(0.2)
        if product_name.strip().upper() == "COMMODITY":
            send_keys("{DOWN}")
            time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.5)

    def set_imports_type(self, cc_hwnd, type_name):
        print(f"Setting Imports Workspace Type to: '{type_name}'")
        all_children = get_all_children(cc_hwnd)
        combo_rect = None
        for hwnd, cls, title, rect, vis in all_children:
            if cls == COMBO_CLASS and vis and (380 < rect[0] < 410) and (170 < rect[1] < 185):
                combo_rect = rect
                break
        if not combo_rect:
            raise Exception("File Imports configuration type combobox missing!")
        click_center(combo_rect)
        time.sleep(0.4)
        send_keys("{HOME}")
        time.sleep(0.2)
        if type_name.strip().upper() == "UDIFF":
            send_keys("{DOWN}")
            time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.5)

    def check_matrix_checkbox(self, cc_hwnd, market_segment, state=True):
        segment_key = market_segment.strip().upper()
        print(f"Configuring Matrix Checkbox intersection for [{segment_key}] -> Target State: {state}")

        all_children = get_all_children(cc_hwnd)
        target_hwnd = None
        target_rect = None

        if segment_key == "BSE":
            x_min, x_max, y_min, y_max = 610, 630, 165, 185
        elif segment_key == "NSE":
            x_min, x_max, y_min, y_max = 610, 630, 190, 210
        else:
            raise ValueError(f"Unsupported segment identifier: {market_segment}")

        for hwnd, cls, title, rect, vis in all_children:
            if cls == BUTTON_CLASS and vis:
                if (x_min <= rect[0] <= x_max) and (y_min <= rect[1] <= y_max):
                    target_hwnd = hwnd
                    target_rect = rect
                    break

        if not target_hwnd:
            raise Exception(f"Failed to isolate matrix checkbox for {segment_key}!")

        print(f"  Clicking {segment_key} checkbox to set state={state}...")
        click_center(target_rect)
        time.sleep(0.8)
        print(f"  {segment_key} Checkbox clicked ✓")

    def close_window(self):
        print("Closing Control Center window...")
        try:
            cc_hwnd = self._get_control_center_hwnd()
            win32gui.PostMessage(cc_hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            print("  Control Center window closed successfully ✓")
        except Exception as e:
            print(f"  Note: Control Center window was already closed or not found: {e}")

    def process(self, date=None, click_file_imports=False, imports_product=None, imports_type=None,
                check_bse_cash=False, check_nse_cash=False, bse_files_workflow=None, nse_files_workflow=None,
                click_processes=False, product=None, for_date=None, click_fetch=False,
                click_others=False, exchange=None, settlement=None, exchange_obligation_reconciliation=False, unprocess_bills=False,
                raw_workflow_config=None):
        
        while True:
            cc_hwnd = self._get_control_center_hwnd()

            if date is not None:
                # Internal normalization converts YYYY/MM/DD target string securely inside application layout sets
                self.set_control_center_date(cc_hwnd, date)
                time.sleep(0.2)
                self.click_proceed_button(cc_hwnd)
                time.sleep(0.5)
            break 

        execution_sequence = ["file_imports", "others", "processes"]
        print(f"[DYNAMIC ROUTER] Computed task sequence pipeline order: {execution_sequence}")

        for step in execution_sequence:
            if step == "file_imports" and click_file_imports:
                print("\n--- Executing File Imports Suite ---")
                self.click_file_imports_button(cc_hwnd)
                time.sleep(0.5)

                if imports_product is not None:
                    self.set_imports_product(cc_hwnd, imports_product)
                    time.sleep(0.2)

                if imports_type is not None:
                    self.set_imports_type(cc_hwnd, imports_type)
                    time.sleep(0.2)

                if check_bse_cash:
                    print("  [SEQUENCER PASS 1] Activating BSE matrix grid segment...")
                    self.check_matrix_checkbox(cc_hwnd, market_segment="BSE", state=True)
                    time.sleep(0.5)

                    print("  [TIMER] Waiting 10 seconds for File BSE grid data to load...")
                    time.sleep(10.0)

                    status = self.scan_and_process_data_grid(cc_hwnd, bse_files_workflow, date_value=date, current_segment="BSE")

                    print("  [SEQUENCER PASS 1] Clearing BSE selection state...")
                    self.check_matrix_checkbox(cc_hwnd, market_segment="BSE", state=False)
                    print("  [SEQUENCER PASS 1] Holding thread for interface refresh synchronization...")
                    time.sleep(1.5)

                    if status == "RESTART":
                        return "RESTART"

                if check_nse_cash:
                    print("  [SEQUENCER PASS 2] Activating NSE matrix grid segment...")
                    self.check_matrix_checkbox(cc_hwnd, market_segment="NSE", state=True)
                    time.sleep(0.5)

                    print("  [TIMER] Waiting 10 seconds for NSE File grid data to load...")
                    time.sleep(10.0)

                    status = self.scan_and_process_data_grid(cc_hwnd, nse_files_workflow, date_value=date, current_segment="NSE")

                    print("  [SEQUENCER PASS 2] Clearing NSE selection state...")
                    self.check_matrix_checkbox(cc_hwnd, market_segment="NSE", state=False)
                    print("  [SEQUENCER PASS 2] Holding thread for interface refresh synchronization...")
                    time.sleep(1.5)

                    if status == "RESTART":
                        return "RESTART"

            elif step == "others" and click_others:
                if raw_workflow_config and not raw_workflow_config.get("others", {}).get("enabled", True):
                    continue

                print("\n--- Executing Others Suite ---")
                self.click_others_button(cc_hwnd)
                time.sleep(0.5)

                if exchange is not None:
                    self.set_others_exchange(cc_hwnd, exchange)

                if settlement is not None:
                    self.set_others_settlement(cc_hwnd, settlement)

                if exchange_obligation_reconciliation:
                    self.select_exchange_obligation_reconciliation_option(cc_hwnd)
                    time.sleep(0.2)

                if unprocess_bills:
                    self.select_unprocess_bills_option(cc_hwnd)
                    time.sleep(0.2)

                self.click_others_workspace_proceed(cc_hwnd)

            elif step == "processes" and click_processes:
                if raw_workflow_config and not raw_workflow_config.get("processes", {}).get("enabled", True):
                    continue

                print("\n--- Executing Processes Suite ---")
                self.click_processes_button(cc_hwnd)
                time.sleep(0.5)

                if product is not None:
                    self.set_product_selection(cc_hwnd, product)
                    time.sleep(0.2)

                if for_date is not None:
                    self.set_process_for_date(cc_hwnd, for_date)
                    time.sleep(0.2)

                if click_fetch:
                    self.click_process_fetch_button(cc_hwnd)
                    time.sleep(0.5)
                    
                    target_settlement_name = None
                    if isinstance(raw_workflow_config, dict):
                        target_settlement_name = raw_workflow_config.get("processes", {}).get("target_settlement")
                        
                    if target_settlement_name:
                        self.process_processes_grid_selection(cc_hwnd, target_settlement_name)
                        time.sleep(0.8)

        print("ControlCenterPage dynamic sequencing suite processing completed successfully.")
        return "SUCCESS"