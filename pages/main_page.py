import time
from pywinauto.keyboard import send_keys


class MainPage:

    def __init__(self, app):
        self.app = app
        self.window = app.top_window()

    def click_submenu_by_index(self, parent_menu, index, submenu_name=""):

        label = submenu_name if submenu_name else f"item {index}"
        print(f"Opening Menu: {parent_menu} → {label} (index {index})")

        # Open the parent menu (e.g. Utilities)
        self.window.menu_select(parent_menu)
        time.sleep(1)

        # Navigate DOWN to the required index (1-based: index 1 = first item, no DOWN needed)
        for _ in range(index - 1):
            send_keys("{DOWN}")
            time.sleep(0.2)

        # Press ENTER to open selected item
        send_keys("{ENTER}")

        print(f"Opened: {parent_menu} → {label}")
        time.sleep(2)