#!/bin/bash
# أو يمكنك استخدام #!/usr/bin/env python3 إذا أردت تشغيل الوحدة مباشرة

# تشغيل وحدة بايثون الرئيسية. تأكد من أن اسم الوحدة صحيح.
# يفترض أن الكود مثبت في python path وأن main.py داخل مجلد pyxkeyboard
python3 -m pyxkeyboard.main "$@"

# بديل إذا كنت تفضل استدعاء ملف main.py مباشرة (يتطلب معرفة المسار الكامل):
# python3 /usr/lib/python3/dist-packages/pyxkeyboard/main.py "$@"

exit $?
