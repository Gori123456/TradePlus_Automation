"""
Run this while TradePlus is open.
It will list ALL running processes so we can find the exact name.
"""
import psutil

print("\n=== ALL RUNNING PROCESSES ===\n")
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    try:
        name = proc.info['name'] or ''
        exe  = proc.info['exe'] or ''
        pid  = proc.info['pid']
        # Show anything that looks like it could be TradePlus or a .NET/WinForms app
        if any(k in name.lower() for k in ['trade', 'plus', 'tplus', 'tpx', 'demat']):
            print(f"  *** MATCH ***  PID={pid}  Name={name}  Path={exe}")
    except:
        continue

print("\n=== ALL .EXE PROCESSES (for manual search) ===\n")
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    try:
        name = proc.info['name'] or ''
        if name.endswith('.exe') or name.endswith('.EXE'):
            print(f"  PID={proc.info['pid']:6d}  Name={name}")
    except:
        continue

input("\nPress Enter to exit...")