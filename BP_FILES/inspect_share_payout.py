import os
import sys
import time
from pywinauto import Application

# Define path for layout logs
output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TradePlusX_Complete_Screen_Map.txt")

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

print("Connecting to TradePlusX via Win32 Engine...")
try:
    # 1. Connect to the application frame
    app = Application(backend="win32").connect(title="TradePlusX", timeout=5)
    main_win = app.window(title="TradePlusX")
    main_win.set_focus()
    
    print("\n" + "="*80)
    print("MAPPING SYSTEM CONTROL BARS")
    print("="*80)

    # 2. Bind the Top Menu Strip (Masters, Transactions, Reports, etc.)
    # Using window specification matching based on your log data
    menu_strip = main_win.child_window(class_name_re=".*MenuStrip.*")
    print(f"✓ MenuStrip Wrapper Detected: {menu_strip}")
    
    # 3. Bind the Metadata Banner Strip (Year, Company, Segment)
    tool_strip = main_win.child_window(class_name_re=".*ToolStrip.*")
    print(f"✓ ToolStrip Wrapper Detected: {tool_strip}")
    
    # Extract existing configurations directly from the components
    company_box = main_win.child_window(title="NARIMAN FINVEST PVT LTD", class_name_re=".*Combo.*")
    year_box = main_win.child_window(title="2026-2027", class_name_re=".*Combo.*")
    
    print(f"  ↳ Current Accounting Year Element: {year_box}")
    print(f"  ↳ Current Selected Company Element: {company_box}")

    print("\n" + "="*80)
    print("DEEP SCANNING MDI CLIENT (INTERNAL ACTIVE WINDOWS)")
    print("="*80)

    # 4. Target the MDI Client container holding the active working screens
    mdi_client = main_win.child_window(class_name_re=".*MDIClient.*")
    
    # Fetch all internal child windows currently active inside the application space
    active_sub_windows = mdi_client.children()
    print(f"Found {len(active_sub_windows)} active workspace layers inside the MDI view.\n")
    
    if len(active_sub_windows) == 0:
        print("💡 [INFO]: The central dashboard workspace area is empty.")
        print("   To extract target logs, open a process screen (e.g., Share Pay-in/Pay-out)")
        print("   and run this tracking script while that process screen is open.")
    else:
        print(f"{'SUB-WINDOW CLASS':<45} {'WINDOW TEXT / TITLE':<35}")
        print("-" * 80)
        for i, sub_win in enumerate(active_sub_windows):
            title = sub_win.window_text() or "[Untitled / Transparent Container]"
            cls_name = sub_win.class_name()
            print(f"{cls_name:<45} {title:<35}")
            
            # Extract controls inside this specific active functional view layout
            sub_children = sub_win.children()
            if sub_children:
                print(f"  ↳ Detected {len(sub_children)} interactive controls inside this view workspace:")
                for sc in sub_children:
                    if sc.window_text():
                        print(f"    - Control Class: '{sc.class_name()}' | Text Label: '{sc.window_text()}'")

except Exception as e:
    print(f"\nCRITICAL ERROR mapping the layout components: {str(e)}")
    print("Verify the application isn't minimized during the runtime capture loop.")

finally:
    print(f"\n✓ Completed deep window trace sequence. Log saved to: {output_file}")
    f.close()
    sys.stdout = sys.__stdout__
    input("\nPress Enter to exit...")