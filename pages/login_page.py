import time


class LoginPage:

    def __init__(self, app):
        self.window = app.top_window()

    def login(self, username, password):

        self.window.wait("ready", timeout=30)

        edits = self.window.descendants(control_type="Edit")

        print(f"Found {len(edits)} edit controls")

        # Username
        edits[0].click_input()
        edits[0].set_text(username)

        time.sleep(1)

        # Password
        edits[1].click_input()
        edits[1].set_focus()

        # Clear existing text
        edits[1].type_keys("^a{BACKSPACE}")

        time.sleep(1)

        edits[1].type_keys(
            password,
            with_spaces=True,
            pause=0.05
        )

        print("Password entered. Verify on screen.")
        time.sleep(5)

        print("Clicking Login")

        self.window.child_window(
            title="Login",
            control_type="Button"
        ).click_input()

        time.sleep(3)