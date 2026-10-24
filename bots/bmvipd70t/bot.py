import os, re, json, time, html, base64, asyncio, logging, random
import urllib.request, urllib.error
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from telegram import (Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup,
                      LinkPreviewOptions)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters)

TOKEN = os.environ["BOT_TOKEN"]
API_ID = os.environ.get("API_ID")      # من my.telegram.org (لحظر أي يوزر)
API_HASH = os.environ.get("API_HASH")
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import User as TLUser
except ImportError:
    TelegramClient = None
TL = None
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("guard")

# =====================================================================
#  القيم الافتراضية لأي مجموعة جديدة (كل شيء قابل للتغيير لاحقًا بالأوامر)
# =====================================================================
DEFAULTS = {
    "lang": "ar",
    "links": True, "promo": True, "spam": True, "words": True,
    "leaveban": True, "welcome": True, "bye": True, "service": True,
    "max_warns": 3,
    "flood_n": 6, "flood_s": 8, "spam_mute": 10,
    "welcome_text": "", "bye_text": "", "rules": "",
    "word_mute": 60,    # مدة الكتم الافتراضية للكلمة المضافة بلا مدة
    "ttl": 0,           # حذف ردود البوت تلقائيًا بعد (ثانية)، 0 = لا تُحذف (يُفعَّل بـ /setautodel)
    "periodic": None,   # الرسالة الدورية
    "welcome_btns": [], "bye_btns": [], "periodic_btns": [],   # أزرار الروابط
    "cheer": True, "cheer_i": 0, "chat_link": "",              # التشجيع على منشورات القناة
    "welcome_media": None, "bye_media": None,
    "banned": {},   # كلمة -> مدة الكتم بالدقائق (0 = حذف وتحذير فقط)
    "allow": [],    # نطاقات روابط مسموحة
    "captcha": False, "captcha_time": 120,        # التحقق بزر عند الانضمام
    "warn_action": "ban", "warn_dur": 1440,       # الإجراء عند بلوغ الحد الأقصى للتحذيرات
}
CREDIT = "🤖 Bot by @Incert_us"   # حقوق البوت
LANGS = {"ar": "🇸🇦 العربية", "en": "🇬🇧 English", "fr": "🇫🇷 Français", "tr": "🇹🇷 Türkçe"}
TOG = ["links", "promo", "spam", "words", "leaveban", "welcome", "bye", "service", "cheer", "captcha"]

# =====================================================================
#  رسائل التشجيع على منشورات القناة (تُرسَل بالترتيب، وعند انتهائها تبدأ من الأولى)
# =====================================================================
_OPEN = [
    "🔥 منشور جديد وصل!", "✨ ما شاء الله على هذا المنشور!", "👏 عمل رائع كالعادة!",
    "🌟 منشور يستحق الاهتمام!", "💎 محتوى مميز بين أيديكم!", "🚀 جديد القناة وصل، تابعوه!",
    "🎯 منشور جديد، لا يفوّتكم!", "💫 إبداع جديد من القناة!", "🌹 تسلم الأيادي على هذا المنشور!",
    "👑 منشور بمستوى مختلف!", "😍 يا له من منشور!", "🙌 بارك الله فيك على هذا الجهد!",
    "⚡ وصل الجديد، تابعوه!", "💥 منشور جديد ومميز!", "🏆 دائمًا في القمة!",
    "🌈 منشور جميل يستحق المتابعة!",
]
_JOIN = [
    "💬 ادخلوا مجموعة الدردشة وشاركونا رأيكم!", "🤝 انضموا لمجموعة الدردشة ولا تبقوا خارج النقاش!",
    "👥 مجموعة الدردشة بانتظاركم، ادخلوا وتفاعلوا!", "🗨️ النقاش الحقيقي في مجموعة الدردشة، تعالوا شاركونا!",
    "🎉 ادخلوا مجموعة الدردشة وكونوا جزءًا من العائلة!", "💌 شاركونا رأيكم بالدخول إلى مجموعة الدردشة!",
    "🔔 لا تفوّتوا النقاش، انضموا لمجموعة الدردشة الآن!", "🌟 مجموعة الدردشة مفتوحة لكم، ادخلوا وتحدثوا معنا!",
    "✍️ رأيكم يهمنا! ادخلوا مجموعة الدردشة وعلّقوا!", "🫶 تعالوا إلى مجموعة الدردشة، أصدقاء لطفاء بانتظاركم!",
    "🚪 باب مجموعة الدردشة مفتوح، ادخلوا الآن!", "🔥 التفاعل الحقيقي يبدأ من مجموعة الدردشة، انضموا إلينا!",
    "😉 هيا إلى مجموعة الدردشة، نحن بانتظاركم!", "🎈 ادخلوا مجموعة الدردشة وشاركونا أجواءها الجميلة!",
    "📢 للمشاركة والنقاش، ادخلوا مجموعة الدردشة!", "🧡 انضموا لمجموعة الدردشة وكونوا معنا دائمًا!",
]
_SOLO = [
    "🔥 منشور نار! هل تودون التعليق؟ ادخلوا مجموعة الدردشة 💬",
    "👏 تصفيق حار! والنقاش الأحلى في مجموعة الدردشة 🎤",
    "🌟 كل المنشورات حلوة، لكن النقاش أحلى! انضموا لمجموعة الدردشة 🤗",
    "💎 هنا يلمع المحتوى، وهناك يلمع النقاش! مجموعة الدردشة تنتظركم ✨",
    "🎊 أهلًا بالمتابعين الأوفياء! ادخلوا مجموعة الدردشة وشاركونا 🫶",
    "🚀 انطلقوا إلى مجموعة الدردشة وقولوا رأيكم بحرية! 🗣️",
    "🌹 تسلمون على متابعتكم! باب مجموعة الدردشة مفتوح 🚪",
    "😎 المتابع الذكي يدخل مجموعة الدردشة! هل أنتم منهم؟ 💬",
    "☀️ يوم جميل مع منشور جميل! شاركونا في مجموعة الدردشة 🧡",
    "🎯 أصبتم الهدف بمتابعتكم! خطوة واحدة تفصلكم: مجموعة الدردشة 👥",
    "🧠 أفكاركم تهمنا! اكتبوها في مجموعة الدردشة 📝",
    "💌 رسالة حب لكل متابع: ادخل مجموعة الدردشة وتعرّف على أصدقاء جدد 🤝",
    "🍀 حظ سعيد لمن يدخل مجموعة الدردشة اليوم! 😄",
    "🥳 الحفلة مستمرة في مجموعة الدردشة، ادخلوا وانضموا! 🎈",
    "🔔 تنبيه لطيف: مجموعة الدردشة بانتظار تعليقاتكم 💭",
    "🌈 كل يوم معكم أجمل! لا تنسوا مجموعة الدردشة 💞",
    "⭐ نجومنا هم المتابعون! انضموا لمجموعة الدردشة وتألقوا ✨",
    "🏅 أبطال المتابعة يتواجدون في مجموعة الدردشة، فادخلوا معهم! 🙌",
    "🎶 النقاش يحلو بوجودكم! تعالوا إلى مجموعة الدردشة 🎵",
    "💪 بهمتكم نكمل! ادخلوا مجموعة الدردشة وشاركونا الحماس 🔥",
    "🤩 منشور يبهر! والتعليقات تبهر أكثر في مجموعة الدردشة 💬",
    "🕊️ جو هادئ ونقاش لطيف في مجموعة الدردشة، تفضلوا ✨",
    "🧩 مجموعة الدردشة قطعة ناقصة من التجربة، أكملوها بوجودكم 💛",
    "📣 بصوت عالٍ: ادخلوا مجموعة الدردشة! 😁",
    "🎁 هدية اليوم: نقاش ممتع في مجموعة الدردشة، فاستلموها 🎀",
    "🌙 مساء الخير والتشجيع! دردشتنا مفتوحة لكم في مجموعة الدردشة 🌟",
    "☕ مع فنجان قهوتكم، تعالوا إلى مجموعة الدردشة وتحدثوا معنا 😊",
    "💫 أنتم سر نجاح القناة! شاركونا في مجموعة الدردشة 🥰",
    "🙋 من يريد أن يشارك؟ مجموعة الدردشة جاهزة لاستقبالكم! 🎤",
    "🌺 ذوقكم رفيع! أضيفوا لمستكم في مجموعة الدردشة 🎨",
    "🔥 الحماس يبدأ هنا وينتشر في مجموعة الدردشة! ادخلوا 💥",
    "🤗 مرحبًا بكل من وصل إلى هنا! بابنا الآخر هو مجموعة الدردشة 🚪",
    "📌 خطوتكم التالية: مجموعة الدردشة، كونوا معنا 👣",
    "🍯 حلاوة المتابعة بدخولكم مجموعة الدردشة! 😋",
    "🎉 أنتم الأروع! مجموعة الدردشة لا تكتمل إلا بكم 💖",
    "👀 هل شاهدتم المنشور؟ شاركونا آراءكم في مجموعة الدردشة 🗨️",
    "🌠 أمنيات جميلة لكم، وبانتظاركم في مجموعة الدردشة 🤲",
    "🏆 تفاعلكم هو الجائزة! ادخلوا مجموعة الدردشة وتفاعلوا 🥇",
    "💬 دردشة لطيفة تنتظركم في مجموعة الدردشة، فتفضلوا! 😄",
    "🧡 شكرًا لكل متابع! وللمزيد من الأجواء ادخلوا مجموعة الدردشة 🌼",
]


def _build_cheers():
    combos = [_OPEN[i] + "\n" + _JOIN[(i + r) % len(_JOIN)]
              for r in range(len(_JOIN)) for i in range(len(_OPEN))]
    out, k = [], 0
    for n, text in enumerate(combos):
        out.append(text)
        if n % 6 == 5 and k < len(_SOLO):
            out.append(_SOLO[k])
            k += 1
    return out + _SOLO[k:]


CHEERS = _build_cheers()

