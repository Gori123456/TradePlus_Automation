import os
import sys
import json

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def execute_project_pipeline(allowed_menus=None, execute_all=True):
    action_path = os.path.join(os.path.dirname(__file__), "Action.json")
    action_data = load_json(action_path)
    
    # Filter tasks based on what the Boss requested
    if not execute_all and allowed_menus:
        print(f"📋 Employee filtering tasks. Allowed: {allowed_menus}")
        for pipeline in action_data.get("execution_pipeline", []):
            for sub in pipeline.get("sub_pipeline", []):
                if sub.get("Menu") not in allowed_menus:
                    sub["enabled"] = False  # Mask out unauthorized tasks

    # -------------------------------------------------------------
    # Your original page execution orchestrator goes here
    # (e.g., from control_center_page import ControlCenterPage...)
    # -------------------------------------------------------------
    print("🤖 Executing active project pages...")
    # Example simulation:
    # page = ControlCenterPage(app)
    # page.process(...)
    
    print("🏁 Project execution sub-pipeline loop completed.")

if __name__ == "__main__":
    # Receive scope arguments forwarded by the master orchestrator
    args = sys.argv[1:]
    if "--all" in args:
        execute_project_pipeline(execute_all=True)
    else:
        # Extract specific tasks sent by the Boss
        tasks = [a for a in args if not a.startswith("--")]
        execute_project_pipeline(allowed_menus=tasks, execute_all=False)