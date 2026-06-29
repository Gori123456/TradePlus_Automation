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
    Converts any incoming date string from JSON (supporting YYYYMMDD, YYYY/MM/DD, 
    spaces, or hyphens) into the standard DD/MM/YYYY format required by TradePlus applications.
    """
    if not date_str:
        return date_str
    
    date_clean = date_str.strip()
    
    # Handle compact YYYYMMDD format (e.g., "20260211")
    if len(date_clean) == 8 and date_clean.isdigit():
        year = date_clean[:4]
        month = date_clean[4:6]
        day = date_clean[6:]
        return f"{day}/{month}/{year}"
        
    # Clean up spaces AND hyphens, converting them to forward slashes
    date_clean = date_clean.replace("-", "/").replace(" ", "/")
    parts = date_clean.split("/")
    
    if len(parts) == 3:
        # Scenario A: If it's YYYY/MM/DD (starts with a 4-digit year)
        if len(parts[0]) == 4:
            year, month, day = parts[0], parts[1], parts[2]
            return f"{day}/{month}/{year}"
        # Scenario B: If it's already DD/MM/YYYY (ends with a 4-digit year)
        elif len(parts[2]) == 4:
            return f"{parts[0]}/{parts[1]}/{parts[2]}"
        
    return date_clean


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

        # Locate grid via AutomationId — no coordinates
        cc_win = self.app.window(handle=cc_hwnd)
        grid = cc_win.child_window(auto_id="dgvFileImp", control_type="Pane")
        grid.wait("visible", timeout=10)
        grid.set_focus()
        time.sleep(0.3)

        grid_rect  = win32gui.GetWindowRect(grid.handle)
        HEADER_H   = 25
        ROW_H      = 20
        # File Name column is 4th col (~offset 450 from grid left), Description is 3rd col (~offset 250)
        FILENAME_X = grid_rect[0] + 450
        DESC_X     = grid_rect[0] + 250

        def click_filename_cell(row_idx):
            y = grid_rect[1] + HEADER_H + (row_idx * ROW_H) + (ROW_H // 2)
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

        # ── Bring main window to foreground ──
        try:
            win32gui.ShowWindow(self.main_hwnd, win32con.SW_SHOWMAXIMIZED)
            win32gui.SetForegroundWindow(self.main_hwnd)
            time.sleep(0.8)
        except Exception as fe:
            print(f"  [PROCESSES GRID] Focus: {fe}")

        # ── Locate grid rect at runtime ──
        cc_win = self.app.window(handle=cc_hwnd)
        grid = cc_win.child_window(auto_id="dgvBillProcess", control_type="Pane")
        grid.wait("visible", timeout=10)
        time.sleep(0.3)

        grid_rect    = win32gui.GetWindowRect(grid.handle)
        HEADER_H     = 22
        ROW_H        = 28

        SETTLEMENT_X = grid_rect[0] + 100   # center of Settlement column
        CHECKBOX_X   = grid_rect[0] + 15    # center of checkbox inside Selected column

        def row_centre_y(row_idx):
            return grid_rect[1] + HEADER_H + (row_idx * ROW_H) + (ROW_H // 2)

        # ── Anchor focus on first Settlement cell ──
        anchor_y = row_centre_y(0)
        print(f"  [PROCESSES GRID] Grid rect: {grid_rect}")
        print(f"  [PROCESSES GRID] SETTLEMENT_X={SETTLEMENT_X}  CHECKBOX_X={CHECKBOX_X}")
        print(f"  [PROCESSES GRID] Anchoring focus at Settlement ({SETTLEMENT_X}, {anchor_y})")
        mouse.click(button='left', coords=(SETTLEMENT_X, anchor_y))
        time.sleep(1.5)

    def process_processes_grid_selection(self, cc_hwnd, target_settlement):
        if not target_settlement:
            print("  [PROCESSES GRID] No target settlement specified. Skipping.")
            return

        target_clean = target_settlement.strip()[:2].lower()
        print(f"\n[PROCESSES GRID] Scanning for settlement prefix: '{target_clean}' (from '{target_settlement}')...")
        time.sleep(3.5)

        # ── Bring main window to foreground ──
        try:
            win32gui.ShowWindow(self.main_hwnd, win32con.SW_SHOWMAXIMIZED)
            win32gui.SetForegroundWindow(self.main_hwnd)
            time.sleep(0.8)
        except Exception as fe:
            print(f"  [PROCESSES GRID] Focus: {fe}")

        # ── Locate grid rect at runtime ──
        cc_win = self.app.window(handle=cc_hwnd)
        grid = cc_win.child_window(auto_id="dgvBillProcess", control_type="Pane")
        grid.wait("visible", timeout=10)
        time.sleep(0.3)

        grid_rect    = win32gui.GetWindowRect(grid.handle)
        HEADER_H     = 22
        ROW_H        = 28

        SETTLEMENT_X = grid_rect[0] + 100
        CHECKBOX_X   = grid_rect[0] + 15

        def row_centre_y(row_idx):
            return grid_rect[1] + HEADER_H + (row_idx * ROW_H) + (ROW_H // 2)

        # ── Anchor focus on first Settlement cell ──
        anchor_y = row_centre_y(0)
        print(f"  [PROCESSES GRID] Grid rect: {grid_rect}")
        print(f"  [PROCESSES GRID] SETTLEMENT_X={SETTLEMENT_X}  CHECKBOX_X={CHECKBOX_X}")
        print(f"  [PROCESSES GRID] Anchoring focus at Settlement ({SETTLEMENT_X}, {anchor_y})")
        mouse.click(button='left', coords=(SETTLEMENT_X, anchor_y))
        time.sleep(1.5)

        # ── PASS 1: Scan rows ──
        MAX_ROWS     = 20
        matched_rows = []

        for row_idx in range(MAX_ROWS):
            current_y = row_centre_y(row_idx)

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
            print(f"  [PROCESSES GRID] Row {row_idx}: '{cell_text}' (y={current_y})")

            if not cell_text:
                print("  [PROCESSES GRID] Empty cell — end of data.")
                break

            if cell_text[:2] == target_clean:
                print(f"  ✓ Prefix match at row {row_idx}")
                matched_rows.append((row_idx, current_y))

            send_keys("{DOWN}")
            time.sleep(0.3)

        if not matched_rows:
            print(f"  [PROCESSES GRID] CRITICAL: '{target_clean}' not found.")
            return

        print(f"  [PROCESSES GRID] Matched rows: {[r for r, y in matched_rows]}")

        # ── PASS 2: Confirm and toggle checkboxes ──
        for row_idx, scan_y in matched_rows:
            print(f"  [PROCESSES GRID] Re-anchoring row {row_idx} → clicking Settlement ({SETTLEMENT_X}, {scan_y})")
            mouse.click(button='left', coords=(SETTLEMENT_X, scan_y))
            time.sleep(0.6)

            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.CloseClipboard()
            except:
                pass
            send_keys("^c")
            time.sleep(0.4)
            confirmed = self.get_clipboard_text().lower().strip()
            print(f"  [PROCESSES GRID] Confirmed: '{confirmed}'")

            if confirmed[:2] != target_clean:
                print(f"  ⚠ Row {row_idx} re-anchor mismatch ('{confirmed}') — skipping.")
                continue

            checkbox_toggled = False
            try:
                print(f"  [PROCESSES GRID] Attempting keyboard toggle: HOME → SPACE")
                send_keys("{HOME}")
                time.sleep(0.3)
                send_keys("{SPACE}")
                time.sleep(0.5)
                print(f"  [PROCESSES GRID] ✓ Checkbox toggled via SPACE for row {row_idx}")
                checkbox_toggled = True
            except Exception as kb_err:
                print(f"  [PROCESSES GRID] Keyboard toggle failed: {kb_err}")

            if not checkbox_toggled:
                print(f"  [PROCESSES GRID] Falling back to pixel click for row {row_idx}")
                mouse.click(button='left', coords=(SETTLEMENT_X, scan_y))
                time.sleep(0.4)

                for x_offset in [15, 20, 10, 25, 30]:
                    test_checkbox_x = grid_rect[0] + x_offset
                    print(f"  [PROCESSES GRID] Trying checkbox pixel click at ({test_checkbox_x}, {scan_y})")
                    mouse.click(button='left', coords=(test_checkbox_x, scan_y))
                    time.sleep(0.4)

                    try:
                        mouse.click(button='left', coords=(SETTLEMENT_X, scan_y))
                        time.sleep(0.3)
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.CloseClipboard()
                        send_keys("^c")
                        time.sleep(0.3)
                        verify_text = self.get_clipboard_text().lower().strip()
                        if verify_text[:2] == target_clean:
                            print(f"  [PROCESSES GRID] ✓ Pixel click succeeded at x_offset={x_offset}")
                            break
                    except:
                        pass

            print(f"  [PROCESSES GRID] ✓ Row {row_idx} checkbox processed.")
            time.sleep(0.3)

        print(f"  [PROCESSES GRID] All {len(matched_rows)} checkbox(es) processed ✓")
        time.sleep(0.5)

        # ── Proceed via AutomationId ──
        print("  [PROCESSES GRID] Clicking Proceed...")
        btn = cc_win.child_window(auto_id="btnProcessProceed", control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()
        time.sleep(2.0)

        # ── Close any report popup that opens after Proceed ──
        print("  [PROCESSES GRID] Checking for report popup after Proceed click...")
        self._close_report_popup()
        time.sleep(1.5)

        # ── Re-acquire cc_win after popup close (handle may have refreshed) ──
        print("  [PROCESSES GRID] Re-acquiring Control Center window handle...")
        try:
            cc_win = self.app.window(handle=cc_hwnd)
            cc_win.wait("visible", timeout=10)
            win32gui.SetForegroundWindow(cc_hwnd)
            time.sleep(1.0)
        except Exception as reacq_err:
            print(f"  [PROCESSES GRID] Re-acquire warning: {reacq_err}")

        # ── Monitor dgvBillStatus for completion ──
        print("  [MONITOR] Locating process log panel (dgvBillStatus)...")
        try:
            status_table = cc_win.child_window(auto_id="dgvBillStatus", control_type="Table")
            status_table.wait("visible", timeout=20)
        except Exception as tbl_err:
            print(f"  [MONITOR] dgvBillStatus not found as Table, trying Pane fallback: {tbl_err}")
            try:
                status_table = cc_win.child_window(auto_id="dgvBillStatus", control_type="Pane")
                status_table.wait("visible", timeout=20)
            except Exception as pane_err:
                print(f"  [MONITOR] dgvBillStatus Pane fallback also failed: {pane_err}")
                # ── Last resort: dismiss msgbox and return ──
                self.dismiss_center_msgbox(cc_hwnd, date_value=None)
                self._close_report_popup()
                return

        status_rect = win32gui.GetWindowRect(status_table.handle)
        console_x = (status_rect[0] + status_rect[2]) // 2
        console_y = (status_rect[1] + status_rect[3]) // 2

        print("  [MONITOR] Waiting for 'Process Completed'...")
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
                    print("  [MONITOR] ✓ 'Process Completed' detected. Progressing pipeline.")
                    break
            except Exception as monitor_err:
                print(f"  [MONITOR WARNING] {monitor_err}")

            time.sleep(check_interval)

        self.dismiss_center_msgbox(cc_hwnd, date_value=None)
        self._close_report_popup()

    def set_control_center_date(self, cc_hwnd, date_value):
        # Normalize incoming config input to standard Application format (DD/MM/YYYY)
        date_value = _normalize_to_dd_mm_yyyy(date_value)
        print(f"Setting Control Center date to: '{date_value}'")
        time.sleep(0.5)

        # Locate via AutomationId='dtMain' — no coordinates
        cc_win = self.app.window(handle=cc_hwnd)
        date_ctrl = cc_win.child_window(auto_id="dtMain", control_type="Pane")
        date_ctrl.wait("visible", timeout=10)
        date_hwnd = date_ctrl.handle
        date_rect  = win32gui.GetWindowRect(date_hwnd)

        # Parse standardized components
        clean_date = date_value.replace(" ", "/")
        parts = clean_date.split("/")
        day   = int(parts[0])  
        month = int(parts[1])  
        year  = int(parts[2])  
        
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
        cc_win = self.app.window(handle=cc_hwnd)
        btn = cc_win.child_window(auto_id="btnProceed", control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()
        time.sleep(1.0)

    def click_processes_button(self, cc_hwnd):
        print("Clicking sidebar 'Processes' navigation button...")
        cc_win = self.app.window(handle=cc_hwnd)
        btn = cc_win.child_window(auto_id="btnOthers", control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()
        
        print("Waiting for Processes workspace view to fully render...")
        cc_win.child_window(auto_id="cmbProcProduct", control_type="ComboBox").wait("visible", timeout=15)
        print("  ✓ Processes workspace active and verified.")
        time.sleep(0.5)

    def set_product_selection(self, cc_hwnd, product_name):
        normalized_name = product_name.strip().capitalize()
        print(f"Setting Product Selection Dropdown to: '{normalized_name}'")
        
        cc_win = self.app.window(handle=cc_hwnd)
        combo = cc_win.child_window(auto_id="cmbProcProduct", control_type="ComboBox")
        combo.wait("visible enabled", timeout=10)
        combo.click_input()
        time.sleep(0.4)
        
        send_keys("{HOME}")
        time.sleep(0.3)
        if normalized_name == "Commodity":
            send_keys("{DOWN}")
            time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.8)

    def set_process_for_date(self, cc_hwnd, for_date_value):
        for_date_value = _normalize_to_dd_mm_yyyy(for_date_value)
        print(f"Setting Processes workspace 'For :' date to: '{for_date_value}'")
        
        cc_win = self.app.window(handle=cc_hwnd)
        date_ctrl = cc_win.child_window(auto_id="dtProcess", control_type="Pane")
        date_ctrl.wait("visible", timeout=10)
        date_hwnd = date_ctrl.handle
        date_rect = win32gui.GetWindowRect(date_hwnd)

        clean_date = for_date_value.replace(" ", "/")
        parts = clean_date.split("/")
        day   = int(parts[0])
        month = int(parts[1])
        year  = int(parts[2])
        
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
                send_keys("{RIGHT}{ENTER}")
            finally:
                ctypes.windll.kernel32.VirtualFreeEx(hProc, remote_mem, 0, 0x8000)
        finally:
            ctypes.windll.kernel32.CloseHandle(hProc)

    def click_process_fetch_button(self, cc_hwnd):
        print("Clicking workspace 'Fetch' button...")
        cc_win = self.app.window(handle=cc_hwnd)
        btn = cc_win.child_window(auto_id="btnProcFetch", control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()
        time.sleep(1.0)

    def set_processes_checkbox(self, cc_hwnd, auto_id, target_state=True):
        """
        Sets a functional configuration checkbox on the Processes tab using its explicit AutomationId.
        """
        print(f"Configuring Processes Checkbox [{auto_id}] -> Target State: {target_state}")
        cc_win = self.app.window(handle=cc_hwnd)
        chk = cc_win.child_window(auto_id=auto_id, control_type="CheckBox")
        chk.wait("visible", timeout=10)
        
        current = chk.get_toggle_state() # 0 = unchecked, 1 = checked
        desired = 1 if target_state else 0
        
        if current != desired:
            chk.click_input()
            time.sleep(0.5)
            print(f"  {auto_id} updated successfully.")
        else:
            print(f"  {auto_id} is already in the desired state.")

    def click_others_button(self, cc_hwnd):
        print("Clicking sidebar 'Others' navigation button...")
        cc_win = self.app.window(handle=cc_hwnd)
        btn = cc_win.child_window(auto_id="btnProcess", control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()
        
        print("Waiting for Others workspace layout to render...")
        cc_win.child_window(auto_id="cmbExch", control_type="ComboBox").wait("visible", timeout=15)
        print("  ✓ Others workspace verified active (cmbExch visible)")
        time.sleep(0.5)

    def set_others_exchange(self, cc_hwnd, exchange_name):
        target = exchange_name.strip().upper()
        if target not in ["BSE", "NSE"]:
            raise ValueError(f"Invalid Exchange selection: '{exchange_name}'. Must be 'BSE' or 'NSE'.")
        print(f"Setting Others Tab Exchange to: '{target}'")
        
        cc_win = self.app.window(handle=cc_hwnd)
        combo = cc_win.child_window(auto_id="cmbExch", control_type="ComboBox")
        combo.wait("visible enabled", timeout=10)
        combo.click_input()
        time.sleep(0.4)
        
        send_keys("{HOME}")
        time.sleep(0.3)
        if target == "NSE":
            send_keys("{DOWN}")
            time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.8)

    def set_others_segment(self, cc_hwnd, segment_name):
        target = segment_name.strip().upper()
        # Supports: CASH, F&O, FX, MF
        print(f"Setting Others Tab Segment to: '{target}'")
        
        cc_win = self.app.window(handle=cc_hwnd)
        combo = cc_win.child_window(auto_id="cmbSeg", control_type="ComboBox")
        combo.wait("visible enabled", timeout=10)
        combo.click_input()
        time.sleep(0.4)
        
        send_keys("{HOME}")
        time.sleep(0.3)
        
        # Incremental downward keyboard offset selectors
        if target in ["F&O", "FO", "F AND O"]:
            send_keys("{DOWN}")
        elif target in ["FX", "CURRENCY"]:
            send_keys("{DOWN 2}")
        elif target in ["MF", "MUTUAL FUNDS", "MUTUAL FUND"]:
            send_keys("{DOWN 3}")
            
        time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.8)

    def set_others_settlement(self, cc_hwnd, settlement_name):
        prefix_target = settlement_name.strip()[:2].upper()
        print(f"Selecting Settlement option via target tracking: '{prefix_target}'")
        
        cc_win = self.app.window(handle=cc_hwnd)
        combo = cc_win.child_window(auto_id="cmbStlmnt", control_type="ComboBox")
        combo.wait("visible enabled", timeout=10)
        target_hwnd = combo.handle
        
        combo.click_input()
        time.sleep(0.5)

        CB_SELECTSTRING = 0x014D
        CBN_SELCHANGE   = 1
        WM_COMMAND      = 0x0111

        matched_idx = win32api.SendMessage(target_hwnd, CB_SELECTSTRING, -1, prefix_target)
        
        if matched_idx != -1:
            print(f"  [WIN32 CB] Prefix match found at index: {matched_idx}")
            time.sleep(0.2)
            
            parent_form_hwnd = win32gui.GetParent(target_hwnd)
            control_id = win32gui.GetDlgCtrlID(target_hwnd)
            notification_message = (CBN_SELCHANGE << 16) | (control_id & 0xFFFF)
            win32api.SendMessage(parent_form_hwnd, WM_COMMAND, notification_message, target_hwnd)
            time.sleep(0.3)
            send_keys("{ESC}")
        else:
            print(f"  ⚠ Prefix missed for '{prefix_target}'. Running fallback injection context...")
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

    def select_others_execution_option(self, cc_hwnd, option_key):
        """
        Dynamically targets the execution row radio element by its unique AutomationId.
        """
        mapping = {
            "exchange_obligation_reconciliation": "optPrOblComp",
            "unprocess_bills": "optPrUnProc",
            "display_obligation_money_sheet": "optPrDispObgl",
            "accumulation_difference": "optPrAccuDiff",
            "stt_mismatch": "optPrSTTMismatch",
            "bill_reconciliation": "optPrBillReco"
        }
        
        target_auto_id = mapping.get(option_key.strip().lower())
        if not target_auto_id:
            print(f"  ⚠ Unknown 'Others' operational radio configuration lookup skipped: {option_key}")
            return

        print(f"Selecting Operational Radio Identifier Node: [{target_auto_id}] for option: {option_key}")
        cc_win = self.app.window(handle=cc_hwnd)
        radio = cc_win.child_window(auto_id=target_auto_id, control_type="RadioButton")
        radio.wait("visible enabled", timeout=10)
        radio.click_input()
        time.sleep(0.6)

    def click_others_workspace_proceed(self, cc_hwnd):
        print("Clicking workspace final execution 'Proceed' button...")
        cc_win = self.app.window(handle=cc_hwnd)
        btn = cc_win.child_window(auto_id="btnProcesses", control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()
        time.sleep(1.5)

        result = self._dismiss_others_proceed_popup()
        if result == "MISMATCH":
            raise Exception(
                "[OTHERS PROCEED] CRITICAL STOP: 'Mis Match Found' detected in post-Proceed dialog. "
                "Halting entire execution pipeline — data integrity check failed."
            )
        self._close_report_popup()

    def _dismiss_others_proceed_popup(self):
        """
        Polls up to 10 seconds for a post-Proceed confirmation or mismatch dialog.

        DIALOG MATCHING RULES (tight — avoids VB6 "Query Management" and other
        unrelated windows that happen to use WindowsForms classes):
          - Class is "#32770" (standard Win32 MessageBox)                   OR
          - Title contains "information", "are you sure", "mis match",
            "mismatch", or "reconcil"                                       OR
          - Class contains "windowsforms" AND title contains at least one
            of the above keywords   (prevents bare WindowsForms panels from
            matching, e.g. the "Query Management" VB6 host window)

        MISMATCH LOGIC:
          "mis match found"     → dismisses dialog cleanly, returns "MISMATCH"
                                  → caller raises Exception → pipeline stops
          "mis match not found" → dismisses safely, returns None → continue
          anything else         → dismisses safely, returns None → continue
          no dialog found       → returns None → continue

        KEYSTROKE SAFETY:
          Never fires send_keys("{ENTER}") unless GetForegroundWindow() confirms
          the dialog handle is in foreground — prevents stray keystrokes reaching
          the desktop taskbar or pinned CRM applications.
        """
        print("  [OTHERS PROCEED] Waiting for post-Proceed dialog box (up to 10 s)...")

        DIALOG_TITLE_KEYWORDS = ("information", "are you sure", "mis match", "mismatch", "reconcil")

        popup_hwnd = None
        for _poll in range(20):        # 20 × 0.5 s = 10 s max
            time.sleep(0.5)
            candidate = None

            def _find_dialog(hwnd, _):
                nonlocal candidate
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return True
                    if hwnd == self.main_hwnd:
                        return True
                    cls   = win32gui.GetClassName(hwnd)
                    title = win32gui.GetWindowText(hwnd).lower().strip()

                    # Standard Win32 message box — always match
                    if cls == "#32770":
                        candidate = hwnd
                        return True

                    title_hit = any(kw in title for kw in DIALOG_TITLE_KEYWORDS)

                    # WindowsForms window: only match when title also has a keyword
                    # (avoids grabbing the "Query Management" VB6 host or CC panel)
                    if "windowsforms" in cls.lower() and title_hit:
                        candidate = hwnd
                        return True

                    # Any other non-WF class with a matching title
                    if title_hit:
                        candidate = hwnd
                        return True

                except:
                    pass
                return True

            win32gui.EnumWindows(_find_dialog, None)

            if candidate:
                popup_hwnd = candidate
                break

        if not popup_hwnd:
            print("  [OTHERS PROCEED] No confirmation dialog detected. Continuing ✓")
            return None

        dialog_title = win32gui.GetWindowText(popup_hwnd)
        print(f"  [OTHERS PROCEED] Dialog found: '{dialog_title}' handle={popup_hwnd}")
        time.sleep(0.3)

        # ── Collect ALL visible child text from the dialog ──
        text_parts = [dialog_title.lower()]
        def _collect(hwnd, _):
            try:
                t = win32gui.GetWindowText(hwnd).strip()
                if t:
                    text_parts.append(t.lower())
            except:
                pass
            return True
        try:
            win32gui.EnumChildWindows(popup_hwnd, _collect, None)
        except:
            pass

        combined = " ".join(text_parts)
        print(f"  [OTHERS PROCEED] Dialog content: {combined!r}")

        # ── MISMATCH DETECTION ──
        is_mismatch_found     = "mis match found"     in combined or "mismatch found"     in combined
        is_mismatch_not_found = "mis match not found" in combined or "mismatch not found" in combined

        if is_mismatch_found and not is_mismatch_not_found:
            print("  [OTHERS PROCEED] ⛔ CRITICAL: 'Mis Match Found' — stopping pipeline.")
            # Cleanly dismiss the dialog before propagating the stop signal
            self._click_ok_or_close_on_dialog(popup_hwnd)
            return "MISMATCH"

        if is_mismatch_not_found:
            print("  [OTHERS PROCEED] ✓ 'Mis Match Not Found' confirmed — safe to continue.")
        else:
            print("  [OTHERS PROCEED] Normal confirmation dialog — dismissing and continuing.")

        self._click_ok_or_close_on_dialog(popup_hwnd)
        return None

    def _click_ok_or_close_on_dialog(self, popup_hwnd):
        """
        Brings popup_hwnd to foreground then dismisses it via:
          1. BM_CLICK on OK / Yes button handle (preferred — no focus dependency)
          2. send_keys("{ENTER}") only when GetForegroundWindow confirms focus
          3. PostMessage(WM_CLOSE) as last resort if focus cannot be obtained
        """
        # Bring to foreground
        try:
            win32gui.SetForegroundWindow(popup_hwnd)
            time.sleep(0.4)
        except:
            pass

        # Find OK / Yes button
        btn_hwnd = None
        def _find_ok(hwnd, _):
            nonlocal btn_hwnd
            try:
                raw   = win32gui.GetWindowText(hwnd).strip()
                clean = raw.replace("&", "").lower()
                cls   = win32gui.GetClassName(hwnd)
                if clean in ("ok", "yes") and "button" in cls.lower() and win32gui.IsWindowVisible(hwnd):
                    btn_hwnd = hwnd
            except:
                pass
            return True
        try:
            win32gui.EnumChildWindows(popup_hwnd, _find_ok, None)
        except:
            pass

        if btn_hwnd:
            try:
                win32api.SendMessage(btn_hwnd, 0x00F5, 0, 0)   # BM_CLICK
                time.sleep(0.5)
                print("  [OTHERS PROCEED] Dismissed via BM_CLICK ✓")
                return
            except Exception as e:
                print(f"  [OTHERS PROCEED] BM_CLICK failed: {e}")

        # send_keys only when we truly own foreground
        if win32gui.GetForegroundWindow() == popup_hwnd:
            send_keys("{ENTER}")
            time.sleep(0.5)
            print("  [OTHERS PROCEED] Dismissed via {ENTER} ✓")
        else:
            win32api.PostMessage(popup_hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(0.5)
            print("  [OTHERS PROCEED] Dismissed via WM_CLOSE ✓")

    def click_file_imports_button(self, cc_hwnd):
        print("Clicking sidebar 'File Imports' navigation button...")
        cc_win = self.app.window(handle=cc_hwnd)
        btn = cc_win.child_window(auto_id="btnImports", control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()

        # Wait for File Imports tab/workspace to be active — poll for cmbProduct
        print("Waiting for File Imports workspace view to fully render and open...")
        cc_win.child_window(auto_id="cmbProduct", control_type="ComboBox").wait("visible", timeout=15)
        print("  ✓ File Imports workspace active and verified (cmbProduct visible)")
        time.sleep(0.5)

    def set_imports_product(self, cc_hwnd, product_name):
        print(f"Setting Imports Workspace Product to: '{product_name}'")
        cc_win = self.app.window(handle=cc_hwnd)
        combo = cc_win.child_window(auto_id="cmbProduct", control_type="ComboBox")
        combo.wait("visible enabled", timeout=10)
        combo.click_input()
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
        cc_win = self.app.window(handle=cc_hwnd)
        combo = cc_win.child_window(auto_id="cmbFileType", control_type="ComboBox")
        combo.wait("visible enabled", timeout=10)
        combo.click_input()
        time.sleep(0.4)
        send_keys("{HOME}")
        time.sleep(0.2)
        if type_name.strip().upper() == "UDIFF":
            send_keys("{DOWN}")
            time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.5)

    def check_matrix_checkbox(self, cc_hwnd, checkbox_id, state=True):
        """
        Sets any specified matrix checkbox within grpTplus to the desired state 
        using its explicit AutomationId.
        """
        print(f"Configuring Matrix Checkbox Identifier [{checkbox_id}] -> Target State: {state}")

        cc_win = self.app.window(handle=cc_hwnd)
        chk = cc_win.child_window(auto_id=checkbox_id, control_type="CheckBox")
        chk.wait("visible", timeout=10)

        current = chk.get_toggle_state()   # 0 = unchecked, 1 = checked
        desired  = 1 if state else 0

        if current != desired:
            chk.click_input()
            time.sleep(0.8)
            print(f"  {checkbox_id} set to {'CHECKED' if state else 'UNCHECKED'} ✓")
        else:
            print(f"  {checkbox_id} already {'CHECKED' if state else 'UNCHECKED'} — no change")

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
                matrix_checkboxes=None, bse_files_workflow=None, nse_files_workflow=None,
                click_processes=False, product=None, for_date=None, click_fetch=False,
                click_others=False, exchange=None, settlement=None, exchange_obligation_reconciliation=False, unprocess_bills=False,
                raw_workflow_config=None):
        
        while True:
            cc_hwnd = self._get_control_center_hwnd()
            if date is not None:
                self.set_control_center_date(cc_hwnd, date)
                time.sleep(0.2)
                self.click_proceed_button(cc_hwnd)
                time.sleep(0.5)
            break 

        execution_sequence = ["file_imports", "others", "processes"]
        print(f"[DYNAMIC ROUTER] Computed task sequence pipeline order: {execution_sequence}")

        for step in execution_sequence:
            cc_hwnd = self._get_control_center_hwnd()

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

                # Unified, single loop execution for matrix checkboxes
                if matrix_checkboxes and isinstance(matrix_checkboxes, dict):
                    for target_cb_id, cb_enabled in matrix_checkboxes.items():
                        if not cb_enabled:
                            continue
                        
                        print(f"\n  [SEQUENCER PASS] Activating matrix segment grid targeting: {target_cb_id}...")
                        self.check_matrix_checkbox(cc_hwnd, checkbox_id=target_cb_id, state=True)
                        time.sleep(0.5)

                        print(f"  [TIMER] Waiting 10 seconds for {target_cb_id} grid data to load...")
                        time.sleep(10.0)

                        active_segment = "NSE" if "NSE" in target_cb_id.upper() else "BSE"
                        active_workflow = nse_files_workflow if active_segment == "NSE" else bse_files_workflow

                        status = self.scan_and_process_data_grid(cc_hwnd, active_workflow, date_value=date, current_segment=active_segment)

                        print(f"  [SEQUENCER PASS] Clearing {target_cb_id} selection state...")
                        self.check_matrix_checkbox(cc_hwnd, checkbox_id=target_cb_id, state=False)
                        print("  [SEQUENCER PASS] Holding thread for interface refresh synchronization...")
                        time.sleep(1.5)

                        if status == "RESTART":
                            return "RESTART"

            elif step == "others" and click_others:
                print("\n--- Executing Others Suite ---")
                self.click_others_button(cc_hwnd)
                time.sleep(0.5)

                if exchange is not None:
                    self.set_others_exchange(cc_hwnd, exchange)

                others_block = raw_workflow_config.get("others", {})
                segment_val = others_block.get("segment")
                if segment_val is not None:
                    self.set_others_segment(cc_hwnd, segment_val)

                if settlement is not None:
                    self.set_others_settlement(cc_hwnd, settlement)

                options_to_check = [
                    "exchange_obligation_reconciliation", 
                    "unprocess_bills", 
                    "display_obligation_money_sheet", 
                    "accumulation_difference", 
                    "stt_mismatch", 
                    "bill_reconciliation"
                ]
                
                for option in options_to_check:
                    if others_block.get(option, False):
                        self.select_others_execution_option(cc_hwnd, option)
                        break

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

                # Set structural options checkboxes parsed out from JSON parameters tracking
                proc_block = raw_workflow_config.get("processes", {})
                checkbox_mappings = {
                    "bill_generation": "chkBillGenerate",
                    "accumulation": "chkProcAccumulate",
                    "agts": "chkAGTS",
                    "revenue_sharing": "chkRemShare",
                    "lock_bill_prior": "chkLockBill"
                }

                for json_key, auto_id in checkbox_mappings.items():
                    if json_key in proc_block:
                        self.set_processes_checkbox(cc_hwnd, auto_id, target_state=proc_block[json_key])

                if click_fetch:
                    self.click_process_fetch_button(cc_hwnd)
                    time.sleep(0.5)
                    
                    target_settlement_name = proc_block.get("target_settlement")
                    if target_settlement_name:
                        self.process_processes_grid_selection(cc_hwnd, target_settlement_name)
                        time.sleep(0.8)

        print("ControlCenterPage dynamic sequencing suite processing completed successfully.")
        return "SUCCESS"