# =====================================================================
#  الترجمات (أي نص ناقص يؤخذ من الإنجليزية)
# =====================================================================
T = {
"ar": {
 "units": ("دقيقة", "ساعة", "يوم"),
 "warn": "⚠️ {user}\n📌 السبب: {reason}\n🔢 هذا التحذير {n} من {max}.",
 "muted": "🔇 تم كتمه لمدة {dur}.",
 "mutedu": "🔇 تم كتم {user} لمدة {dur}.\n📌 السبب: {reason}",
 "banned": "⛔ تم حظر {user}.\n📌 السبب: {reason}",
 "kicked": "👢 تم طرد {user}.",
 "unmuted": "🔊 تم إلغاء الكتم عن {user} بواسطة {admin}.",
 "unbanned": "✅ تم إلغاء حظر {user} بواسطة {admin}.",
 "reset": "🧹 تم تصفير تحذيرات {user} بواسطة {admin}.",
 "r_link": "إرسال الروابط ممنوع", "r_promo": "الترويج ممنوع",
 "r_flood": "إرسال رسائل بسرعة (سبام)", "r_dup": "تكرار نفس الرسالة (سبام)",
 "r_mention": "كثرة الإشارات (إزعاج)", "r_word": "استخدام كلمة محظورة",
 "r_max": "تجاوز الحد الأقصى للتحذيرات ({max})", "r_admin": "قرار المشرف",
 "b_unmute": "🔊 إلغاء الكتم (للمشرفين)", "b_unban": "✅ إلغاء الحظر (للمشرفين)",
 "b_reset": "🧹 تصفير التحذيرات (للمشرفين)",
 "adm_only": "هذا الزر للمشرفين فقط.",
 "left_note": "🚫 تم حظره تلقائيًا لمغادرته. يمكن للمشرفين إلغاء الحظر بالزر أو بالأمر /unban",
 "welcome": "أهلًا بك {name} في {group} 🌹\nالتزم بقوانين المجموعة.",
 "bye": "وداعًا {name} 👋",
 "need_target": "رد على رسالة العضو، أو اكتب @اليوزر أو معرّفه الرقمي بعد الأمر.",
 "is_admin": "لا يمكن تنفيذ هذا الأمر على مشرف.",
 "ok": "✅ تم.",
 "fail": "❌ تعذر التنفيذ. تأكد أن البوت مشرف بصلاحيات الحذف والحظر وتقييد الأعضاء.\n{err}",
 "usage": "الاستخدام: {u}",
 "warns": "📊 تحذيرات {user}: {n}/{max}",
 "no_words": "لا توجد كلمات محظورة.", "words": "🚫 الكلمات المحظورة:\n{list}",
 "w_add": "✅ أُضيفت الكلمة «{w}» ({m}).", "w_del": "✅ حُذفت الكلمة «{w}».",
 "rules_title": "📜 قوانين المجموعة:\n\n{rules}", "no_rules": "لم يضع المشرفون قوانين بعد.",
 "rules_set": "✅ تم حفظ القوانين.", "rules_off": "✅ تم حذف القوانين.",
 "joined": "✅ تم دخولي إلى المجموعة!\n\n⚠️ لأعمل بشكل صحيح اجعلني مشرفًا بصلاحيات: حذف الرسائل، حظر الأعضاء، تقييد الأعضاء.\n\n🌐 اكتب /settings لتغيير اللغة والخيارات.\n\nهذه أوامري:",
 "words_added": "✅ أُضيفت {n} كلمة:\n{list}", "words_bad": "⚠️ تم تجاهل {n} سطر غير صالح.",
 "periodic_set": "✅ ستُرسَل الرسالة الدورية كل {every}.", "periodic_off": "✅ تم إيقاف الرسالة الدورية.",
 "rules_dm": "📜 أهلًا بك في {group}!\nهذه قوانين المجموعة:\n\n{rules}", "b_rules": "📜 استلم القوانين في الخاص",
 "btns_set": "✅ تم حفظ {n} زر.", "btns_off": "✅ تم حذف الأزرار.",
 "link_set": "✅ تم حفظ رابط مجموعة الدردشة.", "link_off": "✅ تم حذف رابط مجموعة الدردشة.", "s_cheer": "تشجيع منشورات القناة",
 "w_none": "الكلمة غير موجودة.", "w_warnonly": "حذف وتحذير فقط",
 "no_domains": "لا توجد نطاقات مسموحة.", "domains": "🔗 النطاقات المسموحة:\n{list}",
 "d_add": "✅ تم السماح بـ {d}.", "d_del": "✅ تم منع {d}.",
 "text_set": "✅ تم حفظ النص.", "text_def": "✅ عاد النص إلى الافتراضي.",
 "media_set": "✅ تم حفظ الوسائط.", "media_off": "✅ تم حذف الوسائط.",
 "media_need": "رد على صورة أو فيديو أو GIF، أو اكتب off لحذفها.",
 "s_links": "حذف الروابط", "s_promo": "منع الترويج", "s_spam": "منع السبام",
 "s_words": "الكلمات المحظورة", "s_leaveban": "حظر من يغادر", "s_welcome": "الترحيب",
 "s_bye": "الوداع", "s_service": "حذف رسائل الانضمام",
 "set_info": "⚙️ إعدادات المجموعة\n\n⚠️ الحد الأقصى للتحذيرات: {mw}\n🚨 السبام: {fn} رسائل خلال {fs} ثانية ← كتم {sm} دقيقة\n\nاللغة والخيارات من الأزرار، وللمزيد: /help",
 "s_captcha": "التحقق (Captcha)",
 "cap_q": "🛡 أهلًا {user}!\nللتأكد أنك لست روبوتًا اضغط على: {emoji}\n⏳ لديك {sec} ثانية وإلا ستُطرد.",
 "cap_ok": "✅ تم التحقق، أهلًا بك!", "cap_wrong": "❌ إجابة خاطئة، حاول مرة أخرى.",
 "cap_fail": "❌ فشل التحقق وتم طردك.", "cap_not_you": "هذا الزر ليس لك.",
 "cap_set": "✅ تم تفعيل التحقق، المهلة {sec} ثانية.", "cap_off": "✅ تم إيقاف التحقق.",
 "words_cleared": "🗑 تم حذف جميع الكلمات المحظورة ({n}).",
 "warns_set": "✅ الحد الأقصى للتحذيرات: {n} — الإجراء عند بلوغه: {act}",
 "kickedr": "👢 تم طرد {user}.\n📌 السبب: {reason}",
 "user_none": "❌ لم أجد مستخدمًا بهذا اليوزر. تأكد من كتابته، أو ردّ على رسالته، أو استخدم معرّفه الرقمي.",
 "start": "أنا بوت حماية للمجموعات 🛡\nأضفني إلى مجموعتك كمشرف ثم اكتب /help هناك.\nأرسل لي صورة هنا لأعطيك file_id الخاص بها.",
 "help": "🛡 أوامر المشرفين (بالرد على رسالة العضو أو بكتابة @اليوزر أو معرّفه الرقمي، مثل: /ban @username سبب):\n/warn [سبب] — تحذير\n/unwarn — إزالة تحذير واحد\n/resetwarns — تصفير التحذيرات\n/warns — عرض التحذيرات\n/mute [المدة] [سبب] — كتم (مثل 30m أو 2h أو 1d، الافتراضي 60 دقيقة)\n/unmute — إلغاء الكتم\n/ban [سبب] — حظر\n/unban — إلغاء الحظر\n/kick — طرد\n/del — حذف الرسالة المردود عليها\n\n⚙️ الإعدادات:\n/settings — لوحة الإعدادات واللغة\n/addword — إضافة كلمات محظورة. كلمة واحدة: /addword كلمة 60m . وعدة كلمات دفعة واحدة، كل كلمة في سطر (أو مفصولة بفاصلة) وبجانبها مدة الكتم:\n/addword\nكلمة1 60m\nكلمة2 2h\nكلمة3 0\n(بدون مدة = المدة الافتراضية، و0 = حذف وتحذير بلا كتم)\n/delword الكلمة — حذف كلمة\n/words — عرض الكلمات\n/clearwords — حذف كل الكلمات المحظورة\n/setcaptcha ثواني — تفعيل التحقق بزر عند الانضمام (off للإيقاف)\n/setwarnaction ban|kick|mute [مدة] — الإجراء عند بلوغ حد التحذيرات (والحد من /setwarns أو لوحة /settings)\n/allow نطاق — السماح بروابط نطاق (بدون نطاق: عرض القائمة)\n/disallow نطاق — منع النطاق\n/setrules نص — تعيين قوانين المجموعة (off لحذفها) ويراها الجميع بالأمر /rules\n/setwelcome نص — رسالة الترحيب (يمكن استخدام {name} {group} {rules})\n/setbye نص — رسالة الوداع\n/setwelcomemedia — بالرد على صورة/فيديو/GIF للترحيب\n/setbyemedia — للوداع (اكتب off لحذف الوسائط)\n/setwarns عدد — الحد الأقصى للتحذيرات\n/setspam رسائل ثواني دقائق_الكتم — ضبط السبام\n/setwordmute المدة — مدة الكتم الافتراضية للكلمات\n/setperiodic المدة نص — رسالة تتكرر كل فترة (مثل 2h)، أو بالرد على صورة/رسالة. و/setperiodic off لإيقافها\n/setautodel ثواني — حذف ردود البوت تلقائيًا (off للإيقاف)\n/setwelcomebuttons — أزرار روابط تحت رسالة الترحيب: كل سطر صف، وكل زر بالشكل: نص | رابط (وللأكثر من زر في الصف افصل بـ &&). و off للحذف\n/setbyebuttons — أزرار الوداع\n/setperiodicbuttons — أزرار الرسالة الدورية\n/setchatlink رابط — رابط مجموعة الدردشة الذي يُضاف لرسائل التشجيع على منشورات القناة (تُفعَّل وتُعطَّل من /settings)\nلإعادة نص الترحيب للافتراضي: /setwelcome default",
},
"en": {
 "units": ("min", "h", "d"),
 "warn": "⚠️ {user}\n📌 Reason: {reason}\n🔢 This is warning {n} of {max}.",
 "muted": "🔇 Muted for {dur}.",
 "mutedu": "🔇 {user} was muted for {dur}.\n📌 Reason: {reason}",
 "banned": "⛔ {user} has been banned.\n📌 Reason: {reason}",
 "kicked": "👢 {user} has been kicked.",
 "unmuted": "🔊 {user} was unmuted by {admin}.",
 "unbanned": "✅ {user} was unbanned by {admin}.",
 "reset": "🧹 Warnings of {user} were reset by {admin}.",
 "r_link": "Links are not allowed", "r_promo": "Promotion is not allowed",
 "r_flood": "Sending messages too fast (spam)", "r_dup": "Repeating the same message (spam)",
 "r_mention": "Too many mentions (annoyance)", "r_word": "Using a banned word",
 "r_max": "Reached the maximum warnings ({max})", "r_admin": "Admin decision",
 "b_unmute": "🔊 Unmute (admins only)", "b_unban": "✅ Unban (admins only)",
 "b_reset": "🧹 Reset warnings (admins only)",
 "adm_only": "This button is for admins only.",
 "left_note": "🚫 Automatically banned for leaving. Admins can unban with the button or /unban",
 "welcome": "Welcome {name} to {group} 🌹\nPlease follow the group rules.",
 "bye": "Goodbye {name} 👋",
 "need_target": "Reply to the member's message, or write their @username or numeric ID after the command.",
 "is_admin": "This command cannot be used on an admin.",
 "ok": "✅ Done.",
 "fail": "❌ Failed. Make sure the bot is an admin with delete, ban and restrict permissions.\n{err}",
 "usage": "Usage: {u}",
 "warns": "📊 Warnings of {user}: {n}/{max}",
 "no_words": "No banned words.", "words": "🚫 Banned words:\n{list}",
 "w_add": "✅ Word «{w}» added ({m}).", "w_del": "✅ Word «{w}» removed.",
 "rules_title": "📜 Group rules:\n\n{rules}", "no_rules": "The admins have not set any rules yet.",
 "rules_set": "✅ Rules saved.", "rules_off": "✅ Rules removed.",
 "joined": "✅ I have joined the group!\n\n⚠️ To work properly make me an admin with: delete messages, ban users, restrict users.\n\n🌐 Type /settings to change the language and options.\n\nHere are my commands:",
 "words_added": "✅ {n} words added:\n{list}", "words_bad": "⚠️ {n} invalid lines were ignored.",
 "periodic_set": "✅ The recurring message will be sent every {every}.", "periodic_off": "✅ The recurring message was turned off.",
 "rules_dm": "📜 Welcome to {group}!\nThese are the group rules:\n\n{rules}", "b_rules": "📜 Get the rules in private",
 "btns_set": "✅ {n} buttons saved.", "btns_off": "✅ Buttons removed.",
 "link_set": "✅ Chat group link saved.", "link_off": "✅ Chat group link removed.", "s_cheer": "Cheer channel posts",
 "w_none": "Word not found.", "w_warnonly": "delete and warn only",
 "no_domains": "No allowed domains.", "domains": "🔗 Allowed domains:\n{list}",
 "d_add": "✅ {d} is now allowed.", "d_del": "✅ {d} is no longer allowed.",
 "text_set": "✅ Text saved.", "text_def": "✅ Text reset to default.",
 "media_set": "✅ Media saved.", "media_off": "✅ Media removed.",
 "media_need": "Reply to a photo, video or GIF, or write off to remove it.",
 "s_links": "Delete links", "s_promo": "Block promotion", "s_spam": "Block spam",
 "s_words": "Banned words", "s_leaveban": "Ban who leaves", "s_welcome": "Welcome",
 "s_bye": "Goodbye", "s_service": "Delete join/leave notices",
 "set_info": "⚙️ Group settings\n\n⚠️ Max warnings: {mw}\n🚨 Spam: {fn} messages in {fs} s → mute {sm} min\n\nUse the buttons for language and options. More: /help",
 "s_captcha": "Captcha",
 "cap_q": "🛡 Welcome {user}!\nTo prove you are not a robot press: {emoji}\n⏳ You have {sec} seconds or you will be kicked.",
 "cap_ok": "✅ Verified, welcome!", "cap_wrong": "❌ Wrong answer, try again.",
 "cap_fail": "❌ Verification failed, you were kicked.", "cap_not_you": "This button is not for you.",
 "cap_set": "✅ Captcha enabled, timeout {sec} s.", "cap_off": "✅ Captcha disabled.",
 "words_cleared": "🗑 All banned words were deleted ({n}).",
 "warns_set": "✅ Max warnings: {n} — action when reached: {act}",
 "kickedr": "👢 {user} has been kicked.\n📌 Reason: {reason}",
 "user_none": "❌ I could not find a user with that username. Check it, reply to their message, or use their numeric ID.",
 "start": "I am a group protection bot 🛡\nAdd me to your group as an admin, then send /help there.\nSend me a photo here to get its file_id.",
 "help": "🛡 Admin commands (reply to the member's message or write their @username or numeric ID, e.g. /ban @username reason):\n/warn [reason] — warn\n/unwarn — remove one warning\n/resetwarns — reset warnings\n/warns — show warnings\n/mute [time] [reason] — mute (e.g. 30m, 2h, 1d; default 60 min)\n/unmute — unmute\n/ban [reason] — ban\n/unban — unban\n/kick — kick\n/del — delete the replied message\n\n⚙️ Settings:\n/settings — settings panel and language\n/addword — add banned words. One word: /addword word 60m . Many words at once, one per line (or comma separated) with the mute time beside each:\n/addword\nword1 60m\nword2 2h\nword3 0\n(no time = default time, 0 = delete and warn only)\n/delword word — remove a word\n/words — list words\n/clearwords — delete all banned words\n/setcaptcha seconds — enable join captcha button (off to disable)\n/setwarnaction ban|kick|mute [time] — action at max warnings (limit via /setwarns or /settings)\n/allow domain — allow links of a domain (no argument: list)\n/disallow domain — block the domain again\n/setrules text — set the group rules (off to remove); everyone sees them with /rules\n/setwelcome text — welcome message ({name} {group} {rules} allowed)\n/setbye text — goodbye message\n/setwelcomemedia — reply to a photo/video/GIF\n/setbyemedia — same for goodbye (write off to remove)\n/setwarns number — max warnings\n/setspam messages seconds mute_minutes — spam settings\n/setwordmute time — default mute time for words\n/setperiodic time text — a message repeated every period (e.g. 2h), or reply to a photo/message. /setperiodic off to stop it\n/setautodel seconds — auto-delete bot replies (off to disable)\n/setwelcomebuttons — link buttons under the welcome message: one row per line, each button as: text | link (several in a row separated by &&). off to remove\n/setbyebuttons — goodbye buttons\n/setperiodicbuttons — buttons for the recurring message\n/setchatlink link — chat group link added to the cheer replies on channel posts (toggle in /settings)\nReset welcome text: /setwelcome default",
},
"fr": {
 "units": ("min", "h", "j"),
 "warn": "⚠️ {user}\n📌 Raison : {reason}\n🔢 Avertissement {n} sur {max}.",
 "muted": "🔇 Réduit au silence pendant {dur}.",
 "mutedu": "🔇 {user} est réduit au silence pendant {dur}.\n📌 Raison : {reason}",
 "banned": "⛔ {user} a été banni.\n📌 Raison : {reason}",
 "kicked": "👢 {user} a été expulsé.",
 "unmuted": "🔊 {user} a retrouvé la parole (par {admin}).",
 "unbanned": "✅ {user} a été débanni par {admin}.",
 "reset": "🧹 Avertissements de {user} remis à zéro par {admin}.",
 "r_link": "Les liens sont interdits", "r_promo": "La promotion est interdite",
 "r_flood": "Messages trop rapides (spam)", "r_dup": "Même message répété (spam)",
 "r_mention": "Trop de mentions", "r_word": "Mot interdit utilisé",
 "r_max": "Maximum d'avertissements atteint ({max})", "r_admin": "Décision d'un admin",
 "b_unmute": "🔊 Rétablir la parole (admins)", "b_unban": "✅ Débannir (admins)",
 "b_reset": "🧹 Réinitialiser les avertissements (admins)",
 "adm_only": "Ce bouton est réservé aux admins.",
 "left_note": "🚫 Banni automatiquement pour avoir quitté. Les admins peuvent débannir avec le bouton ou /unban",
 "welcome": "Bienvenue {name} dans {group} 🌹\nMerci de respecter les règles.",
 "bye": "Au revoir {name} 👋",
 "need_target": "Répondez au message du membre, ou écrivez son ID numérique après la commande.",
 "is_admin": "Impossible sur un admin.",
 "ok": "✅ Fait.",
 "fail": "❌ Échec. Vérifiez que le bot est admin (suppression, bannissement, restriction).\n{err}",
 "usage": "Utilisation : {u}",
 "warns": "📊 Avertissements de {user} : {n}/{max}",
 "no_words": "Aucun mot interdit.", "words": "🚫 Mots interdits :\n{list}",
 "w_add": "✅ Mot «{w}» ajouté ({m}).", "w_del": "✅ Mot «{w}» supprimé.",
 "rules_title": "📜 Règles du groupe :\n\n{rules}", "no_rules": "Les admins n'ont pas encore défini de règles.",
 "rules_set": "✅ Règles enregistrées.", "rules_off": "✅ Règles supprimées.",
 "joined": "✅ Je suis dans le groupe !\n\n⚠️ Pour fonctionner, faites de moi un admin (supprimer, bannir, restreindre).\n\n🌐 Tapez /settings pour la langue et les options.\n\nVoici mes commandes :",
 "words_added": "✅ {n} mots ajoutés :\n{list}", "words_bad": "⚠️ {n} lignes invalides ignorées.",
 "periodic_set": "✅ Le message récurrent sera envoyé toutes les {every}.", "periodic_off": "✅ Message récurrent désactivé.",
 "rules_dm": "📜 Bienvenue dans {group} !\nVoici les règles du groupe :\n\n{rules}", "b_rules": "📜 Recevoir les règles en privé",
 "btns_set": "✅ {n} boutons enregistrés.", "btns_off": "✅ Boutons supprimés.",
 "link_set": "✅ Lien du groupe de discussion enregistré.", "link_off": "✅ Lien supprimé.", "s_cheer": "Encourager les posts du canal",
 "w_none": "Mot introuvable.", "w_warnonly": "suppression et avertissement seulement",
 "no_domains": "Aucun domaine autorisé.", "domains": "🔗 Domaines autorisés :\n{list}",
 "d_add": "✅ {d} autorisé.", "d_del": "✅ {d} n'est plus autorisé.",
 "text_set": "✅ Texte enregistré.", "text_def": "✅ Texte par défaut rétabli.",
 "media_set": "✅ Média enregistré.", "media_off": "✅ Média supprimé.",
 "media_need": "Répondez à une photo, vidéo ou GIF, ou écrivez off.",
 "s_links": "Supprimer les liens", "s_promo": "Bloquer la promotion", "s_spam": "Bloquer le spam",
 "s_words": "Mots interdits", "s_leaveban": "Bannir ceux qui partent", "s_welcome": "Bienvenue",
 "s_bye": "Au revoir", "s_service": "Supprimer les notifications",
 "set_info": "⚙️ Paramètres du groupe\n\n⚠️ Avertissements max : {mw}\n🚨 Spam : {fn} messages en {fs} s → silence {sm} min\n\nLangue et options avec les boutons. Plus : /help",
 "start": "Je suis un bot de protection de groupe 🛡\nAjoutez-moi comme admin puis envoyez /help dans le groupe.",
},
"tr": {
 "units": ("dk", "sa", "g"),
 "warn": "⚠️ {user}\n📌 Sebep: {reason}\n🔢 Bu uyarı {n}/{max}.",
 "muted": "🔇 {dur} süreyle susturuldu.",
 "mutedu": "🔇 {user} {dur} süreyle susturuldu.\n📌 Sebep: {reason}",
 "banned": "⛔ {user} yasaklandı.\n📌 Sebep: {reason}",
 "kicked": "👢 {user} atıldı.",
 "unmuted": "🔊 {user} susturması {admin} tarafından kaldırıldı.",
 "unbanned": "✅ {user} yasağı {admin} tarafından kaldırıldı.",
 "reset": "🧹 {user} uyarıları {admin} tarafından sıfırlandı.",
 "r_link": "Bağlantı göndermek yasak", "r_promo": "Reklam yasak",
 "r_flood": "Çok hızlı mesaj (spam)", "r_dup": "Aynı mesajı tekrarlama (spam)",
 "r_mention": "Çok fazla etiket", "r_word": "Yasaklı kelime kullanımı",
 "r_max": "Maksimum uyarıya ulaşıldı ({max})", "r_admin": "Yönetici kararı",
 "b_unmute": "🔊 Susturmayı kaldır (yöneticiler)", "b_unban": "✅ Yasağı kaldır (yöneticiler)",
 "b_reset": "🧹 Uyarıları sıfırla (yöneticiler)",
 "adm_only": "Bu düğme sadece yöneticiler içindir.",
 "left_note": "🚫 Gruptan ayrıldığı için otomatik yasaklandı. Yöneticiler düğmeyi veya /unban kullanabilir.",
 "welcome": "{group} grubuna hoş geldin {name} 🌹\nLütfen kurallara uy.",
 "bye": "Hoşça kal {name} 👋",
 "need_target": "Üyenin mesajını yanıtlayın veya komuttan sonra sayısal ID yazın.",
 "is_admin": "Bu komut yöneticiye uygulanamaz.",
 "ok": "✅ Tamam.",
 "fail": "❌ Başarısız. Botun silme, yasaklama ve kısıtlama yetkisi olan yönetici olduğundan emin olun.\n{err}",
 "usage": "Kullanım: {u}",
 "warns": "📊 {user} uyarıları: {n}/{max}",
 "no_words": "Yasaklı kelime yok.", "words": "🚫 Yasaklı kelimeler:\n{list}",
 "w_add": "✅ «{w}» eklendi ({m}).", "w_del": "✅ «{w}» silindi.",
 "rules_title": "📜 Grup kuralları:\n\n{rules}", "no_rules": "Yöneticiler henüz kural belirlemedi.",
 "rules_set": "✅ Kurallar kaydedildi.", "rules_off": "✅ Kurallar silindi.",
 "joined": "✅ Gruba katıldım!\n\n⚠️ Düzgün çalışmam için beni yönetici yapın (mesaj silme, yasaklama, kısıtlama).\n\n🌐 Dil ve seçenekler için /settings yazın.\n\nKomutlarım:",
 "words_added": "✅ {n} kelime eklendi:\n{list}", "words_bad": "⚠️ {n} geçersiz satır yok sayıldı.",
 "periodic_set": "✅ Tekrarlayan mesaj her {every} gönderilecek.", "periodic_off": "✅ Tekrarlayan mesaj kapatıldı.",
 "rules_dm": "📜 {group} grubuna hoş geldin!\nGrup kuralları:\n\n{rules}", "b_rules": "📜 Kuralları özelden al",
 "btns_set": "✅ {n} düğme kaydedildi.", "btns_off": "✅ Düğmeler silindi.",
 "link_set": "✅ Sohbet grubu bağlantısı kaydedildi.", "link_off": "✅ Bağlantı silindi.", "s_cheer": "Kanal gönderilerini teşvik et",
 "w_none": "Kelime bulunamadı.", "w_warnonly": "sadece sil ve uyar",
 "no_domains": "İzinli alan adı yok.", "domains": "🔗 İzinli alan adları:\n{list}",
 "d_add": "✅ {d} artık izinli.", "d_del": "✅ {d} artık izinli değil.",
 "text_set": "✅ Metin kaydedildi.", "text_def": "✅ Varsayılana dönüldü.",
 "media_set": "✅ Medya kaydedildi.", "media_off": "✅ Medya silindi.",
 "media_need": "Bir fotoğraf, video veya GIF'i yanıtlayın ya da off yazın.",
 "s_links": "Bağlantıları sil", "s_promo": "Reklamı engelle", "s_spam": "Spamı engelle",
 "s_words": "Yasaklı kelimeler", "s_leaveban": "Ayrılanı yasakla", "s_welcome": "Karşılama",
 "s_bye": "Veda", "s_service": "Giriş/çıkış mesajlarını sil",
 "set_info": "⚙️ Grup ayarları\n\n⚠️ Maks. uyarı: {mw}\n🚨 Spam: {fs} sn içinde {fn} mesaj → {sm} dk susturma\n\nDil ve seçenekler için düğmeler. Daha fazlası: /help",
 "start": "Ben bir grup koruma botuyum 🛡\nBeni yönetici olarak ekleyin ve grupta /help yazın.",
},
}


