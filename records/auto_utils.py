import os
import cv2
import numpy as np
import pyautogui
import smtplib
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
        fourcc = cv2.VideoWriter_fourcc(*"XVID") # Standard AVI format
        video_path = os.path.join(self.video_dir, filename)
        out = cv2.VideoWriter(video_path, fourcc, fps, screen_size)
        
        last_time = time.time()
        while self._recording:
            # Capture the screen frame by frame
            img = pyautogui.screenshot()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame)
            
            # Control frame rate smoothly
            time_to_wait = (1.0 / fps) - (time.time() - last_time)
            if time_to_wait > 0:
                time.sleep(time_to_wait)
            last_time = time.time()
            
        out.release()

    def start_recording(self):
        """Starts recording the screen in a background thread."""
        if not self._recording:
            self._recording = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"execution_{timestamp}.avi"
            self._video_thread = threading.Thread(target=self._record_loop, args=(filename,))
            self._video_thread.start()
            print(f"🎬 Screen recording started. Saving to {filename}")

    def stop_recording(self):
        """Stops the active background screen recording."""
        if self._recording:
            self._recording = False
            self._video_thread.join()
            print("🛑 Screen recording stopped.")

    # ==========================================
    # FEATURE 2: UNIVERSAL SCREENSHOT
    # ==========================================
    def take_screenshot(self, status="END"):
        """Takes a screenshot of the entire primary screen."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{status}_{timestamp}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        print(f"📸 Screenshot saved: {filepath}")
        return filepath

    # ==========================================
    # FEATURE 3: EMAIL NOTIFICATION
    # ==========================================
    def send_email_notification(self, to_email, success=True, error_message=None, screenshot_path=None):
        """Sends a structured outcome email with BOTH the screenshot and video recording attached."""
        # ─── CONFIGURATION MATRIX ───
        smtp_server = "smtp.gmail.com"
        smtp_port = 587  
        sender_email = "jatingori72@gmail.com"  # Keep your email
        sender_password = "ytwd xepj hldm udte"       # Keep your verified app password
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        
        # ─── SUBJECT & CONTENT CUSTOMIZATION ───
        if success:
            msg['Subject'] = "✅ TradePlusX Run: SUCCESS"
            body = """
            <h3>The automation run completed successfully!</h3>
            <p><strong>Attached files below:</strong></p>
            <ul>
                <li><strong>Image:</strong> Final execution window screenshot</li>
                <li><strong>Video:</strong> Complete step-by-step desktop transaction recording (.avi)</li>
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
                <li><strong>Video:</strong> Recorded operations leading up to the failure event (.avi)</li>
            </ul>
            """
            
        msg.attach(MIMEText(body, 'html'))
        
        # ─── ATTACHMENT GATHERING LOOP ───
        # Automatically collects the screenshot parameter and your active video recording file path
        attachments = []
        
        if screenshot_path and os.path.exists(screenshot_path):
            attachments.append(screenshot_path)
            
        # self.video_filename should hold the path to the running execution .avi file
        if hasattr(self, 'video_filename') and self.video_filename and os.path.exists(self.video_filename):
            attachments.append(self.video_filename)
            
        for path in attachments:
            try:
                filename = os.path.basename(path)
                print(f"📎 Packing attachment context: {filename}...")
                with open(path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={filename}")
                    msg.attach(part)
            except Exception as file_err:
                print(f"⚠️ Warning: Cloud not read/attach file '{path}': {file_err}")
                
        # ─── SMTP EXECUTION ROUTINE ───
        try:
            print(f"📧 Sending execution report bundle to {to_email}...")
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30) # Extended timeout for large video uploads
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
            server.quit()
            print(f"✅ Full report bundle successfully sent to {to_email}!")
        except Exception as e:
            print(f"\n❌ EMAIL ERROR: Transmission dropped out midway: {e}")