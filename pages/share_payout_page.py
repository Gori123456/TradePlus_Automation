import time
import win32con
import win32gui
import win32api
import win32clipboard
from pywinauto.keyboard import send_keys
from pywinauto import mouse


class SharePayoutPage:

    def __init__(self, app):
        self.app = app
        self.main_hwnd = win32gui.FindWindow("WindowsForms10.Window.8.app.0.141b42a_r7_ad1", "TradePlusX")
        if not self.main_hwnd:
            raise Exception("TradePlusX main window handle not found inside SharePayoutPage!")

    def _wait_and_handle_areyousure_dialog(self):
        """
        Called immediately after settlement ENTER is sent.
        Blocks for up to 6 seconds waiting for the 'Are You Sure?' dialog.
        
        Detection: scans children of every visible window for a Yes+No button pair.
        This works regardless of the dialog's title or Win32 class name.
        
        If dialog found  → clicks Yes button by screen coordinate → returns True
        If not found in 6s → returns False (no dialog appeared, safe to continue)
        """
        print("  [DIALOG WAIT] Waiting up to 6s for 'Are You Sure?' dialog...")

        deadline = time.time() + 6.0

        while time.time() < deadline:
            # Scan every visible top-level window for one that has both Yes and No buttons
            found_dialog_hwnd = None
            found_yes_hwnd    = None

            def scan_top(hwnd, _):
                nonlocal found_dialog_hwnd, found_yes_hwnd
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return True
                    if hwnd == self.main_hwnd:
                        return True

                    # Check children of this window for Yes / No buttons
                    yes_h = None
                    no_h  = None

                    def scan_children(ch, _):
                        nonlocal yes_h, no_h
                        try:
                            ct = win32gui.GetWindowText(ch).strip()
                            cc = win32gui.GetClassName(ch)
                            # WinForms buttons have class "WindowsForms10.BUTTON..." or "Button"
                            if "button" in cc.lower() or cc == "Button":
                                if ct.lower() == "yes":
                                    yes_h = ch
                                elif ct.lower() == "no":
                                    no_h = ch
                        except:
                            pass
                        return True

                    try:
                        win32gui.EnumChildWindows(hwnd, scan_children, None)
                    except:
                        pass

                    # Only treat as our dialog if it has BOTH Yes and No buttons
                    if yes_h and no_h:
                        found_dialog_hwnd = hwnd
                        found_yes_hwnd    = yes_h

                except:
                    pass
                return True

            win32gui.EnumWindows(scan_top, None)

            if found_dialog_hwnd and found_yes_hwnd:
                title = win32gui.GetWindowText(found_dialog_hwnd)
                print(f"  [DIALOG WAIT] Dialog found! hwnd={found_dialog_hwnd} title={title!r}")
                print(f"  [DIALOG WAIT] Yes button hwnd={found_yes_hwnd}")

                try:
                    # Bring dialog to front
                    win32gui.ShowWindow(found_dialog_hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(found_dialog_hwnd)
                    time.sleep(0.3)

                    # Click Yes button directly using its screen coordinates
                    rect = win32gui.GetWindowRect(found_yes_hwnd)
                    cx = (rect[0] + rect[2]) // 2
                    cy = (rect[1] + rect[3]) // 2
                    print(f"  [DIALOG WAIT] Clicking Yes at ({cx}, {cy})")
                    mouse.click(button='left', coords=(cx, cy))
                    time.sleep(1.0)
                    print("  [DIALOG WAIT] Dialog dismissed. Proceeding to Fetch.")
                    return True

                except Exception as e:
                    print(f"  [DIALOG WAIT] Click failed: {e}. Sending ENTER...")
                    send_keys("{ENTER}")
                    time.sleep(1.0)
                    return True

            time.sleep(0.1)

        print("  [DIALOG WAIT] No Yes/No dialog appeared within 6s. Continuing to Fetch.")
        return False

    def process(self, date_value, settlement_name, target_process_name):
        self.window = self.app.top_window()
        self.window.wait("ready", timeout=30)

        # ==========================
        # 1. DATE SELECTION
        # ==========================
        print(f"Setting Date value to: {date_value}")
        date_pane = self.window.child_window(auto_id="dtMain", control_type="Pane")
        date_pane.click_input(coords=(5, 10))
        time.sleep(0.5)
        send_keys("^a")
        time.sleep(0.3)
        send_keys("{BACKSPACE}")
        time.sleep(0.3)
        send_keys(date_value)
        time.sleep(0.3)
        send_keys("{ENTER}")
        print(f"Date Selected: {date_value}")
        time.sleep(1.5)

        # ==========================
        # 2. SETTLEMENT SELECTION
        # ==========================
        print(f"Targeting Settlement Name: {settlement_name}")

        dots_button = self.window.child_window(title="...", auto_id="btnHelp", control_type="Button")
        dots_button.click_input()
        time.sleep(1.5)

        try:
            dropdown_table = self.window.child_window(title="DataGridView", auto_id="dgvStlmnt", control_type="Table")
            cells = dropdown_table.descendants(control_type="DataItem")
            prefix = str(settlement_name).strip()[:2].upper()
            target_cell = None
            for cell in cells:
                cell_text = str(cell.window_text()).strip().upper()
                if cell_text.startswith(prefix):
                    target_cell = cell
                    print(f"  Matched cell '{cell_text}' using prefix '{prefix}'")
                    break

            if target_cell:
                target_cell.click_input()
                time.sleep(0.5)
                send_keys("{ENTER}")
                print(f"Settlement prefix '{prefix}' confirmed with ENTER.")
            else:
                raise Exception(f"No cell starting with '{prefix}' found in grid.")

        except Exception as e:
            print(f"Direct selection failed: {e}. Using coordinate fallback...")
            SETTLEMENT_Y_OFFSETS = {
                "BM": 248,
                "NM": 269,
                "NQ": 290,
                "NU": 311,
                "NA": 332
            }
            prefix = str(settlement_name).strip()[:2].upper()
            if prefix in SETTLEMENT_Y_OFFSETS:
                table_rect = self.window.child_window(title="DataGridView", auto_id="dgvStlmnt", control_type="Table").rectangle()
                click_x = table_rect.left + 50
                click_y = table_rect.top + (SETTLEMENT_Y_OFFSETS[prefix] - 202)
                mouse.click(button='left', coords=(click_x, click_y))
                time.sleep(0.5)
                send_keys("{ENTER}")
                print(f"Settlement prefix '{prefix}' confirmed via coordinate fallback.")
            else:
                print(f"CRITICAL ERROR: prefix '{prefix}' not found in offset map.")

        self._wait_and_handle_areyousure_dialog()

        self.window = self.app.top_window()

        # ==========================================
        # 3. FETCH
        # ==========================================
        try:
            error_dialog = self.window.child_window(title="Information", control_type="Window")
            if error_dialog.exists(timeout=1):
                error_dialog.child_window(title="OK", control_type="Button").click_input()
                time.sleep(0.5)
        except:
            pass

        already_has_data = False
        try:
            grid = self.window.child_window(title="DataGridView", auto_id="dgvDemat", control_type="Table")
            if grid.exists(timeout=1):
                grid.set_focus()
                time.sleep(0.2)
                grid_rect = grid.rectangle()
                row_height    = 24
                header_height = 22
                col2_x = grid_rect.left + 250
                row1_y = grid_rect.top + header_height + (row_height // 2)
                mouse.click(button='left', coords=(col2_x, row1_y))
                time.sleep(0.3)
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.CloseClipboard()
                except:
                    pass
                time.sleep(0.05)
                send_keys("^c")
                time.sleep(0.25)
                sample_text = self.get_clipboard_text().strip()
                if sample_text:
                    print(f"  [DEMAT CHECK] Grid already has data ('{sample_text}'). Skipping Fetch.")
                    already_has_data = True
                else:
                    print("  [DEMAT CHECK] Grid blank. Running Fetch.")
        except Exception as check_err:
            print(f"  [DEMAT CHECK] {check_err}")

        if not already_has_data:
            print("Locating Fetch button...")
            time.sleep(0.8)
            fetch_clicked = False

            # TIER 1: Pywinauto UIA
            try:
                for target_id in ["cmdFetech", "cmdFetch"]:
                    if self.window.child_window(auto_id=target_id, control_type="Button").exists(timeout=0.5):
                        self.window.child_window(auto_id=target_id, control_type="Button").click_input()
                        print(f"  ✓ Fetch clicked via UIA id: {target_id}")
                        fetch_clicked = True
                        break
            except Exception as uia_err:
                print(f"  UIA bypassed: {uia_err}")

            # TIER 2: Win32 child scan
            if not fetch_clicked:
                children = []
                def enum_cb(hwnd, _):
                    try:
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd).strip().lower()
                            if "fetch" in title or "fetech" in title:
                                children.append((hwnd, win32gui.GetWindowRect(hwnd)))
                    except:
                        pass
                    return True
                win32gui.EnumChildWindows(self.window.handle, enum_cb, None)
                if not children:
                    win32gui.EnumChildWindows(self.main_hwnd, enum_cb, None)
                if children:
                    fetch_rect = children[0][1]
                    cx = (fetch_rect[0] + fetch_rect[2]) // 2
                    cy = (fetch_rect[1] + fetch_rect[3]) // 2
                    win32gui.SetForegroundWindow(self.main_hwnd)
                    time.sleep(0.2)
                    mouse.click(button='left', coords=(cx, cy))
                    print(f"  ✓ Fetch clicked via Win32 at ({cx}, {cy})")
                    fetch_clicked = True

            # TIER 3: Fixed coordinate fallback
            if not fetch_clicked:
                win_rect = self.window.rectangle()
                fallback_x = win_rect.left + 680
                fallback_y = win_rect.top + 150
                win32gui.SetForegroundWindow(self.main_hwnd)
                time.sleep(0.1)
                mouse.click(button='left', coords=(fallback_x, fallback_y))
                print(f"  ✓ Fetch clicked via coordinate fallback ({fallback_x}, {fallback_y})")
                fetch_clicked = True

            if not fetch_clicked:
                raise Exception("CRITICAL: All Fetch strategies failed!")

            print("  Waiting for data grid...")
            time.sleep(8)
        else:
            time.sleep(1.0)

        # ==========================
        # 4. CLICK TARGET PROCESS
        # ==========================
        self.click_process_by_live_clipboard_scan(target_process_name)

        # ==========================
        # 5. CLOSE WINDOW
        # ==========================
        print("Finishing workflow...")
        time.sleep(15.0)
        self.close_window()

    def get_clipboard_text(self):
        try:
            win32clipboard.OpenClipboard()
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return str(data)
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return ""

    def _handle_post_process_confirmation_screens(self):
        """Monitors and processes optional secondary verification screens and report modals."""
        print("Checking for intermediate Demat confirmation views...")
        time.sleep(1.5)

        confirm_hwnd = None
        def find_confirm_window(hwnd, _):
            nonlocal confirm_hwnd
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if "demat processes" in title or "pay-in" in title or "processes" in title:
                        if hwnd != self.main_hwnd:
                            confirm_hwnd = hwnd
            except: pass
            return True

        win32gui.EnumWindows(find_confirm_window, None)

        # Scene A: The "Demat Processes" confirmation grid sub-window appears (image_720bc6.png)
        if confirm_hwnd:
            print(f"  [CONFIRMATION SCREEN] Identified active validation layout frame: handle={confirm_hwnd}")
            
            continue_btn_rect = None
            children = []
            def enum_children(hwnd, _):
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd).strip()
                        cls = win32gui.GetClassName(hwnd).lower()
                        if "continue" in title.lower() and "button" in cls:
                            children.append(win32gui.GetWindowRect(hwnd))
                except: pass
                return True

            win32gui.EnumChildWindows(confirm_hwnd, enum_children, None)

            if children:
                continue_btn_rect = children[0]
                cx = (continue_btn_rect[0] + continue_btn_rect[2]) // 2
                cy = (continue_btn_rect[1] + continue_btn_rect[3]) // 2
                print(f"    ✓ Target 'Continue' button isolated at ({cx}, {cy}). Clicking...")
                mouse.click(button='left', coords=(cx, cy))
            else:
                print("    WARNING: 'Continue' button text node obscured. Delivering standard safety {ENTER} sequence...")
                win32gui.SetForegroundWindow(confirm_hwnd)
                time.sleep(0.1)
                send_keys("{ENTER}")

            print("    Waiting for information report dialog to surface...")
            time.sleep(2.5)  # Breather to let calculations compile cleanly

        # Scene B: Intercept and dismiss the report generated dialogue alert popup (image_720805.png / image_3d458f.png)
        popup_hwnd = None
        for lookup_attempt in range(25):
            def find_info_box(hwnd, _):
                nonlocal popup_hwnd
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        cls = win32gui.GetClassName(hwnd)
                        title = win32gui.GetWindowText(hwnd).lower()
                        if "#32770" in cls or "information" in title or not title:
                            if hwnd != self.main_hwnd:
                                popup_hwnd = hwnd
                except: pass
                return True

            win32gui.EnumWindows(find_info_box, None)
            if popup_hwnd:
                break
            time.sleep(0.2)

        if popup_hwnd:
            print(f"  [ALERT INTERCEPT] Report generation popup captured: handle={popup_hwnd}. Clearing via direct Win32 message loop...")
            try:
                win32gui.ShowWindow(popup_hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
                win32gui.SetForegroundWindow(popup_hwnd)
                win32gui.SetActiveWindow(popup_hwnd)
                time.sleep(0.2)

                send_keys("{ENTER}")
                time.sleep(0.3)

                if win32gui.IsWindow(popup_hwnd) and win32gui.IsWindowVisible(popup_hwnd):
                    print("    ⚠ Dialog still present. Dispatching hardware virtual key message hooks...")
                    win32api.PostMessage(popup_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                    time.sleep(0.1)
                    win32api.PostMessage(popup_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                
                print("    ✓ Confirmation modal dismissed successfully.")
                time.sleep(1.0)
            except Exception as pe:
                print(f"    Fallback click routing trace exception error: {pe}. Retrying via safety keystroke sequence...")
                send_keys("{ENTER}")
        else:
            print("  ⚠ Notice: Post-process Information dialog popup window did not arrive or was bypassed.")

    def click_process_by_live_clipboard_scan(self, target_name):
        print(f"Scanning for target: '{target_name}'...")
        grid = self.window.child_window(title="DataGridView", auto_id="dgvDemat", control_type="Table")
        grid.set_focus()
        time.sleep(0.5)

        grid_rect = grid.rectangle()
        row_height    = 24
        header_height = 22
        col2_x = grid_rect.left + 250
        col1_x = grid_rect.left + 35
        row1_y = grid_rect.top + header_height + (row_height // 2)

        mouse.click(button='left', coords=(col2_x, row1_y))
        time.sleep(0.5)

        found_row_idx = None
        for row_idx in range(100):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.CloseClipboard()
            except:
                pass
            time.sleep(0.05)
            send_keys("^c")
            time.sleep(0.25)
            cell_text = self.get_clipboard_text().strip()
            print(f"  Row {row_idx}: '{cell_text}'")
            if target_name.lower() in cell_text.lower():
                print(f"  ✓ Found '{target_name}' at row {row_idx}")
                found_row_idx = row_idx
                break
            send_keys("{DOWN}")
            time.sleep(0.1)

        if found_row_idx is None:
            print(f"CRITICAL ERROR: '{target_name}' not found.")
            return

        grid_height  = grid_rect.bottom - grid_rect.top
        visible_rows = (grid_height - header_height) // row_height
        visual_offset = found_row_idx if found_row_idx < visible_rows else visible_rows - 1

        click_y = grid_rect.top + header_height + (visual_offset * row_height) + (row_height // 2)
        mouse.click(button='left', coords=(int(col1_x), int(click_y)))
        print(f"  Process button clicked at ({col1_x}, {click_y})")
        self._handle_post_process_confirmation_screens()
        time.sleep(15.0)

    def _get_demat_win_hwnd(self):
        for attempt in range(10):
            result = []
            def cb(hwnd, _):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if "share pay-in" in title.lower() or "pay-out processes" in title.lower():
                        result.append(hwnd)
                except:
                    pass
                return True
            win32gui.EnumChildWindows(self.main_hwnd, cb, None)
            if result and win32gui.IsWindowVisible(result[0]):
                return result[0]
            time.sleep(0.5)
        raise Exception("Demat Processes window not found!")

    def close_window(self):
        print("Closing Demat Processes window...")
        try:
            hwnd = self._get_demat_win_hwnd()
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            print("  Closed ✓")
        except Exception as e:
            print(f"  ⚠ Failed to close: {e}")