def lang_of(cid):
    return cfg(cid)["lang"]


def tr(cid, key, **kw):
    L = lang_of(cid) if cid is not None else "ar"
    s = T.get(L, {}).get(key) or T["en"].get(key) or key
    if key in ("start", "help", "set_info"):
        s += "\n\n" + CREDIT
    return s.format(**kw) if kw else s


# =====================================================================
#  التخزين الدائم داخل مستودع GitHub (ملف data/<bot_id>.json)
# =====================================================================
REPO = os.environ.get("GITHUB_REPOSITORY")
GH = os.environ.get("GITHUB_TOKEN")
DATA_PATH = f"data/{TOKEN.split(':')[0]}.json"
data = {"chats": {}, "warns": {}, "unames": {}}
sha = None
loaded = False
dirty = False


def touch():
    global dirty
    dirty = True


def _gh(method, body=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{DATA_PATH}", method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {GH}", "Accept": "application/vnd.github+json",
                 "User-Agent": "group-guard-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load():
    global data, sha, loaded
    try:
        if REPO and GH:
            try:
                j = _gh("GET")
                sha = j["sha"]
                data = json.loads(base64.b64decode(j["content"]).decode())
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
        elif os.path.exists("data.json"):
            data = json.load(open("data.json", encoding="utf-8"))
        data.setdefault("chats", {})
        data.setdefault("warns", {})
        data.setdefault("unames", {})
        if data.get("v", 0) < 2:  # ترحيل: إيقاف الحذف التلقائي للردود في المجموعات القديمة
            for _c in data["chats"].values():
                _c["ttl"] = 0
            data["v"] = 2
            touch()
        loaded = True
        log.info("data loaded")
    except Exception as e:
        loaded = False
        log.error("load failed: %s", e)


def save(payload):
    global sha
    try:
        if REPO and GH:
            body = {"message": "bot data", "content": base64.b64encode(payload.encode()).decode()}
            for _ in range(2):
                if sha:
                    body["sha"] = sha
                try:
                    sha = _gh("PUT", body)["content"]["sha"]
                    return True
                except urllib.error.HTTPError as e:
                    if e.code in (409, 422):
                        try:
                            sha = _gh("GET")["sha"]
                        except urllib.error.HTTPError:
                            sha = None
                        continue
                    raise
            return False
        with open("data.json", "w", encoding="utf-8") as f:
            f.write(payload)
        return True
    except Exception as e:
        log.error("save failed: %s", e)
        return False


async def saver():
    global dirty
    while True:
        await asyncio.sleep(15)
        if not loaded:
            await asyncio.to_thread(load)
        if dirty and loaded:
            dirty = False
            payload = json.dumps(data, ensure_ascii=False, indent=1)
            if not await asyncio.to_thread(save, payload):
                dirty = True


def cfg(cid):
    c = data["chats"].setdefault(str(cid), {})
    for k, v in DEFAULTS.items():
        if k not in c:
            c[k] = deepcopy(v)
    return c


def warns_of(cid, uid):
    return data["warns"].get(f"{cid}:{uid}", 0)


def set_warns(cid, uid, n):
    if n <= 0:
        data["warns"].pop(f"{cid}:{uid}", None)
    else:
        data["warns"][f"{cid}:{uid}"] = n
    touch()


# =====================================================================
#  أدوات مساعدة
# =====================================================================
AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})


