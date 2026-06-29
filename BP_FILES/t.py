from pywinauto import Desktop
import time
import sys


def dump_control(control, level=0, file=None):
    try:
        info = control.element_info
        automation_id = getattr(info, 'automation_id', '') or ''
        control_type = getattr(info, 'control_type', '') or ''
        class_name = getattr(info, 'class_name', '') or ''
        name = info.name or ''

        has_id = bool(automation_id.strip())
        marker = " <<<" if has_id else ""

        line = (
            f"{' ' * level}"
            f"[{'★' if has_id else ' '}] "
            f"AutomationId='{automation_id}' | "
            f"Name='{name}' | "
            f"ControlType='{control_type}' | "
            f"ClassName='{class_name}'"
            f"{marker}"
        )

        print(line)
        if file:
            file.write(line + "\n")

        for child in control.children():
            dump_control(child, level + 4, file)

    except Exception as e:
        error_msg = f"{' ' * level}[ERROR] {e}"
        print(error_msg)
        if file:
            file.write(error_msg + "\n")


# Countdown
print("=" * 60)
print("  Open your application now! Scanning in 3 seconds...")
print("=" * 60)
for i in range(3, 0, -1):
    print(f"  {i}...", end="\r")
    time.sleep(1)
print("  Scanning...                    ")

keyword = sys.argv[1] if len(sys.argv) > 1 else None
target = None

for backend in ["uia", "win32"]:
    try:
        for w in Desktop(backend=backend).windows():
            try:
                title = w.window_text()
                if keyword and keyword.lower() in title.lower():
                    target = w
                    print(f"Found: '{title}' [{backend}]")
                    break
            except Exception:
                pass
        if target:
            break
    except Exception:
        pass

if not target:
    print(f"Window with '{keyword}' not found.")
    sys.exit(1)

output_file = "automation_DematContinue.txt"

with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"AUTOMATION ID INSPECTOR\n")
    f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Window: {target.window_text()}\n")
    f.write("★ = Has AutomationId   <<< = Use this!\n")
    f.write("=" * 100 + "\n\n")

try:
    target.restore()
    target.maximize()
    target.set_focus()
    time.sleep(1)
except Exception:
    pass

print(f"Dumping controls for: {target.window_text()}")

with open(output_file, "a", encoding="utf-8") as f:
    dump_control(target, file=f)

print(f"\n✓ Done! Saved to: {output_file}")
print("  Look for [★] and <<< marks for usable AutomationIds.")