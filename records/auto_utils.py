import os
import cv2
import numpy as np
import pyautogui
import smtplib
import ssl  # Added for native SSL support
import threading
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

class AutomationUtils:
    def __init__(self, output_dir="automation_outputs"):
        self.output_dir = output_dir
        self.video_dir = os.path.join(output_dir, "videos")
        self.screenshot_dir = os.path.join(output_dir, "screenshots")
        
        # Ensure directories exist
        os.makedirs(self.video_dir, exist_ok=True)
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        self._recording = False
        self._video_thread = None

    # ==========================================
    # FEATURE 1: UNIVERSAL SCREEN RECORDING
    # ==========================================
    def _record_loop(self, filename, fps=10.0):
        screen_size = tuple(pyautogui.size())
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        video_path = os.path.join(self.video_dir, filename)
        out = cv2.VideoWriter(video_path, fourcc, fps, screen_size)
        
        last_time = time.time()
        while self._recording:
            img = pyautogui.screenshot()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame)
            
            time_to_wait = (1.0 / fps) - (time.time() - last_time)
            if time_to_wait > 0:
                time.sleep(time_to_wait)
            last_time = time.time()
            
        out.release()

    def start_recording(self):
        if not self._recording:
            self._recording = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"execution_{timestamp}.avi"
            self.video_filename = os.path.join(self.video_dir, filename) # Tracking target explicitly
            self._video_thread = threading.Thread(target=self._record_loop, args=(filename,))
            self._video_thread.start()
            print(f"🎬 Screen recording started. Saving to {filename}")

    def stop_recording(self):
        if self._recording:
            self._recording = False
            self._video_thread.join()
            print("🛑 Screen recording stopped.")

    # ==========================================
    # FEATURE 2: UNIVERSAL SCREENSHOT
    # ==========================================
    def take_screenshot(self, status="END"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{status}_{timestamp}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        print(f"📸 Screenshot saved: {filepath}")
        return filepath

    # ==========================================
    # FEATURE 3: DYNAMIC CONFIGURABLE EMAIL
    # ==========================================
    def send_email_notification(self, mail_config, success=True, error_message=None, screenshot_path=None):
        """Sends a structured outcome email parsing parameters out of dynamic execution JSON mapping blocks."""
        
        # ─── EXTRACTION MATRIX ───
        sender_email  = mail_config.get("From Email", "").strip()
        smtp_server   = mail_config.get("IPAddress", "").strip()
        smtp_port     = int(mail_config.get("Port", 587))
        smtp_user     = mail_config.get("User", "").strip()
        smtp_password = mail_config.get("Password", "").replace(" ", "")
        is_ssl        = str(mail_config.get("SSL", "N")).strip().upper() == "Y"
        
        # Parse multiple recipients using the requested '/' delimiter string structures
        cc_raw        = mail_config.get("CCEmail", "")
        bcc_raw       = mail_config.get("BCCEmail", "")
        
        cc_list       = [email.strip() for email in cc_raw.split("/") if email.strip()] if cc_raw else []
        bcc_list      = [email.strip() for email in bcc_raw.split("/") if email.strip()] if bcc_raw else []
        
        # Main recipient fallback to self user if empty
        primary_to    = smtp_user if smtp_user else sender_email

        if not smtp_server or not smtp_user or not smtp_password:
            print("❌ EMAIL ERROR: Essential SMTP connection configuration keys are missing inside JSON profiles.")
            return

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = primary_to
        
        if cc_list:
            msg['Cc'] = ", ".join(cc_list)
            
        # Collect all distribution destinations for the envelope sender routing call
        all_recipients = [primary_to] + cc_list + bcc_list
        
        # ─── SUBJECT & CONTENT CUSTOMIZATION ───
        if success:
            msg['Subject'] = "✅ TradePlusX Run: SUCCESS"
            body = """
            <h3>The automation run completed successfully!</h3>
            <p><strong>Attached files below:</strong></p>
            <ul>
                <li><strong>Image:</strong> Final execution window screenshot</li>
            </ul>
            """
        else:
            msg['Subject'] = "❌ TradePlusX Run: FAILED"
            body = f"""
            <h3>The automation run encountered an error.</h3>
            <p><strong>Error Detail:</strong> <span style="color:red;">{error_message}</span></p>
            <p><strong>Attached files below for debugging:</strong></p>
            <ul>
                <li><strong>Image:</strong> Crash point screen context capture</li>
            </ul>
            """
            
        msg.attach(MIMEText(body, 'html'))
        
        # ─── ATTACHMENT GATHERING (SCREENSHOT ONLY) ───
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                filename = os.path.basename(screenshot_path)
                print(f"📎 Packing attachment context: {filename}...")
                with open(screenshot_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={filename}")
                    msg.attach(part)
            except Exception as file_err:
                print(f"⚠️ Warning: Could not read/attach screenshot file '{screenshot_path}': {file_err}")
                
        # ─── SMTP CONNECTION ENGINE ───
        try:
            print(f"📧 Connecting to SMTP Server {smtp_server}:{smtp_port}...")
            
            if is_ssl:
                # SSL Direct Layer Connection (Port 465 style)
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=45)
            else:
                # Standard Connection with opportunistic TLS (Port 587 style)
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=45)
                server.ehlo()
                server.starttls()
                server.ehlo()
                
            server.login(smtp_user, smtp_password)
            print(f"📧 Transmitting report package to target recipients...")
            server.sendmail(sender_email, all_recipients, msg.as_string())
            server.quit()
            print(f"✅ Full report bundle successfully routed via customizable parameters!")
        except Exception as e:
            print(f"\n❌ EMAIL ERROR: Connection or routing dropped out: {e}")