def norm(s):
    s = re.sub("[\u064b-\u065f\u0670\u0640]", "", s.casefold())
    return s.translate(AR_MAP).strip()


def parse_dur(s):
    m = re.fullmatch(r"(\d+)([mhd]?)", s.lower())
    if not m:
        return None
    return int(m[1]) * {"": 1, "m": 1, "h": 60, "d": 1440}[m[2]]


def fmt_dur(cid, mins):
    u = T.get(lang_of(cid), {}).get("units") or T["en"]["units"]
    d, r = divmod(mins, 1440)
    h, mn = divmod(r, 60)
    parts = [f"{n} {u[i]}" for n, i in ((d, 2), (h, 1), (mn, 0)) if n]
    return " ".join(parts) or f"0 {u[0]}"


def mention_id(uid, name):
    return f'<a href="tg://user?id={uid}">{html.escape(name or str(uid))}</a>'


def mention(u):
    return mention_id(u.id, u.full_name)


def media_of(m):
    if m.photo:
        return ["photo", m.photo[-1].file_id]
    if m.animation:
        return ["animation", m.animation.file_id]
    if m.video:
        return ["video", m.video.file_id]
    return None


async def send_media(bot, cid, media, text, markup=None):
    if media:
        fn = {"photo": bot.send_photo, "video": bot.send_video,
              "animation": bot.send_animation}.get(media[0])
        try:
            return await fn(cid, media[1], caption=text, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            log.warning("media send failed: %s", e)
    return await bot.send_message(cid, text, parse_mode="HTML", reply_markup=markup)


def render(tpl, user, chat):
    return (html.escape(tpl).replace("{name}", mention(user))
            .replace("{group}", html.escape(chat.title or "")).replace("{id}", str(user.id))
            .replace("{rules}", html.escape(cfg(chat.id)["rules"])))


adm_cache = {}


async def is_admin(ctx, cid, uid):
    if uid == 1087968824:  # المشرف المجهول
        return True
    t, s = adm_cache.get(cid, (0, set()))
    if time.time() - t > 60:
        try:
            s = {m.user.id for m in await ctx.bot.get_chat_administrators(cid)}
            adm_cache[cid] = (time.time(), s)
        except Exception as e:
            log.warning("admin list failed: %s", e)
    return uid in s


async def name_of(ctx, cid, uid):
    try:
        return (await ctx.bot.get_chat_member(cid, uid)).user.full_name
    except Exception:
        return str(uid)


def no_perms():
    f = getattr(ChatPermissions, "no_permissions", None)
    return f() if f else ChatPermissions(can_send_messages=False)


def all_perms():
    f = getattr(ChatPermissions, "all_permissions", None)
    return f() if f else ChatPermissions(can_send_messages=True, can_send_other_messages=True,
                                         can_send_polls=True, can_add_web_page_previews=True)


async def do_mute(ctx, cid, uid, minutes):
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes) if minutes else None
    await ctx.bot.restrict_chat_member(cid, uid, no_perms(), until_date=until)


