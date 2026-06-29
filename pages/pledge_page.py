import time
import threading
import ctypes
import ctypes.wintypes
import win32gui
import win32con
import win32api
from pywinauto import mouse
from pywinauto.keyboard import send_keys


TRADEPLUS_CLASS = "WindowsForms10.Window.8.app.0.141b42a_r7_ad1"
BUTTON_CLASS    = "WindowsForms10.BUTTON.app.0.141b42a_r7_ad1"
COMBO_CLASS     = "WindowsForms10.COMBOBOX.app.0.141b42a_r7_ad1"
DATETIME_CLASS  = "WindowsForms10.SysDateTimePick32.app.0.141b42a_r7_ad1"
TAB_CLASS       = "WindowsForms10.SysTabControl32.app.0.141b42a_r7_ad1"


# ══════════════════════════════════════════════════════════════════════
# LOW-LEVEL WIN32 HELPERS
# ══════════════════════════════════════════════════════════════════════

def _get_all_children(parent_hwnd):
    """Returns flat list of (hwnd, class, title, rect, visible) for all descendants."""
    out = []
    def _cb(hwnd, _):
        try:
            out.append((
                hwnd,
                win32gui.GetClassName(hwnd),
                win32gui.GetWindowText(hwnd),
                win32gui.GetWindowRect(hwnd),
                win32gui.IsWindowVisible(hwnd),
            ))
        except Exception:
            pass
        return True
    win32gui.EnumChildWindows(parent_hwnd, _cb, None)
    return out


def _click_rect_center(rect):
    """Physical mouse click at the centre of a screen rect (l,t,r,b)."""
    x = (rect[0] + rect[2]) // 2
    y = (rect[1] + rect[3]) // 2
    mouse.click(button='left', coords=(x, y))
    time.sleep(0.3)


def _bm_click(hwnd):
    """Sends BM_CLICK to a button/checkbox — no coordinate needed."""
    win32api.SendMessage(hwnd, win32con.BM_CLICK, 0, 0)
    time.sleep(0.25)


def _normalize_to_dd_mm_yyyy(date_str):
    if not date_str:
        return date_str
    s = str(date_str).strip()
    if len(s) == 8 and s.isdigit():                    # YYYYMMDD
        return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"
    s = s.replace("-", "/").replace(" ", "/")
    p = s.split("/")
    if len(p) == 3:
        if len(p[0]) == 4:                             # YYYY/MM/DD
            return f"{p[2]}/{p[1]}/{p[0]}"
        if len(p[2]) == 4:                             # DD/MM/YYYY already
            return f"{p[0]}/{p[1]}/{p[2]}"
    return s


# ══════════════════════════════════════════════
# POPUP KILLER THREAD (unchanged)
# ══════════════════════════════════════════════

