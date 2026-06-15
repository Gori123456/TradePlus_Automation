"""
Run this script WHILE the process window is open on your screen.
Dynamically handles both 'Share Pay-in / Pay-out Processes' and 'Control Center' titles.
"""
import time
import sys
import os
import win32gui
import win32con

# Layout configuration output path
output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SharePayInOut_RedCircle_Output.txt")

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
print("Waiting 3 seconds — keep the Share Pay-in / Pay-out Processes window visible...")
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

# ── Step 3: Find the targeting window sub-frame dynamically ──
print("\n" + "=" * 100)
print("SEARCHING FOR TARGET PROCESS WINDOW FRAME")
print("=" * 100)
target_hwnd = None

# Checks both possible titles seen across your execution steps
VALID_TITLES = ["share pay-in", "pay-out processes", "control center"]

for hwnd, cname, title, rect, visible in all_windows:
    t_low = title.lower()
    if any(vt in t_low for vt in VALID_TITLES):
        print(f"\n*** FOUND TARGET INTERFACE: handle={hwnd} | class='{cname}' | title='{title}' | rect={rect}")
        target_hwnd = hwnd
        break

if not target_hwnd:
    print("Target sub-window not found inside application tree. Attempting global desktop scan...")
    def enum_all(hwnd, lparam):
        global target_hwnd
        try:
            title = win32gui.GetWindowText(hwnd)
            t_low = title.lower()
            if any(vt in t_low for vt in VALID_TITLES):
                cname = win32gui.GetClassName(hwnd)
                rect  = win32gui.GetWindowRect(hwnd)
                print(f"  Found via desktop scan: handle={hwnd} | class='{cname}' | title='{title}' | rect={rect}")
                target_hwnd = hwnd
        except: 
            pass
        return True
    win32gui.EnumWindows(enum_all, None)

# ── Step 4: Dump and filter window sub-components ──
if target_hwnd:
    print(f"\n" + "=" * 100)
    print(f"ALL CHILDREN of Target Process Window (handle={target_hwnd})")
    print("=" * 100)

    target_children = []
    def enum_target_child(hwnd, lparam):
        try:
            title      = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            rect       = win32gui.GetWindowRect(hwnd)
            visible    = win32gui.IsWindowVisible(hwnd)
            target_children.append((hwnd, class_name, title, rect, visible))
        except:
            pass
        return True
    win32gui.EnumChildWindows(target_hwnd, enum_target_child, None)

    print(f"{'HANDLE':<12} {'VISIBLE':<8} {'CLASS':<55} {'TITLE':<40} RECT")
    print("-" * 100)
    for hwnd, cname, title, rect, visible in target_children:
        v = "YES" if visible else "no"
        print(f"{hwnd:<12} {v:<8} {cname:<55} {title:<40} {rect}")

    # ── Step 5: HIGHEST PRIORITY - Find the Red Circle Control (Process Log Window) ──
    print(f"\n" + "=" * 100)
    print("PRIORITY TARGET: PROCESS LOG CONSOLE (RED CIRCLE AREA)")
    print("=" * 100)
    
    t_left, t_top, t_right, t_bottom = win32gui.GetWindowRect(target_hwnd)
    t_width = t_right - t_left
    
    found_log_box = False
    for hwnd, cname, title, rect, visible in target_children:
        c_low = cname.lower()
        r_left, r_top, r_right, r_bottom = rect
        w = r_right - r_left
        h = r_bottom - r_top
        
        # Geolocation criteria: Must sit heavily on the right side of the inner layout panel
        is_right_side = r_left > (t_left + (t_width * 0.58))
        
        # Expanded target text signatures matching your new screenshot
        LOG_SIGNATURES = [
            "Process Started", 
            ">>Process", 
            "Trades not found", 
            "Process Completed", 
            "Settlement"
        ]
        contains_log_text = any(sig in title for sig in LOG_SIGNATURES)
        
        # Look for the control container matching position bounds or text elements
        if (contains_log_text) or (is_right_side and w > 100 and h > 120 and ("list" in c_low or "edit" in c_low or "window" in c_low)):
            print(f"🌟 MATCH FOUND FOR RED CIRCLE CONTROL:")
            print(f"   Handle: {hwnd}")
            print(f"   Class Name: {cname}")
            print(f"   Current Text/Title: '{title}'")
            print(f"   Dimensions: Width={w}, Height={h} | Rect={rect}\n")
            found_log_box = True

    if not found_log_box:
        print("  Could not definitively isolate the log box. Review the structural layout dump saved above.")

else:
    print(f"\nCRITICAL: Could not locate window matching titles: {VALID_TITLES}")

print(f"\n✓ Analysis completed successfully. Output saved to: {output_file}")
f.close()
sys.stdout = sys.__stdout__
input("\nPress Enter to close window mapping tool...")