async def do_unmute(ctx, cid, uid):
    ch = await ctx.bot.get_chat(cid)
    await ctx.bot.restrict_chat_member(cid, uid, ch.permissions or all_perms())


def btn(cid, key, cb):
    return InlineKeyboardButton(tr(cid, key), callback_data=cb)


async def punish(ctx, cid, uid, name, reason, mute_min=0):
    """تحذير + (كتم اختياري) + حظر عند بلوغ الحد الأقصى. reason نص آمن لـ HTML."""
    c = cfg(cid)
    mx = c["max_warns"]
    n = warns_of(cid, uid) + 1
    ment = mention_id(uid, name)
    if n >= mx:
        set_warns(cid, uid, 0)
        act = c.get("warn_action", "ban")
        full = tr(cid, "r_max", max=mx) + " — " + reason
        if act == "kick":
            await ctx.bot.ban_chat_member(cid, uid)
            await ctx.bot.unban_chat_member(cid, uid, only_if_banned=True)
            text = tr(cid, "kickedr", user=ment, reason=full)
            rows = []
        elif act == "mute":
            dur = c.get("warn_dur", 1440)
            await do_mute(ctx, cid, uid, dur)
            text = tr(cid, "mutedu", user=ment, dur=fmt_dur(cid, dur), reason=full)
            rows = [[btn(cid, "b_unmute", f"um:{uid}")]]
        else:
            await ctx.bot.ban_chat_member(cid, uid)
            text = tr(cid, "banned", user=ment, reason=full)
            rows = [[btn(cid, "b_unban", f"ub:{uid}")]]
    else:
        set_warns(cid, uid, n)
        text = tr(cid, "warn", user=ment, reason=reason, n=n, max=mx)
        rows = []
        if mute_min > 0:
            await do_mute(ctx, cid, uid, mute_min)
            text += "\n" + tr(cid, "muted", dur=fmt_dur(cid, mute_min))
            rows.append([btn(cid, "b_unmute", f"um:{uid}")])
        rows.append([btn(cid, "b_reset", f"rw:{uid}")])
    await ctx.bot.send_message(cid, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows) if rows else None)


# =====================================================================
#  كشف المخالفات
# =====================================================================
TLDS = ("com|net|org|io|me|ly|app|xyz|info|ru|tr|ir|sa|eg|tk|gg|cc|ai|dev|link|online|site|top|club|"
        "shop|store|live|tv|bot|fr|de|uk|vip|pw|cn|biz|click|run|page|cloud|su|ua")
DOM_RE = re.compile(rf"(?<![\w@.])(?:https?://)?((?:[a-z0-9-]+\.)+(?:{TLDS}))\b", re.I)
PROMO_RE = re.compile("|".join([
    r"(?:انضم|اشترك|تابع|ادخل|شاهد|زور)\w*\s+(?:\S+\s+){0,2}?[لبوف]?(?:قناتي|قناتنا|قناه|مجموعتي|مجموعتنا|جروبي|صفحتي|حسابي|رابط)",
    r"(?:join|subscribe|follow|visit)\s+(?:\S+\s+){0,2}?(?:channel|group|page|account|link)",
    r"(?:rejoignez|abonnez)\w*\s+(?:\S+\s+){0,2}?(?:chaine|canal|groupe)",
    r"kanal\w*\s+(?:\S+\s+)?(?:katil|katıl|abone)",
    r"للبيع|للايجار|ربح\s+مضمون|اربح\s+من|استثمار\s+مضمون|راسلني\s+خاص|تواصل\s+خاص|للتواصل\s+واتس",
    r"earn\s+\$|free\s+money|dm\s+me|crypto\s+signals|forex\s+signals",
]), re.I)

times = defaultdict(deque)
dups = defaultdict(lambda: deque(maxlen=3))


def extract_domains(msg, text):
    doms = set()
    ents = {}
    try:
        ents.update(msg.parse_entities(["url", "text_link"]))
        ents.update(msg.parse_caption_entities(["url", "text_link"]))
    except Exception:
        pass
    for e, t in ents.items():
        u = e.url if e.type == "text_link" and e.url else t
        h = urlparse(u if "://" in u else "http://" + u).hostname
        if h:
            doms.add(h.lower().removeprefix("www."))
    for m in DOM_RE.finditer(text):
        doms.add(m.group(1).lower().removeprefix("www."))
    return doms


def check_spam(c, cid, uid, msg, n_text):
    now = time.time()
    k = (cid, uid)
    q = times[k]
    if q.maxlen != c["flood_n"]:
        q = times[k] = deque(q, maxlen=c["flood_n"])
    q.append(now)
    if len(q) == q.maxlen and now - q[0] < c["flood_s"]:
        q.clear()
        return "r_flood"
    ents = tuple(msg.entities or ()) + tuple(msg.caption_entities or ())
    if sum(1 for e in ents if e.type in ("mention", "text_mention")) >= 6:
        return "r_mention"
    if len(n_text) >= 4:
        d = dups[k]
        d.append((now, n_text))
        if sum(1 for t, x in d if now - t < 30 and x == n_text) >= 3:
            d.clear()
            return "r_dup"
    return None


async def guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if msg and getattr(msg, "is_automatic_forward", False) and update.edited_message is None:
        return await cheer_post(msg, chat)
    if not msg or not user or msg.sender_chat or user.is_bot:
        return
    remember(user)
    c = cfg(chat.id)
    text = msg.text or msg.caption or ""
    nt = norm(text)
    edited = update.edited_message is not None
    viol = None  # (مفتاح السبب، مدة الكتم)

    if c["words"] and c["banned"] and nt:
        best = None
        for w, mins in c["banned"].items():
            if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", nt):
                best = max(best or 0, mins)
        if best is not None:
            viol = ("r_word", best)
    if not viol and c["links"]:
        doms = extract_domains(msg, text)
        if any(not any(d == a or d.endswith("." + a) for a in c["allow"]) for d in doms):
            viol = ("r_link", 0)
    if not viol and c["promo"]:
        fo = getattr(msg, "forward_origin", None)
        if (fo is not None and fo.type == "channel") or (nt and PROMO_RE.search(nt)):
            viol = ("r_promo", 0)
    if c["spam"] and not edited:
        r = check_spam(c, chat.id, user.id, msg, nt)
        if r and not viol:
            viol = (r, c["spam_mute"])
    if not viol:
        return
    if await is_admin(ctx, chat.id, user.id):
        return
    try:
        await msg.delete()
    except Exception as e:
        log.warning("delete failed: %s", e)
    try:
        await punish(ctx, chat.id, user.id, user.full_name, tr(chat.id, viol[0]), viol[1])
    except Exception as e:
        log.warning("punish failed: %s", e)


# =====================================================================
#  الترحيب والوداع وحظر من يغادر
# =====================================================================
recent = {}


def fresh(cid, uid, kind):
    """يمنع تكرار نفس الحدث إذا وصل من مصدرين (رسالة خدمة + تحديث عضوية)."""
    now = time.time()
    k = (cid, uid, kind)
    if now - recent.get(k, 0) < 30:
        return False
    if len(recent) > 2000:
        recent.clear()
    recent[k] = now
    return True


def was_member(cm):
    return cm.status in ("member", "administrator", "creator") or (
        cm.status == "restricted" and bool(getattr(cm, "is_member", False)))


async def bot_joined(ctx, cid):
    if fresh(cid, ctx.bot.id, "joined"):
        await ctx.bot.send_message(cid, tr(cid, "joined") + "\n\n" + tr(cid, "help"))


async def do_join(ctx, chat, u):
    c = cfg(chat.id)
    if u.is_bot or not fresh(chat.id, u.id, "join"):
        return
    remember(u)
    if c["captcha"] and await start_captcha(ctx, chat, u):
        return
    await welcome_user(ctx, chat, u)


async def welcome_user(ctx, chat, u):
    c = cfg(chat.id)
    dm_ok = False
    if c["rules"]:  # القوانين في الخاص (تنجح فقط إن سبق للعضو أن بدأ محادثة مع البوت)
        try:
            await ctx.bot.send_message(u.id, tr(chat.id, "rules_dm", group=chat.title or "", rules=c["rules"]))
            dm_ok = True
        except Exception:
            dm_ok = False
    if not c["welcome"]:
        return
    rows = [[InlineKeyboardButton(t, url=url) for t, url in r] for r in c["welcome_btns"]]
    if c["rules"] and not dm_ok and getattr(ctx.bot, "username", None):
        rows.append([InlineKeyboardButton(tr(chat.id, "b_rules"),
                                          url=f"https://t.me/{ctx.bot.username}?start=r{abs(chat.id)}")])
    tpl = c["welcome_text"] or tr(chat.id, "welcome")
    await send_media(ctx.bot, chat.id, c["welcome_media"], render(tpl, u, chat),
                     InlineKeyboardMarkup(rows) if rows else None)



# ---------------- التحقق (Captcha) ----------------
CAP_EMOJI = ["🍎", "🐶", "🚗", "⚽", "🌙", "🔑", "🎁", "🐱", "🍕", "🌸", "⭐", "🎈"]
cap_pending = {}


