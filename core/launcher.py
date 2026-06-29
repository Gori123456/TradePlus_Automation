from pywinauto import Application


def start_application(app_path):
    app = Application(backend="uia").start(app_path)
    
    return app