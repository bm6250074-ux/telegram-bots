import os, re, json, time, html, base64, asyncio, logging
import urllib.request, urllib.error
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)

TOKEN = os.environ["BOT_TOKEN"]
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
    "welcome_text": "", "bye_text": "",
    "welcome_media": None, "bye_media": None,
    "banned": {},   # كلمة -> مدة الكتم بالدقائق (0 = حذف وتحذير فقط)