async def captcha_timeout(bot, cid, uid, secs):
    await asyncio.sleep(secs)
    p = cap_pending.pop((cid, uid), None)
    if not p:
        return
    try:
        await bot.delete_message(cid, p["mid"])
    except Exception:
        pass
    try:
        await bot.ban_chat_member(cid, uid)
        await bot.unban_chat_member(cid, uid, only_if_banned=True)
    except Exception as e:
        log.warning("captcha kick failed: %s", e)


async def start_captcha(ctx, chat, u):
    cid, secs = chat.id, cfg(chat.id)["captcha_time"]
    try:
        until = datetime.now(timezone.utc) + timedelta(seconds=secs + 90)
        await ctx.bot.restrict_chat_member(cid, u.id, no_perms(), until_date=until)
        opts = random.sample(CAP_EMOJI, 4)
        ans = random.choice(opts)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(e, callback_data=f"cp:{u.id}:{e}") for e in opts]])
        msg = await ctx.bot.send_message(cid, tr(cid, "cap_q", user=mention(u), emoji=ans, sec=secs),
                                         parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        log.warning("captcha start failed: %s", e)
        return False
    task = asyncio.create_task(captcha_timeout(ctx.bot, cid, u.id, secs))
    cap_pending[(cid, u.id)] = {"mid": msg.message_id, "ans": ans, "task": task, "tries": 0}
    return True


async def captcha_press(q, ctx):
    _, uid_s, emoji = q.data.split(":", 2)
    uid, chat = int(uid_s), q.message.chat
    cid = chat.id
    if q.from_user.id != uid:
        return await q.answer(tr(cid, "cap_not_you"), show_alert=True)
    p = cap_pending.get((cid, uid))
    if not p:
        await try_delete(q.message)
        return await q.answer()
    if emoji == p["ans"]:
        cap_pending.pop((cid, uid), None)
        p["task"].cancel()
        try:
            await do_unmute(ctx, cid, uid)
        except Exception as e:
            log.warning("captcha unmute failed: %s", e)
        await try_delete(q.message)
        await q.answer(tr(cid, "cap_ok"))
        return await welcome_user(ctx, chat, q.from_user)
    p["tries"] += 1
    if p["tries"] >= 2:
        cap_pending.pop((cid, uid), None)
        p["task"].cancel()
        await try_delete(q.message)
        try:
            await ctx.bot.ban_chat_member(cid, uid)
            await ctx.bot.unban_chat_member(cid, uid, only_if_banned=True)
        except Exception as e:
            log.warning("captcha kick failed: %s", e)
        return await q.answer(tr(cid, "cap_fail"), show_alert=True)
    await q.answer(tr(cid, "cap_wrong"), show_alert=True)


async def do_leave(ctx, chat, u):
    c, cid = cfg(chat.id), chat.id
    if u.is_bot or not fresh(cid, u.id, "leave"):
        return
    p = cap_pending.pop((cid, u.id), None)
    if p:  # غادر أثناء التحقق: لا حظر ولا وداع
        p["task"].cancel()
        try:
            await ctx.bot.delete_message(cid, p["mid"])
        except Exception:
            pass
        return
    if c["leaveban"]:  # حظر صامت: لا تظهر أي رسالة عن الحظر
        try:
            await ctx.bot.ban_chat_member(cid, u.id)
        except Exception as e:
            log.warning("leave-ban failed: %s", e)
    if c["bye"]:
        await send_media(ctx.bot, cid, c["bye_media"], render(c["bye_text"] or tr(cid, "bye"), u, chat),
                         make_markup(c["bye_btns"]))


async def service(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg, chat = update.effective_message, update.effective_chat
    c = cfg(chat.id)
    for u in msg.new_chat_members or []:
        if u.id == ctx.bot.id:
            await bot_joined(ctx, chat.id)
        else:
            await do_join(ctx, chat, u)
    u = msg.left_chat_member
    if u and msg.from_user and msg.from_user.id == u.id:  # غادر بنفسه
        await do_leave(ctx, chat, u)
    if c["service"]:
        try:
            await msg.delete()
        except Exception:
            pass


async def member_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """يصل حتى في المجموعات الكبيرة التي لا تُرسَل فيها رسائل الانضمام (يتطلب أن يكون البوت مشرفًا)."""
    cmu = update.chat_member
    if not cmu or cmu.chat.type not in ("group", "supergroup"):
        return
    old, new = cmu.old_chat_member, cmu.new_chat_member
    u = new.user
    if not was_member(old) and was_member(new):
        await do_join(ctx, cmu.chat, u)
    elif was_member(old) and new.status == "left" and cmu.from_user and cmu.from_user.id == u.id:
        await do_leave(ctx, cmu.chat, u)


async def my_member_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cmu = update.my_chat_member
    if cmu and cmu.chat.type in ("group", "supergroup") and \
            not was_member(cmu.old_chat_member) and was_member(cmu.new_chat_member):
        await bot_joined(ctx, cmu.chat.id)


# =====================================================================
#  حذف الأوامر والردود تلقائيًا + أدوات القوائم
# =====================================================================
async def try_delete(msg):
    try:
        await msg.delete()
    except Exception:
        pass


async def _later_delete(msg, secs):
    await asyncio.sleep(secs)
    await try_delete(msg)


def make_reply(ctx, cid):
    """يرسل رد البوت دون الاعتماد على رسالة الأمر (لأنها تُحذف)، ويحذف الرد تلقائيًا."""
    async def reply(text, parse_mode=None, reply_markup=None, long=False, keep=None, ttl=None):
        if len(text) > 4000:
            text = text[:3990] + "…"
        msg = await ctx.bot.send_message(cid, text, parse_mode=parse_mode, reply_markup=reply_markup)
        t = cfg(cid)["ttl"]
        if keep is None:
            keep = reply_markup is not None
        if ttl is None:
            ttl = t * (4 if long else 1)
        if t and not keep and ttl:
            asyncio.create_task(_later_delete(msg, ttl))
        return msg
    return reply


def parse_entries(body, default):
    """كل سطر أو فاصلة = كلمة + مدة اختيارية (قبلها أو بعدها). يعيد (قاموس، عدد غير الصالح)."""
    out, bad = {}, 0
    for item in re.split(r"[\n,،;؛]+", body):
        t = item.split()
        if not t:
            continue
        d = None
        if len(t) == 1 and parse_dur(t[0]) is not None:
            bad += 1
            continue
        if len(t) > 1 and parse_dur(t[-1]) is not None:
            d, t = parse_dur(t[-1]), t[:-1]
        elif len(t) > 1 and parse_dur(t[0]) is not None:
            d, t = parse_dur(t[0]), t[1:]
        w = norm(" ".join(t))
        if not w:
            bad += 1
            continue
        out[w] = default if d is None else d
    return out, bad


def make_markup(rows):
    if not rows:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, url=u) for t, u in r] for r in rows])


def parse_btns(body):
    """كل سطر = صف أزرار. كل زر: نص | رابط. للأكثر من زر في الصف: افصل بـ &&"""
    rows, bad = [], 0
    for line in body.splitlines():
        row = []
        for part in line.split("&&"):
            if not part.strip():
                continue
            if "|" not in part:
                bad += 1
                continue
            t, u = part.split("|", 1)
            t, u = t.strip(), u.strip()
            if u.startswith("@"):
                u = "https://t.me/" + u[1:]
            elif u.startswith(("t.me/", "www.")):
                u = "https://" + u
            if not t or not re.fullmatch(r"(https?|tg)://\S+", u):
                bad += 1
                continue
            row.append([t[:60], u])
        if row:
            rows.append(row[:3])
    return rows[:6], bad


async def cheer_post(msg, chat):
    """يرد على منشور القناة (الذي يظهر في مجموعة الدردشة) برسالة تشجيع بالترتيب."""
    c = cfg(chat.id)
    if not c["cheer"]:
        return
    i = c["cheer_i"] % len(CHEERS)
    c["cheer_i"] = (i + 1) % len(CHEERS)  # بعد آخر رسالة نعود للأولى
    touch()
    text = CHEERS[i]
    link = c["chat_link"] or (f"https://t.me/{chat.username}" if getattr(chat, "username", None) else "")
    if link:
        text += "\n" + link
    try:
        await msg.reply_text(text, link_preview_options=LinkPreviewOptions(is_disabled=True))
    except Exception as e:
        log.warning("cheer failed: %s", e)


def words_summary(cid, entries, bad):
    items = list(entries.items())
    shown = items if len(items) <= 12 else items[:8]
    lst = "\n".join(f"• {w} — {fmt_dur(cid, v) if v else tr(cid, 'w_warnonly')}" for w, v in shown)
    if len(items) > len(shown):
        lst += f"\n… +{len(items) - len(shown)}"
    txt = tr(cid, "words_added", n=len(entries), list=lst)
    if bad:
        txt += "\n" + tr(cid, "words_bad", n=bad)
    return txt


async def addword_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """إرسال ملف نصي (.txt) مع التعليق /addword يضيف كل الكلمات التي فيه دفعة واحدة."""
    m, chat, me = update.effective_message, update.effective_chat, update.effective_user
    cid = chat.id
    reply = make_reply(ctx, cid)
    await try_delete(m)
    if not await is_admin(ctx, cid, me.id):
        return
    d = m.document
    if d.file_size and d.file_size > 1_000_000:
        return await reply(tr(cid, "fail", err="file too large"))
    try:
        f = await d.get_file()
        text = bytes(await f.download_as_bytearray()).decode("utf-8-sig", errors="ignore")
    except Exception as e:
        return await reply(tr(cid, "fail", err=str(e)[:200]))
    c = cfg(cid)
    entries, bad = parse_entries(text, c["word_mute"])
    if not entries:
        return await reply(tr(cid, "usage", u="/addword (file)"))
    c["banned"].update(entries)
    touch()
    await reply(words_summary(cid, entries, bad), long=True)


async def periodic_tick(bot):
    now = time.time()
    for k in list(data["chats"]):
        c = cfg(k)
        p = c.get("periodic")
        if not p or now - p.get("last", 0) < p["every"] * 60:
            continue
        p["last"] = now
        touch()
        cid = int(k)
        if p.get("mid"):
            try:
                await bot.delete_message(cid, p["mid"])
            except Exception:
                pass
        try:
            title = (await bot.get_chat(cid)).title or ""
            txt = (html.escape(p.get("text", "")).replace("{group}", html.escape(title))
                   .replace("{rules}", html.escape(c["rules"])))
            msg = await send_media(bot, cid, p.get("media"), txt, make_markup(c["periodic_btns"]))
            p["mid"] = msg.message_id
        except Exception as e:
            log.warning("periodic send failed: %s", e)