def async_popup_killer(main_hwnd):
    print("[THREAD WATCHER] Scanning for dialog box contexts...")
    for _ in range(35):
        time.sleep(0.2)
        result = []
        def cb(hwnd, _):
            try:
                title = win32gui.GetWindowText(hwnd)
                cls   = win32gui.GetClassName(hwnd)
                if win32gui.IsWindowVisible(hwnd):
                    if ("information" in title.lower() or "confirm" in title.lower() or not title):
                        if "#32770" in cls or "WindowsForms10.Window" in cls:
                            r = win32gui.GetWindowRect(hwnd)
                            if r[2]-r[0] < 600 and r[3]-r[1] < 400:
                                result.append(hwnd)
            except Exception:
                pass
            return True
        win32gui.EnumChildWindows(main_hwnd, cb, None)
        if result:
            phwnd = result[0]
            print(f"[THREAD WATCHER] Popup hwnd={phwnd} — dismissing...")
            try:
                win32gui.ShowWindow(phwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(phwnd)
                time.sleep(0.15)
                send_keys("{ENTER}")
                print("[THREAD WATCHER] ✓ ENTER pressed ✓")
                return True
            except Exception as e:
                win32gui.PostMessage(phwnd, win32con.WM_CLOSE, 0, 0)
                return True
    print("[THREAD WATCHER] Timed out.")
    return False


# ══════════════════════════════════════════════════════════════════════
# PLEDGE PAGE
# ══════════════════════════════════════════════════════════════════════

class PledgePage:

    # ── Maps JSON checkbox label → (title_in_win32, class) ──────────────
    # Source: automation_ids.txt — Name field for each CheckBox control.
    # We match by WIN32 WINDOW TEXT (GetWindowText) because GetProp("ControlName")
    # is unreliable across the 32-bit/64-bit process boundary.
    _CHECKBOX_TITLE = {
        "items sold by client":                             "Items Sold By Client",
        "with epn-blk":                                    "With EPN-BLK",
        "deduct dp holding":                               "Deduct DP Holding",
        "by client & branch request":                      "By Client & Branch Request",
        "unapproved securities":                           "Unapproved Securities",
        "client with position":                            "Client with Position",
        "excess over":                                     "Excess Over",
        "items not re-pledged only":                       "Items Not Re-Pledged Only",
        "exclude re-pledged":                              "Exclude Re-Pledged",
        "by client not having margin requirement in past": "By Client Not Having Margin Requirement in Past ",
        "value after hair-cut below rs.":                  "Value After Hair-Cut Below Rs.",
        "value after hair-cut above rs.":                  "Value After Hair-Cut Above Rs.",
        "pledged in past":                                 "Pledged in Past ",
        "pledgee a/c":                                     "Pledgee A/c",
        "re-pledged to":                                   "Re-Pledged to",
        "re-pledged for":                                  "Re-Pledged for",
        "segment":                                         "Segment",
        "reject pending requests":                         "Reject Pending Requests",
    }

    def __init__(self, app):
        self.app = app
        self.main_hwnd = win32gui.FindWindow(TRADEPLUS_CLASS, "TradePlusX")
        if not self.main_hwnd:
            raise Exception("TradePlusX main window not found!")

    # ──────────────────────────────────────────
    # PLEDGE WINDOW LOCATOR
    # ──────────────────────────────────────────

    def _get_pledge_win_hwnd(self):
        """Finds the Margin-Pledge/Unpledge MDI child by window title."""
        for attempt in range(12):
            found = []
            def cb(hwnd, _):
                try:
                    t = win32gui.GetWindowText(hwnd).lower()
                    if ("pledge" in t or "unpledge" in t) and win32gui.IsWindowVisible(hwnd):
                        found.append(hwnd)
                except Exception:
                    pass
                return True
            win32gui.EnumChildWindows(self.main_hwnd, cb, None)
            if found:
                print(f"  [PLEDGE WIN] hwnd={found[0]}  title='{win32gui.GetWindowText(found[0])}'")
                return found[0]
            time.sleep(0.5)
        raise Exception("Pledge Management window not found after 12 attempts!")

    # ──────────────────────────────────────────
    # TAB CLICK  — physical mouse click via TCM_GETITEMRECT
    # ──────────────────────────────────────────

    def click_manage_tab(self):
        """
        Clicks the 'Manage' tab header with a real mouse event.

        WinForms TabControl ONLY fires SelectedIndexChanged (which swaps the
        visible panel) when it receives WM_LBUTTONDOWN at a valid tab-header
        pixel.  TCM_SETCURSEL alone does NOT trigger the event.

        We use TCM_GETITEMRECT (cross-process) to get the exact header rect so
        there are zero hardcoded screen coordinates.
        """
        print("Clicking tab: 'Manage'")
        pledge_hwnd = self._get_pledge_win_hwnd()
        win32gui.SetForegroundWindow(pledge_hwnd)
        time.sleep(0.3)

        children = _get_all_children(pledge_hwnd)

        # Find the SysTabControl32
        tab_hwnd = tab_rect = None
        for hwnd, cls, title, rect, vis in children:
            if cls == TAB_CLASS and vis:
                tab_hwnd, tab_rect = hwnd, rect
                break

        if not tab_hwnd:
            raise Exception("SysTabControl32 not found in Pledge window!")

        print(f"  [TAB] hwnd={tab_hwnd}  screen_rect={tab_rect}")

        # ── Cross-process TCM_GETITEMRECT to get exact tab header rect ──────
        TCM_GETITEMRECT = 0x130A
        MANAGE_TAB_IDX  = 1     # Pledge=0, Manage=1, Imports=2, Reports=3 …

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top",    ctypes.c_long),
                        ("right",ctypes.c_long), ("bottom", ctypes.c_long)]

        PROCESS_ALL_ACCESS = 0x1F0FFF
        MEM_COMMIT         = 0x1000
        MEM_RESERVE        = 0x2000
        PAGE_READWRITE     = 0x04

        pid = ctypes.wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(tab_hwnd, ctypes.byref(pid))
        hProc = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)

        click_x = click_y = None
        try:
            remote_rect = ctypes.windll.kernel32.VirtualAllocEx(
                hProc, None, ctypes.sizeof(RECT),
                MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
            try:
                ok = ctypes.windll.user32.SendMessageW(
                    tab_hwnd, TCM_GETITEMRECT, MANAGE_TAB_IDX, remote_rect)
                if ok:
                    local_rect = RECT()
                    read = ctypes.c_size_t(0)
                    ctypes.windll.kernel32.ReadProcessMemory(
                        hProc, remote_rect,
                        ctypes.byref(local_rect), ctypes.sizeof(RECT),
                        ctypes.byref(read))

                    # client rect → screen coords
                    cx_client = (local_rect.left + local_rect.right)  // 2
                    # Use 75 % down the tab header height so we're safely
                    # inside the clickable label area (not on the border).
                    cy_client = local_rect.top + int((local_rect.bottom - local_rect.top) * 0.75)

                    click_x = tab_rect[0] + cx_client
                    click_y = tab_rect[1] + cy_client
                    print(f"  [TAB] item rect (client) L={local_rect.left} T={local_rect.top} "
                          f"R={local_rect.right} B={local_rect.bottom}")
                    print(f"  [TAB] clicking screen ({click_x}, {click_y})")
            finally:
                ctypes.windll.kernel32.VirtualFreeEx(hProc, remote_rect, 0, 0x8000)
        finally:
            ctypes.windll.kernel32.CloseHandle(hProc)

        if click_x is None:
            # Fallback: rough estimate — each tab ~55 px wide, strip ~22 px tall
            click_x = tab_rect[0] + 82     # centre of 2nd tab
            click_y = tab_rect[1] + 16
            print(f"  [TAB] TCM_GETITEMRECT failed — fallback ({click_x},{click_y})")

        # Physical click — brings WinForms TabControl to fire its event handler
        mouse.click(button='left', coords=(click_x, click_y))
        time.sleep(1.5)

        # ── Verify: 'Items Sold By Client' checkbox must be visible now ──────
        ok = False
        for _ in range(6):
            ch = _get_all_children(pledge_hwnd)
            for hwnd, cls, title, rect, vis in ch:
                if cls == BUTTON_CLASS and vis and "items sold by client" in title.lower():
                    ok = True
                    break
            if ok:
                break
            time.sleep(0.5)

        if ok:
            print("  Tab 'Manage' activated and verified ✓")
        else:
            print("  [TAB] Manage panel still not visible — retrying click once...")
            mouse.click(button='left', coords=(click_x, click_y))
            time.sleep(2.0)
            print("  [TAB] Retry done.")

    # ──────────────────────────────────────────
    # ACTION COMBO  — matched by window title "Securities :"
    # From automation_ids.txt: cmbManage  Name='Securities :'
    # ──────────────────────────────────────────

    def set_manage_action(self, action_value):
        """Sets the action ComboBox (title='Securities :') to the requested value."""
        normalized = action_value.strip().lower()
        print(f"Setting action dropdown to: '{action_value}'")

        pledge_hwnd = self._get_pledge_win_hwnd()
        children    = _get_all_children(pledge_hwnd)

        combo_hwnd = combo_rect = None
        for hwnd, cls, title, rect, vis in children:
            # cmbManage has window text "Securities :" per automation_ids.txt
            if cls == COMBO_CLASS and vis and "securities" in title.lower():
                combo_hwnd, combo_rect = hwnd, rect
                break

        # Fallback: first VISIBLE combobox whose rect is in the upper portion
        # of the pledge window (the action combo is near the top of the panel)
        if not combo_hwnd:
            pledge_rect = win32gui.GetWindowRect(pledge_hwnd)
            upper_y     = pledge_rect[1] + (pledge_rect[3] - pledge_rect[1]) * 0.35
            for hwnd, cls, title, rect, vis in children:
                if cls == COMBO_CLASS and vis and rect[1] < upper_y:
                    combo_hwnd, combo_rect = hwnd, rect
                    print(f"  [COMBO] Fallback — using first upper ComboBox hwnd={hwnd} title='{title}'")
                    break

        if not combo_hwnd:
            raise Exception("Action ComboBox (cmbManage / 'Securities :') not found!")

        print(f"  [COMBO] hwnd={combo_hwnd}  title='{win32gui.GetWindowText(combo_hwnd)}'")

        if normalized in ("un-pledge", "un pledge", "unpledge"):
            search_term = "Un Pledge"
        elif normalized in ("un re-pledge", "un re pledge", "un repledge"):
            search_term = "Un Re-Pledge"
        else:
            search_term = "Pledge"

        CB_FINDSTRINGEXACT = 0x0158
        CB_SETCURSEL       = 0x014E
        CBN_SELCHANGE      = 1
        WM_COMMAND         = 0x0111

        idx = win32api.SendMessage(combo_hwnd, CB_FINDSTRINGEXACT, -1, search_term)
        if idx == -1:
            idx = 2 if "un re" in search_term.lower() else (1 if "un" in search_term.lower() else 0)
            print(f"  [COMBO] String not found — fallback index {idx}")

        win32api.SendMessage(combo_hwnd, CB_SETCURSEL, idx, 0)
        time.sleep(0.2)

        parent  = win32gui.GetParent(combo_hwnd)
        ctrl_id = win32gui.GetDlgCtrlID(combo_hwnd)
        win32api.SendMessage(parent, WM_COMMAND,
                             (CBN_SELCHANGE << 16) | (ctrl_id & 0xFFFF), combo_hwnd)
        send_keys("{ENTER}")
        time.sleep(0.5)
        print(f"  Action set to '{search_term}' (index {idx}) ✓")

    # ──────────────────────────────────────────
    # DATE PICKER  — matched by window title (date string) + DATETIME_CLASS
    # From automation_ids.txt: dtManageDate  Name='25/06/2026'
    # ──────────────────────────────────────────

    def set_manage_date(self, date_value):
        """Sets dtManageDate via cross-process SYSTEMTIME write."""
        date_value = _normalize_to_dd_mm_yyyy(date_value)
        print(f"Setting Manage date to: '{date_value}'")
        time.sleep(0.3)

        pledge_hwnd = self._get_pledge_win_hwnd()
        children    = _get_all_children(pledge_hwnd)

        # There are two DateTimePicker controls in the Manage tab:
        #   dtManageDate      (the main 'Date :' filter — upper area)
        #   dtManageExecDt    (Execution Date inside grpSave — lower/right area)
        # Pick the one that is HIGHER on screen (smaller rect[1]).
        date_controls = [(hwnd, rect) for hwnd, cls, title, rect, vis in children
                         if cls == DATETIME_CLASS and vis]

        if not date_controls:
            raise Exception("No DateTimePicker found in Pledge window!")

        # Sort by Y position — dtManageDate is the topmost one
        date_controls.sort(key=lambda x: x[1][1])
        date_hwnd, date_rect = date_controls[0]
        print(f"  [DATE] Using hwnd={date_hwnd}  rect={date_rect}")

        parts = date_value.split("/")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])

        PROCESS_ALL_ACCESS = 0x1F0FFF
        MEM_COMMIT         = 0x1000
        MEM_RESERVE        = 0x2000
        PAGE_READWRITE     = 0x04
        DTM_SETSYSTEMTIME  = 0x1002

        st = (ctypes.c_uint16(year).value.to_bytes(2, 'little') +
              ctypes.c_uint16(month).value.to_bytes(2, 'little') +
              ctypes.c_uint16(0).value.to_bytes(2, 'little') +
              ctypes.c_uint16(day).value.to_bytes(2, 'little') +
              b'\x00' * 8)
        buf = ctypes.create_string_buffer(16)
        ctypes.memmove(buf, st, 16)

        pid = ctypes.wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(date_hwnd, ctypes.byref(pid))
        hProc = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        try:
            remote = ctypes.windll.kernel32.VirtualAllocEx(
                hProc, None, 16, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
            try:
                ctypes.windll.kernel32.WriteProcessMemory(hProc, remote, buf, 16, None)
                _click_rect_center(date_rect)
                time.sleep(0.1)
                ctypes.windll.user32.SendMessageW(date_hwnd, DTM_SETSYSTEMTIME, 0, remote)
                time.sleep(0.2)
                send_keys("{RIGHT}{UP}{DOWN}{ENTER}")
                time.sleep(0.3)
                print(f"  ✓ Date set to '{date_value}' ✓")
            finally:
                ctypes.windll.kernel32.VirtualFreeEx(hProc, remote, 0, 0x8000)
        finally:
            ctypes.windll.kernel32.CloseHandle(hProc)

    # ──────────────────────────────────────────
    # CHECKBOXES  — matched by exact window title (GetWindowText)
    # ──────────────────────────────────────────

    def set_checkbox_state(self, checkbox_title, target_state):
        """
        Finds a checkbox by its WIN32 window title (GetWindowText) and
        toggles it to target_state.  No coordinates, no AutomationId property.
        """
        print(f"  Processing checkbox: '{checkbox_title}' → Target: {target_state}")

        win32_title = self._CHECKBOX_TITLE.get(checkbox_title.strip().lower())
        if not win32_title:
            raise Exception(f"No title mapping for checkbox '{checkbox_title}'.")

        pledge_hwnd = self._get_pledge_win_hwnd()
        children    = _get_all_children(pledge_hwnd)

        chk_hwnd = None
        for hwnd, cls, title, rect, vis in children:
            if cls == BUTTON_CLASS and vis and title.strip() == win32_title.strip():
                chk_hwnd = hwnd
                break

        if not chk_hwnd:
            # Partial-match fallback
            for hwnd, cls, title, rect, vis in children:
                if cls == BUTTON_CLASS and vis and win32_title.strip().lower() in title.strip().lower():
                    chk_hwnd = hwnd
                    print(f"    [CHK] Partial match: '{title}'")
                    break

        if not chk_hwnd:
            raise Exception(f"Checkbox '{checkbox_title}' (title='{win32_title}') not found!")

        current = win32api.SendMessage(chk_hwnd, win32con.BM_GETCHECK, 0, 0) == win32con.BST_CHECKED
        if current != target_state:
            _bm_click(chk_hwnd)
            print(f"    Checkbox '{checkbox_title}': CHANGED → {target_state}")
        else:
            print(f"    Checkbox '{checkbox_title}': already {current} — no change.")

    # ──────────────────────────────────────────
    # FETCH BUTTON  — title='Fetch', lower-right area of window
    # ──────────────────────────────────────────

    def click_pledge_fetch_button(self):
        print("Clicking 'Fetch' button...")
        pledge_hwnd = self._get_pledge_win_hwnd()
        children    = _get_all_children(pledge_hwnd)
        pledge_rect = win32gui.GetWindowRect(pledge_hwnd)
        right_half  = pledge_rect[0] + (pledge_rect[2] - pledge_rect[0]) * 0.6

        btn_hwnd = None
        for hwnd, cls, title, rect, vis in children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Fetch" and rect[0] > right_half:
                btn_hwnd = hwnd
                break

        # Fallback: any visible Fetch button
        if not btn_hwnd:
            for hwnd, cls, title, rect, vis in children:
                if cls == BUTTON_CLASS and vis and title.strip() == "Fetch":
                    btn_hwnd = hwnd
                    break

        if not btn_hwnd:
            raise Exception("Fetch button not found!")

        _bm_click(btn_hwnd)
        print("  Fetch button clicked ✓")

    # ──────────────────────────────────────────
    # SAVE BUTTON  — title='Save'
    # ──────────────────────────────────────────

    def click_pledge_save_button(self):
        print("Clicking 'Save' button...")
        pledge_hwnd = self._get_pledge_win_hwnd()
        children    = _get_all_children(pledge_hwnd)

        btn_hwnd = None
        for hwnd, cls, title, rect, vis in children:
            if cls == BUTTON_CLASS and vis and title.strip() == "Save":
                btn_hwnd = hwnd
                break

        if not btn_hwnd:
            raise Exception("Save button not found!")

        _bm_click(btn_hwnd)
        print("  Save button clicked ✓")

    # ──────────────────────────────────────────
    # SLIP PRINTING / CLOSE
    # ──────────────────────────────────────────

    def close_slip_printing_tab(self):
        print("Searching for 'Slip printing' report window...")
        time.sleep(1.0)
        found = []
        def _cb(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd).lower()
                    if "slip" in t or "printing" in t:
                        found.append(hwnd)
            except Exception:
                pass
            return True
        win32gui.EnumWindows(_cb, None)
        if found:
            print(f"  [REPORT] Closing hwnd={found[0]}...")
            win32gui.PostMessage(found[0], win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            print("  [REPORT] Closed ✓")
        else:
            print("  ⚠ Slip printing window not found.")

    def close_window(self):
        print("Closing Pledge Management window...")
        try:
            hwnd = self._get_pledge_win_hwnd()
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(1.0)
            print("  Pledge Management window closed ✓")
        except Exception as e:
            print(f"  ⚠ Close failed: {e}")

    # ══════════════════════════════════════════════
    # MAIN ENTRY POINT  (app.py signature unchanged)
    # ══════════════════════════════════════════════

    def process(self, tab_name, manage_action=None, manage_date=None,
                items_sold_by_client=None, with_epn_blk=None, click_fetch=False):

        if tab_name.strip().lower() == "manage":
            self.click_manage_tab()

            if manage_action is not None:
                self.set_manage_action(manage_action)

            if manage_date is not None:
                self.set_manage_date(manage_date)

            if with_epn_blk is not None:
                self.set_checkbox_state("With EPN-BLK", with_epn_blk)

            if items_sold_by_client is not None:
                self.set_checkbox_state("Items Sold By Client", items_sold_by_client)

            if click_fetch:
                killer = threading.Thread(target=async_popup_killer,
                                          args=(self.main_hwnd,), daemon=True)
                killer.start()
                self.click_pledge_fetch_button()
                time.sleep(10.0)

                print("  [WAIT] Fetch done — waiting 3 s before Save...")
                time.sleep(3.0)

                save_killer = threading.Thread(target=async_popup_killer,
                                               args=(self.main_hwnd,), daemon=True)
                save_killer.start()
                self.click_pledge_save_button()
                time.sleep(3.5)

                self.close_slip_printing_tab()
                time.sleep(1.0)

        print("Pledge Management workflow complete.")
        self.close_window()
        print("PledgePage.process() finished successfully.")