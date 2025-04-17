#!/usr/bin/python3
# -*- coding: utf-8 -*-

# file: pyxkeyboard.py (to be installed as /usr/bin/pyxkeyboard)
# PyXKeyboard v1.0.5 - Launcher Script
# This script ensures the package is in the Python path and runs the main function.
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

import sys
import os
import site
import locale

# --- إعداد المجال للترجمة (إذا كنت ستستخدمها لاحقًا) ---
# locale.bindtextdomain('pyxkeyboard', '/usr/share/locale') # Example path
# locale.textdomain('pyxkeyboard')
# _ = locale.gettext

# --- إضافة مسارات التثبيت القياسية إلى مسار بايثون ---
# هذا مهم لضمان العثور على الوحدة pyxkeyboard بعد التثبيت.

# دالة لإضافة مسار إذا كان موجودًا ولم يكن مضافًا بالفعل
def add_to_sys_path(path_to_add):
    if os.path.isdir(path_to_add) and path_to_add not in sys.path:
        # site.addsitedir(path_to_add) # طريقة أخرى قد تكون أفضل أحيانًا
        sys.path.insert(0, path_to_add)
        # print(f"Debug: Added to sys.path: {path_to_add}") # للتشخيص فقط

# مسارات شائعة لحزم النظام (قد تحتاج لتعديل حسب التوزيعة)
common_paths = [
    "/usr/lib/python3/dist-packages",
    "/usr/lib64/python3/site-packages", # شائع في أنظمة RPM 64-bit
    "/usr/lib/python3/site-packages",
]

# إضافة المسارات الشائعة
for path in common_paths:
    add_to_sys_path(path)

# محاولة إضافة مسار site-packages الخاص بإصدار بايثون الحالي
try:
    # الحصول على مسار site-packages القياسي لهذا الإصدار
    # قد يختلف هذا قليلاً بين التوزيعات
    py_version_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    site_packages_path = f"/usr/lib/python{py_version_major_minor}/site-packages"
    add_to_sys_path(site_packages_path)
    # قد تحتاج أيضًا للتحقق من /usr/local/lib/...
    local_site_packages_path = f"/usr/local/lib/python{py_version_major_minor}/dist-packages" # لـ Debian/Ubuntu
    add_to_sys_path(local_site_packages_path)
    local_site_packages_path_rpm = f"/usr/local/lib/python{py_version_major_minor}/site-packages" # لـ RPM
    add_to_sys_path(local_site_packages_path_rpm)

except Exception as e:
    print(f"Warning: Could not dynamically add specific site-packages path: {e}", file=sys.stderr)


# --- محاولة تشغيل من شجرة المصدر (للتطوير/الاختبار) ---
# هذا الجزء مشابه للملف المرفق ويتيح تشغيل السكربت مباشرة من مجلد المشروع
try:
    PROJECT_ROOT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
    # نفترض أن هذا الملف سيكون في /usr/bin، لذا نحتاج للبحث عن الوحدة
    # في مسارات site-packages التي أضفناها أعلاه.

    # إذا فشل الاستيراد أدناه، قد يعني أن الحزمة غير مثبتة بشكل صحيح
    # أو أننا بحاجة لتعديل المسارات أعلاه لتطابق نظام التثبيت.

except Exception as e:
     print(f"Error determining project root: {e}", file=sys.stderr)
     # لا يمكن المتابعة بدون مسار صحيح أو وحدة مثبتة
     # sys.exit(1) # يمكنك الخروج هنا إذا أردت

# --- استيراد وتشغيل الوحدة الرئيسية ---
try:
    # الآن يجب أن يكون pyxkeyboard متاحًا في sys.path
    from pyxkeyboard import main as pyx_main # استيراد الدالة main من الوحدة
    # print("Debug: Successfully imported pyxkeyboard.main") # للتشخيص
    # تشغيل الدالة الرئيسية للتطبيق
    pyx_main.main()
except ImportError:
    print("FATAL ERROR: Could not import the 'pyxkeyboard' module.", file=sys.stderr)
    print("Ensure the package is installed correctly in one of the Python paths:", file=sys.stderr)
    print("\n".join(sys.path), file=sys.stderr)
    sys.exit(1)
except AttributeError:
     print("FATAL ERROR: Could not find the 'main' function within the 'pyxkeyboard.main' module.", file=sys.stderr)
     sys.exit(1)
except Exception as e:
    print(f"FATAL ERROR: An unexpected error occurred during execution: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# file: pyxkeyboard_launcher.py