async def periodic_loop(app):
    while True:
        await asyncio.sleep(30)
        if loaded:
            await periodic_tick(app.bot)

# =====================================================================
#  أوامر الإشراف
# =====================================================================
def remember(u):
    """يحفظ يوزر -> معرّف لكل من يتكلم أو ينضم (يُستخدم لحظر @يوزر بسرعة)."""
    if u and getattr(u, "username", None):
        k = u.username.lower()
        names = data.setdefault("unames", {})
        if names.get(k) != u.id and (k in names or len(names) < 50000):
            names[k] = u.id
            touch()


async def find_user(ctx, uname):
    """يحوّل @يوزر إلى (معرّف، اسم): 1) ذاكرة البوت 2) MTProto عبر Telethon (أي يوزر عام) 3) Bot API."""
    uname = uname.lstrip("@").lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,31}", uname):
        return None
    uid = data.get("unames", {}).get(uname)
    if uid:
        return uid, "@" + uname
    if TL:
        try:
            ent = await asyncio.wait_for(TL.get_entity("@" + uname), 15)
            if isinstance(ent, TLUser):
                name = " ".join(x for x in (ent.first_name, ent.last_name) if x) or "@" + uname
                data.setdefault("unames", {})[uname] = ent.id
                touch()
                return ent.id, name
        except Exception as e:
            log.info("telethon resolve failed for %s: %s", uname, e)
    try:
        ch = await ctx.bot.get_chat("@" + uname)
        if ch.type == "private":
            return ch.id, ch.full_name or "@" + uname
    except Exception:
        pass
    return None


async def resolve(update, ctx, reply):
    m, cid = update.effective_message, update.effective_chat.id
    args = list(ctx.args)
    if not (m.reply_to_message and m.reply_to_message.from_user) and args and \
            (args[0].startswith("@") or "t.me/" in args[0]):
        uname = args[0].rstrip("/").split("/")[-1].lstrip("@")
        f = await find_user(ctx, uname)
        if not f:
            await reply(tr(cid, "user_none"))
            return None
        return f[0], f[1], args[1:]
    if m.reply_to_message and m.reply_to_message.from_user:
        u = m.reply_to_message.from_user
        return u.id, u.full_name, args
    if args and args[0].isdigit():
        uid = int(args[0])
        return uid, await name_of(ctx, cid, uid), args[1:]
    await reply(tr(cid, "need_target"))
    return None


async def mod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m, chat, me = update.effective_message, update.effective_chat, update.effective_user
    cid = chat.id
    reply = make_reply(ctx, cid)
    await try_delete(m)  # حذف رسالة الأمر تلقائيًا
    if not await is_admin(ctx, cid, me.id):
        return
    cmd = m.text.split()[0][1:].split("@")[0].lower()
    if cmd == "del":
        if m.reply_to_message:
            for x in (m.reply_to_message, m):
                try:
                    await x.delete()
                except Exception:
                    pass
        return
    r = await resolve(update, ctx, reply)
    if not r:
        return
    uid, name, rest = r
    if uid == ctx.bot.id:
        return
    ment = mention_id(uid, name)
    c = cfg(cid)
    if cmd in ("ban", "kick", "mute", "warn") and await is_admin(ctx, cid, uid):
        return await reply(tr(cid, "is_admin"))
    try:
        if cmd == "warns":
            await reply(tr(cid, "warns", user=ment, n=warns_of(cid, uid), max=c["max_warns"]), parse_mode="HTML")
        elif cmd in ("resetwarns", "reset"):
            set_warns(cid, uid, 0)
            await reply(tr(cid, "reset", user=ment, admin=mention(me)), parse_mode="HTML")
        elif cmd == "unwarn":
            set_warns(cid, uid, warns_of(cid, uid) - 1)
            await reply(tr(cid, "warns", user=ment, n=warns_of(cid, uid), max=c["max_warns"]), parse_mode="HTML")
        elif cmd == "unmute":
            await do_unmute(ctx, cid, uid)
            await reply(tr(cid, "unmuted", user=ment, admin=mention(me)), parse_mode="HTML")
        elif cmd == "unban":
            await ctx.bot.unban_chat_member(cid, uid, only_if_banned=True)
            await reply(tr(cid, "unbanned", user=ment, admin=mention(me)), parse_mode="HTML")
        elif cmd == "kick":
            await ctx.bot.ban_chat_member(cid, uid)
            await ctx.bot.unban_chat_member(cid, uid, only_if_banned=True)
            await reply(tr(cid, "kicked", user=ment), parse_mode="HTML")
        elif cmd == "ban":
            reason = html.escape(" ".join(rest)) or tr(cid, "r_admin")
            await ctx.bot.ban_chat_member(cid, uid)
            await reply(tr(cid, "banned", user=ment, reason=reason), parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup([[btn(cid, "b_unban", f"ub:{uid}")]]))
        elif cmd == "mute":
            dur = 60
            if rest and parse_dur(rest[0]) is not None:
                dur = parse_dur(rest[0]) or 60
                rest = rest[1:]
            reason = html.escape(" ".join(rest)) or tr(cid, "r_admin")
            await do_mute(ctx, cid, uid, dur)
            await reply(tr(cid, "mutedu", user=ment, dur=fmt_dur(cid, dur), reason=reason), parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup([[btn(cid, "b_unmute", f"um:{uid}")]]))
        elif cmd == "warn":
            reason = html.escape(" ".join(rest)) or tr(cid, "r_admin")
            await punish(ctx, cid, uid, name, reason, 0)
    except Exception as e:
        await reply(tr(cid, "fail", err=str(e)[:200]))


# =====================================================================
#  الإعدادات
# =====================================================================
def panel(cid):
    c = cfg(cid)
    text = tr(cid, "set_info", mw=c["max_warns"], fn=c["flood_n"], fs=c["flood_s"], sm=c["spam_mute"])
    items = list(LANGS.items())
    rows = [[InlineKeyboardButton(("✓ " if c["lang"] == k else "") + n, callback_data="lg:" + k)
             for k, n in items[i:i + 2]] for i in range(0, len(items), 2)]
    tg = [InlineKeyboardButton(("✅ " if c[k] else "❌ ") + tr(cid, "s_" + k), callback_data="tg:" + k) for k in TOG]
    rows += [tg[i:i + 2] for i in range(0, len(tg), 2)]
    rows.append([InlineKeyboardButton("➖", callback_data="mw:-"),
                 InlineKeyboardButton(f"⚠️ {c['max_warns']}", callback_data="mw:0"),
                 InlineKeyboardButton("➕", callback_data="mw:+")])
    return text, InlineKeyboardMarkup(rows)


