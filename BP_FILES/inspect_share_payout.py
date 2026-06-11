"""
Run this script WHILE the Control Center window is open on your screen.
Uses pure win32 handle-based scanning to dump all child controls.
"""
import time
import sys
import os
import win32gui
import win32con

# Updated to generate a dedicated layout configuration report file
output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demat_control_output.txt")

class Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()
    def flush(self):
        for s in self.streams: 
            s.flush()

f = open(output_file, "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, f)

print(f"Saving layout log to: {output_file}")
print("Waiting 3 seconds — keep the Control Center window open and on top...")
time.sleep(3)

# ── Step 1: Find TradePlusX main window ──
TRADEPLUS_CLASS = "WindowsForms10.Window.8.app.0.141b42a_r7_ad1"
main_hwnd = win32gui.FindWindow(TRADEPLUS_CLASS, "TradePlusX")
if not main_hwnd:
    print("ERROR: TradePlusX main window not found!")
    f.close()
    sys.stdout = sys.__stdout__
    input("Press Enter to exit...")
    exit()
print(f"✓ TradePlusX main window handle: {main_hwnd}")

# ── Step 2: Walk ALL child windows recursively ──
all_windows = []

def enum_child(hwnd, lparam):
    try:
        title      = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        rect       = win32gui.GetWindowRect(hwnd)
        visible    = win32gui.IsWindowVisible(hwnd)
        all_windows.append((hwnd, class_name, title, rect, visible))
    except:
        pass
    return True

win32gui.EnumChildWindows(main_hwnd, enum_child, None)
print(f"✓ Total child controls found inside application frame: {len(all_windows)}\n")

print("=" * 100)
print(f"{'HANDLE':<12} {'VISIBLE':<8} {'CLASS':<55} {'TITLE':<40} RECT")
print("=" * 100)
for hwnd, cname, title, rect, visible in all_windows:
    v = "YES" if visible else "no"
    print(f"{hwnd:<12} {v:<8} {cname:<55} {title:<40} {rect}")

# ── Step 3: Find the Control Center dialog specifically ──
print("\n" + "=" * 100)
print("SEARCHING FOR CONTROL CENTER WINDOW FRAME")
print("=" * 100)
cc_hwnd = None
for hwnd, cname, title, rect, visible in all_windows:
    t_low = title.lower()
    if "control" in t_low and "center" in t_low:
        if "window" in cname.lower() or "sys" in cname.lower() or rect[2] - rect[0] > 400:
            print(f"\n*** FOUND CONTROL CENTER INTERFACE: handle={hwnd} | class='{cname}' | title='{title}' | rect={rect}")
            cc_hwnd = hwnd
            break

if not cc_hwnd:
    print("Control Center window not found in nested application children. Trying desktop window tree lookup...")
    def enum_all(hwnd, lparam):
        global cc_hwnd
        try:
            title = win32gui.GetWindowText(hwnd)
            t_low = title.lower()
            if "control" in t_low and "center" in t_low:
                cname = win32gui.GetClassName(hwnd)
                rect  = win32gui.GetWindowRect(hwnd)
                print(f"  Found via desktop-wide surface scan: handle={hwnd} | class='{cname}' | title='{title}' | rect={rect}")
                cc_hwnd = hwnd
        except: 
            pass
        return True
    win32gui.EnumWindows(enum_all, None)

# ── Step 4: Dump target window child sub-components ──
if cc_hwnd:
    print(f"\n" + "=" * 100)
    print(f"ALL CHILDREN of Control Center window (handle={cc_hwnd})")
    print("=" * 100)

    cc_children = []
    def enum_cc_child(hwnd, lparam):
        try:
            title      = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            rect       = win32gui.GetWindowRect(hwnd)
            visible    = win32gui.IsWindowVisible(hwnd)
            cc_children.append((hwnd, class_name, title, rect, visible))
        except:
            pass
        return True
    win32gui.EnumChildWindows(cc_hwnd, enum_cc_child, None)

    print(f"{'HANDLE':<12} {'VISIBLE':<8} {'CLASS':<55} {'TITLE':<40} RECT")
    print("-" * 100)
    for hwnd, cname, title, rect, visible in cc_children:
        v = "YES" if visible else "no"
        print(f"{hwnd:<12} {v:<8} {cname:<55} {title:<40} {rect}")

    # ── Step 5: Segment elements by Control Classes ──
    print(f"\n" + "=" * 100)
    print("KEY CONTROLS SUMMARY (CONTROL CENTER)")
    print("=" * 100)

    print("\n--- ACTION BUTTONS & CHECKBOXES (BSE, NSE, Cash, F&O, Go, etc.) ---")
    for hwnd, cname, title, rect, visible in cc_children:
        if "button" in cname.lower():
            print(f"  handle={hwnd} | class='{cname}' | title='{title}' | visible={visible} | rect={rect}")

    print("\n--- COMBOBOXES / SELECTION DROPDOWNS (Product, Type) ---")
    for hwnd, cname, title, rect, visible in cc_children:
        if "combobox" in cname.lower() or "combo" in cname.lower():
            print(f"  handle={hwnd} | class='{cname}' | title='{title}' | visible={visible} | rect={rect}")

    print("\n--- DATE SELECTION, INPUT PATHS & EDIT FIELDS ---")
    for hwnd, cname, title, rect, visible in cc_children:
        c_low = cname.lower()
        if "edit" in c_low or "datetime" in c_low or "sysdate" in c_low:
            print(f"  handle={hwnd} | class='{cname}' | title='{title}' | visible={visible} | rect={rect}")
            
    print("\n--- DATA VIEW GRIDS & TABLES (File Import Success Matrix) ---")
    for hwnd, cname, title, rect, visible in cc_children:
        c_low = cname.lower()
        # Enhanced to catch pure generic window nodes that WinForms relies on for its embedded tables
        if "grid" in c_low or "view" in c_low or "list" in c_low or "window" in c_low:
            # Filters for the size profile matching the layout grid shown on your screenshot
            if rect[2] - rect[0] > 300 and rect[3] - rect[1] > 200:
                print(f"  [TARGET DATA TABLE FOUND] handle={hwnd} | class='{cname}' | title='{title}' | visible={visible} | rect={rect}")

else:
    print("\nCRITICAL: Could not locate window matching Control Center layout descriptors.")

print(f"\n✓ Analysis completed successfully. Output saved to: {output_file}")
f.close()
sys.stdout = sys.__stdout__
input("\nPress Enter to close window mapping tool...")