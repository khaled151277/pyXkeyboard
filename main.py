# -*- coding: utf-8 -*-
# file:main.py
# PyXKeyboard v1.0.7 - A simple, customizable on-screen virtual keyboard.
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.
# Main entry point for the Python XKeyboard application.

import sys
import os
import traceback

# --- استيراد PyQt6 أولاً للتحقق منه ---
try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket # <<<--- إضافة الاستيرادات الجديدة
    from PyQt6.QtCore import QIODevice # <<<--- إضافة QIODevice
except ImportError:
    print("FATAL ERROR: PyQt6 library (including QtNetwork) is required to run the application.")
    print("Please install it: pip install PyQt6")
    sys.exit(1)

# --- استيراد مكونات التطبيق باستخدام الاستيراد النسبي ---
try:
    from .virtual_keyboard_gui import VirtualKeyboard
    from .settings_manager import SETTINGS_DIR 
except ImportError as e:
    print(f"FATAL ERROR: Could not import application components: {e}")
    try:
        err_app = QApplication([])
        QMessageBox.critical(None, "Import Error",
                             f"Failed to import required application modules:\n\n{e}\n\n"
                             "Ensure all .py files are part of the installed 'pyxkeyboard' package.")
    except Exception as msg_e:
        print(f"Could not display import error message box: {msg_e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FATAL ERROR: Unexpected error during imports: {e}")
    traceback.print_exc()
    sys.exit(1)

# اسم فريد للخادم المحلي - يجب أن يكون فريدًا للتطبيق
APP_GUID = "PyXKeyboard_Khaled1512_AppGuid_v1" # اجعله فريدًا جدًا

# --- الدالة الرئيسية التي تحتوي على منطق التطبيق ---
def main():
    print("Starting Python XKeyboard Application...")
    print(f"Using settings directory: {SETTINGS_DIR}")

    if os.environ.get("WAYLAND_DISPLAY"):
         print("--- WARNING: Wayland Detected ---")
         print("   XTEST/XKB features might be unreliable or non-functional.")
         print("---")
    if not os.environ.get("DISPLAY"):
         print("--- WARNING: DISPLAY environment variable not set. X features may fail. ---")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # مهم ليبقى الخادم يعمل

    # --- منطق النسخة الواحدة ---
    socket = QLocalSocket()
    # محاولة الاتصال بالخادم الموجود
    socket.connectToServer(APP_GUID)

    if socket.waitForConnected(500): # انتظر 500 ملي ثانية للاتصال
        print("Another instance is already running. Sending activation message.")
        # أرسل رسالة لتنشيط النافذة الموجودة
        socket.write(b"activate_window\n") # \n قد يساعد في بعض الأنظمة
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        sys.exit(0) # اخرج من هذه النسخة لأن نسخة أخرى نشطة
    else:
        # لم يتم الاتصال بالخادم، هذا يعني أن هذه هي النسخة الأولى أو الوحيدة
        # أو أن الخادم لم يستجب بسرعة كافية (حالة نادرة)
        # قم بإزالة أي خادم قديم قد يكون عالقًا (إذا فشل في الإزالة سابقًا)
        QLocalServer.removeServer(APP_GUID)
        
        server = QLocalServer()
        # ابدأ الاستماع
        if not server.listen(APP_GUID):
            # إذا فشل الاستماع، قد يكون هناك مشكلة أو تعارض آخر
            QMessageBox.critical(None, "Error",
                                 f"Could not start local server: {server.errorString()}. "
                                 "Another instance might be running or there's a permission issue.")
            sys.exit(1)
        print(f"Local server started successfully. Listening on '{APP_GUID}'. This is the primary instance.")
    # --- نهاية منطق النسخة الواحدة ---


    keyboard_window = None
    try:
        print("Initializing main window...")
        keyboard_window = VirtualKeyboard()
        print("Showing main window...")
        keyboard_window.show()
        print("Main window shown.")

        # --- ربط إشارة newConnection من الخادم ---
        # يجب أن تكون keyboard_window متاحة عند تلقي الاتصال
        def handle_new_connection():
            print("New connection received on local server.")
            client_connection = server.nextPendingConnection()
            if client_connection:
                # انتظر حتى تصبح البيانات جاهزة للقراءة
                if client_connection.waitForReadyRead(500): # انتظر 500 ملي ثانية
                    request = client_connection.readLine().data().decode().strip()
                    print(f"Received command: {request}")
                    if request == "activate_window":
                        if keyboard_window:
                            keyboard_window.activate_and_show() # دالة جديدة في VirtualKeyboard
                else:
                    print("No data received from client or timeout.")
                client_connection.disconnectFromServer()
                client_connection.deleteLater() # تأكد من حذف الاتصال

        server.newConnection.connect(handle_new_connection)
        # --- نهاية ربط الإشارة ---

    except Exception as e:
        print(f"FATAL ERROR during application initialization: {e}")
        traceback.print_exc()
        QMessageBox.critical(None, "Initialization Error",
                             f"Failed to initialize or show the virtual keyboard:\n\n{e}\n\n"
                             "Check console output for details.")
        if server and server.isListening(): # تأكد من إغلاق الخادم عند الخروج بسبب خطأ
            server.close()
            QLocalServer.removeServer(APP_GUID)
        sys.exit(1) 

    exit_code = app.exec()
    print(f"Application finished with exit code {exit_code}.")

    # --- تأكد من إغلاق الخادم وإزالة الملف عند الخروج الطبيعي ---
    if server and server.isListening():
        server.close()
        QLocalServer.removeServer(APP_GUID) # مهم لإزالة ملف socket
        print(f"Local server '{APP_GUID}' closed and removed.")
    # --- نهاية إغلاق الخادم ---

    sys.exit(exit_code)

if __name__ == "__main__":
    main()