async def conf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m, chat, me = update.effective_message, update.effective_chat, update.effective_user
    cid = chat.id
    reply = make_reply(ctx, cid)
    await try_delete(m)  # حذف رسالة الأمر تلقائيًا
    cmd = m.text.split()[0][1:].split("@")[0].lower()
    if cmd == "help":
        return await reply(tr(cid, "help"), long=True)
    if cmd == "about":
        return await reply(CREDIT)
    if cmd == "rules":
        r = cfg(cid)["rules"]
        return await reply(tr(cid, "rules_title", rules=r) if r else tr(cid, "no_rules"), long=True)
    if not await is_admin(ctx, cid, me.id):
        return
    c = cfg(cid)
    a = ctx.args
    parts = m.text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    def usage(u):
        return reply(tr(cid, "usage", u=u))

    if cmd in ("settings", "lang"):
        t, kb = panel(cid)
        return await reply(t, reply_markup=kb, keep=False, ttl=300)
    if cmd == "addword":
        entries, bad = parse_entries(body, c["word_mute"])
        if not entries:
            return await usage("/addword word 60m")
        c["banned"].update(entries)
        touch()
        return await reply(words_summary(cid, entries, bad), long=True)
    if cmd == "delword":
        ws = [norm(x) for x in re.split(r"[\n,،;؛]+", body) if x.strip()]
        gone = [w for w in ws if c["banned"].pop(w, None) is not None]
        if not gone:
            return await reply(tr(cid, "w_none"))
        touch()
        return await reply(tr(cid, "w_del", w="، ".join(gone)))
    if cmd == "clearwords":
        n = len(c["banned"])
        if not n:
            return await reply(tr(cid, "no_words"))
        c["banned"].clear()
        touch()
        return await reply(tr(cid, "words_cleared", n=n))
    if cmd == "setcaptcha":
        if a and a[0].lower() == "off":
            c["captcha"] = False
            touch()
            return await reply(tr(cid, "cap_off"))
        if not (a and a[0].isdigit() and 15 <= int(a[0]) <= 900):
            return await usage("/setcaptcha 120  |  /setcaptcha off")
        c["captcha"], c["captcha_time"] = True, int(a[0])
        touch()
        return await reply(tr(cid, "cap_set", sec=int(a[0])))
    if cmd == "setwarnaction":
        if not (a and a[0].lower() in ("ban", "kick", "mute")):
            return await usage("/setwarnaction ban  |  kick  |  mute 1d")
        c["warn_action"] = a[0].lower()
        if c["warn_action"] == "mute" and len(a) > 1 and parse_dur(a[1]):
            c["warn_dur"] = parse_dur(a[1])
        touch()
        return await reply(tr(cid, "warns_set", n=c["max_warns"], act=c["warn_action"]))
    if cmd == "setwordmute":
        d = parse_dur(a[0]) if a else None
        if d is None:
            return await usage("/setwordmute 60m")
        c["word_mute"] = d
        touch()
        return await reply(tr(cid, "ok"))
    if cmd == "setautodel":
        if not (a and (a[0].isdigit() or a[0].lower() == "off")):
            return await usage("/setautodel 30  |  /setautodel off")
        c["ttl"] = 0 if a[0].lower() == "off" else min(int(a[0]), 3600)
        touch()
        return await reply(tr(cid, "ok"))
    if cmd == "setperiodic":
        if a and a[0].lower() == "off":
            c["periodic"] = None
            touch()
            return await reply(tr(cid, "periodic_off"))
        d = parse_dur(a[0]) if a else None
        if d is None or d < 5:
            return await usage("/setperiodic 2h text  |  /setperiodic off")
        sp = body.split(None, 1)
        rest = sp[1].strip() if len(sp) > 1 else ""
        rm = m.reply_to_message
        media = media_of(rm) if rm else None
        text = rest or ((rm.text or rm.caption or "") if rm else "")
        if not text and not media:
            return await usage("/setperiodic 2h text  |  /setperiodic off")
        c["periodic"] = {"every": d, "text": text, "media": media, "last": 0, "mid": None}
        touch()
        return await reply(tr(cid, "periodic_set", every=fmt_dur(cid, d)))
    if cmd == "words":
        if not c["banned"]:
            return await reply(tr(cid, "no_words"))
        lines = [f"• {w} — {fmt_dur(cid, v) if v else tr(cid, 'w_warnonly')}" for w, v in c["banned"].items()]
        chunks, cur = [], ""
        for ln in lines:
            if len(cur) + len(ln) + 1 > 3300:
                chunks.append(cur)
                cur = ""
            cur += ln + "\n"
        chunks.append(cur)
        for ch in chunks:
            await reply(tr(cid, "words", list=ch.rstrip()), long=True)
        return
    if cmd in ("allow", "disallow"):
        if not a:
            if not c["allow"]:
                return await reply(tr(cid, "no_domains"))
            return await reply(tr(cid, "domains", list="\n".join("• " + d for d in c["allow"])), long=True)
        d = (urlparse(a[0] if "://" in a[0] else "http://" + a[0]).hostname or "").lower().removeprefix("www.")
        if not d:
            return await usage(f"/{cmd} example.com")
        if cmd == "allow" and d not in c["allow"]:
            c["allow"].append(d)
        if cmd == "disallow" and d in c["allow"]:
            c["allow"].remove(d)
        touch()
        return await reply(tr(cid, "d_add" if cmd == "allow" else "d_del", d=d))
    if cmd == "setrules":
        if not body:
            return await usage("/setrules text  |  /setrules off")
        if body.lower() == "off":
            c["rules"] = ""
            touch()
            return await reply(tr(cid, "rules_off"))
        c["rules"] = body[:3000]
        touch()
        return await reply(tr(cid, "rules_set"))
    if cmd in ("setwelcomebuttons", "setbyebuttons", "setperiodicbuttons"):
        key = {"setwelcomebuttons": "welcome_btns", "setbyebuttons": "bye_btns",
               "setperiodicbuttons": "periodic_btns"}[cmd]
        if body.lower() == "off":
            c[key] = []
            touch()
            return await reply(tr(cid, "btns_off"))
        rows, bad = parse_btns(body)
        if not rows:
            return await usage(f"/{cmd}\nنص الزر | https://t.me/xxx\nزر1 | https://a.com && زر2 | https://b.com")
        c[key] = rows
        touch()
        txt = tr(cid, "btns_set", n=sum(len(r) for r in rows))
        if bad:
            txt += "\n" + tr(cid, "words_bad", n=bad)
        return await reply(txt)
    if cmd == "setchatlink":
        link = body.strip()
        if link.lower() == "off":
            c["chat_link"] = ""
            touch()
            return await reply(tr(cid, "link_off"))
        if link.startswith("@"):
            link = "https://t.me/" + link[1:]
        elif link.startswith(("t.me/", "www.")):
            link = "https://" + link
        if not re.fullmatch(r"https?://\S+", link):
            return await usage("/setchatlink https://t.me/xxx  |  /setchatlink off")
        c["chat_link"] = link
        touch()
        return await reply(tr(cid, "link_set"))
    if cmd in ("setwelcome", "setbye"):
        key = "welcome_text" if cmd == "setwelcome" else "bye_text"
        if not body:
            return await usage(f"/{cmd} text  |  /{cmd} default")
        if body.lower() == "default":
            c[key] = ""
            touch()
            return await reply(tr(cid, "text_def"))
        c[key] = body
        touch()
        return await reply(tr(cid, "text_set"))
    if cmd in ("setwelcomemedia", "setbyemedia"):
        key = "welcome_media" if cmd == "setwelcomemedia" else "bye_media"
        if a and a[0].lower() == "off":
            c[key] = None
            touch()
            return await reply(tr(cid, "media_off"))
        md = media_of(m.reply_to_message) if m.reply_to_message else None
        if not md:
            return await reply(tr(cid, "media_need"))
        c[key] = md
        touch()
        return await reply(tr(cid, "media_set"))
    if cmd == "setwarns":
        if not (a and a[0].isdigit() and 1 <= int(a[0]) <= 50):
            return await usage("/setwarns 3  (1-50)")
        c["max_warns"] = int(a[0])
        touch()
        return await reply(tr(cid, "warns_set", n=c["max_warns"], act=c.get("warn_action", "ban")))
    if cmd == "setspam":
        if len(a) != 3 or not all(x.isdigit() for x in a) or int(a[0]) < 3 or int(a[1]) < 1:
            return await usage("/setspam 6 8 10")
        c["flood_n"], c["flood_s"], c["spam_mute"] = int(a[0]), int(a[1]), int(a[2])
        touch()
        return await reply(tr(cid, "ok"))


async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q.message:
        return await q.answer()
    cid = q.message.chat.id
    if q.data.startswith("cp:"):
        return await captcha_press(q, ctx)
    if not await is_admin(ctx, cid, q.from_user.id):
        return await q.answer(tr(cid, "adm_only"), show_alert=True)
    act, _, arg = q.data.partition(":")
    try:
        if act in ("tg", "lg", "mw"):
            c = cfg(cid)
            if act == "mw" and arg in ("+", "-"):
                c["max_warns"] = max(1, min(50, c["max_warns"] + (1 if arg == "+" else -1)))
            if act == "tg" and arg in TOG:
                c[arg] = not c[arg]
            if act == "lg" and arg in LANGS:
                c["lang"] = arg
            touch()
            t, kb = panel(cid)
            await q.edit_message_text(t, reply_markup=kb)
            return await q.answer()
        uid = int(arg)
        ment = mention_id(uid, await name_of(ctx, cid, uid))
        admin = mention(q.from_user)
        if act == "um":
            await do_unmute(ctx, cid, uid)
            note = tr(cid, "unmuted", user=ment, admin=admin)
        elif act == "ub":
            await ctx.bot.unban_chat_member(cid, uid, only_if_banned=True)
            note = tr(cid, "unbanned", user=ment, admin=admin)
        else:
            set_warns(cid, uid, 0)
            note = tr(cid, "reset", user=ment, admin=admin)
        rows = [[b for b in row if b.callback_data != q.data] for row in q.message.reply_markup.inline_keyboard]
        rows = [r for r in rows if r]
        markup = InlineKeyboardMarkup(rows) if rows else None
        if q.message.text:
            await q.edit_message_text(q.message.text_html + "\n\n" + note, parse_mode="HTML", reply_markup=markup)
        else:
            await q.edit_message_caption((q.message.caption_html or "") + "\n\n" + note, parse_mode="HTML",
                                         reply_markup=markup)
        await q.answer()
    except Exception as e:
        log.warning("button failed: %s", e)
        await q.answer(str(e)[:150], show_alert=True)


# =====================================================================
#  المحادثة الخاصة
# =====================================================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    arg = ctx.args[0] if ctx.args else ""
    if re.fullmatch(r"r\d+", arg):  # رابط «استلم القوانين في الخاص»
        cid = -int(arg[1:])
        if str(cid) in data["chats"] and cfg(cid)["rules"]:
            try:
                title = (await ctx.bot.get_chat(cid)).title or ""
            except Exception:
                title = ""
            return await m.reply_text(tr(cid, "rules_dm", group=title, rules=cfg(cid)["rules"]))
    await m.reply_text(tr(None, "start"))


async def get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    fid = (m.photo[-1].file_id if m.photo else m.animation.file_id if m.animation
           else m.video.file_id if m.video else m.sticker.file_id if m.sticker else None)
    if fid:
        await m.reply_text(f"file_id:\n\n{fid}")


async def on_error(update, ctx: ContextTypes.DEFAULT_TYPE):
    log.warning("error: %s", ctx.error)


async def start_tl():
    global TL
    if not (TelegramClient and API_ID and API_HASH):
        log.warning("Telethon/API_ID/API_HASH missing: @username lookup limited to users the bot has seen")
        return
    try:
        cl = TelegramClient(StringSession(), int(API_ID), API_HASH)
        await cl.start(bot_token=TOKEN)
        TL = cl
        log.info("telethon ready")
    except Exception as e:
        log.error("telethon start failed: %s", e)


async def post_init(app):
    await start_tl()
    for _ in range(5):
        await asyncio.to_thread(load)
        if loaded:
            break
        await asyncio.sleep(3)
    asyncio.create_task(saver())
    asyncio.create_task(periodic_loop(app))


async def post_shutdown(app):
    if TL:
        try:
            await TL.disconnect()
        except Exception:
            pass
    if loaded:
        await asyncio.to_thread(save, json.dumps(data, ensure_ascii=False, indent=1))


G = filters.ChatType.GROUPS
app = Application.builder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
app.add_error_handler(on_error)
app.add_handler(CommandHandler("start", start, filters.ChatType.PRIVATE))
app.add_handler(MessageHandler(G & (filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER), service))
app.add_handler(ChatMemberHandler(member_update, ChatMemberHandler.CHAT_MEMBER))
app.add_handler(ChatMemberHandler(my_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
app.add_handler(CommandHandler(["ban", "unban", "kick", "mute", "unmute", "warn", "unwarn", "resetwarns",
                                "reset", "warns", "del"], mod, G))
app.add_handler(CommandHandler(["settings", "lang", "help", "addword", "delword", "words", "allow", "disallow",
                                "setwelcome", "setbye", "setwelcomemedia", "setbyemedia", "setwarns", "setspam", "about", "rules", "setrules", "setwordmute", "setautodel",
                                "setperiodic", "setwelcomebuttons", "setbyebuttons", "setperiodicbuttons", "setchatlink",
                                "clearwords", "setcaptcha", "setwarnaction"],
                               conf, G))
app.add_handler(MessageHandler(G & filters.Document.ALL & filters.CaptionRegex(r"^/addword(@\w+)?(\s|$)"), addword_file))
app.add_handler(CallbackQueryHandler(buttons, pattern=r"^(um|ub|rw|tg|lg|mw|cp):"))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.ANIMATION | filters.VIDEO |
                                                           filters.Sticker.ALL), get_id))
app.add_handler(MessageHandler(G & ~filters.COMMAND & ~filters.StatusUpdate.ALL, guard), group=1)
app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
