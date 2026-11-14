import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = "9143382402:AAE53HEfxCXYT85ytZ2bFdoFI93IvZX1zUg"
ADMIN_ID = 8101223043
CHANNEL_ID = -1004400634832  # Siparişlerin düşeceği kanal ID'si

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ---------------- VERİTABANI BAŞLANGICI ----------------
def db_init():
    conn = sqlite3.connect("magaza.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS urunler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            fiyat INTEGER NOT NULL,
            aciklama TEXT,
            stok INTEGER DEFAULT 10
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS siparisler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            urun_adi TEXT,
            fiyat INTEGER,
            tarih DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def get_or_create_user(user_id: int):
    conn = sqlite3.connect("magaza.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
    conn.close()

# ---------------- ANA MENÜ ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id)
    
    msg = (
        "🌟 **Dijital Ödeme ve Ürün Mağazası**\n\n"
        f"👤 Hoş Geldin, **{user.first_name}**\n\n"
        "Aşağıdaki menüden aktif ürünleri inceleyebilir ve **Telegram Stars (⭐)** ile güvenle satın alabilirsiniz:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Ürün Kataloğu (/katalog)", callback_data="katalog")],
        [InlineKeyboardButton("📦 Siparişlerim (/siparislerim)", callback_data="siparislerim")],
        [InlineKeyboardButton("ℹ️ Yardım (/yardim)", callback_data="yardim")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

# ---------------- YÖNETİCİ: TEK KOMUTLA ÜRÜN & ÖDEME OLUŞTURMA ----------------
async def odeme_al_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanmaya yetkiniz yok!")
        return

    text_args = " ".join(context.args)
    parcalar = [p.strip() for p in text_args.split("|")]

    if len(parcalar) != 3:
        await update.message.reply_text(
            "❌ **Hatalı Kullanım!**\n\n"
            "Doğru format:\n"
            "`/odemeal Ürün Adı | Açıklama | Fiyat`\n\n"
            "Örnek:\n"
            "`/odemeal batu | aa | 50`",
            parse_mode="Markdown"
        )
        return

    ad, aciklama, fiyat_str = parcalar[0], parcalar[1], parcalar[2]

    try:
        fiyat = int(fiyat_str)
    except ValueError:
        await update.message.reply_text("❌ Fiyat kısmı sadece sayı (yıldız miktarı) olmalıdır!")
        return

    # Veritabanına kaydet
    conn = sqlite3.connect("magaza.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO urunler (ad, fiyat, aciklama, stok) VALUES (?, ?, ?, ?)", (ad, fiyat, aciklama, 10))
    urun_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Kullanıcılara gönderilecek ödeme mesajı
    mesaj = (
        "🛍️ **Yeni Ürün / Ödeme İsteği**\n\n"
        f"🔹 **Ürün:** {ad}\n"
        f"📝 **Açıklama:** {aciklama}\n"
        f"⭐ **Fiyat:** {fiyat} Yıldız\n\n"
        "Satın almak için aşağıdaki butona tıklayabilirsiniz:"
    )
    keyboard = [[InlineKeyboardButton(f"⭐ Yıldız ile Satın Al ({fiyat} Yıldız)", callback_data=f"satin_{urun_id}")]]
    
    await update.message.reply_text(f"✅ Ürün veritabanına eklendi ve ID'si `{urun_id}` oldu.\nMüşteriler için hazırlanan ödeme paneli aşağıdadır:", parse_mode="Markdown")
    await update.message.reply_text(mesaj, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ---------------- KATALOG & ÖDEME İŞLEMLERİ ----------------
async def katalog_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
    
    conn = sqlite3.connect("magaza.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, ad, fiyat, aciklama, stok FROM urunler")
    urunler = cursor.fetchall()
    conn.close()

    keyboard = []
    if not urunler:
        keyboard.append([InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="anamenu")])
        text = "❌ Mağazada şu anda aktif ürün bulunmamaktadır."
        if update.callback_query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "🛍️ **Ürün Kataloğu**\n\nSatın almak istediğiniz ürüne tıklayın:\n"
    for u in urunler:
        urun_id, ad, fiyat, aciklama, stok = u
        if stok > 0:
            keyboard.append([InlineKeyboardButton(f"📦 {ad} — ⭐ {fiyat} Yıldız", callback_data=f"detay_{urun_id}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {ad} (TÜKENDİ)", callback_data=f"tukendi_{urun_id}")])

    keyboard.append([InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="anamenu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def urun_detay_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("tukendi_"):
        await query.answer("❌ Üzgünüz, bu ürünün stoğu tükenmiştir!", show_alert=True)
        return

    urun_id = int(query.data.split("_")[1])
    conn = sqlite3.connect("magaza.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ad, fiyat, aciklama, stok FROM urunler WHERE id = ?", (urun_id,))
    urun = cursor.fetchone()
    conn.close()

    if not urun:
        await query.answer("Ürün bulunamadı!", show_alert=True)
        return

    ad, fiyat, aciklama, stok = urun
    text = (
        "📦 **Ürün Detayı**\n\n"
        f"🔹 **Ürün Adı:** {ad}\n"
        f"⭐ **Fiyat:** {fiyat} Yıldız\n"
        f"📦 **Kalan Stok:** {stok}\n"
        f"ℹ️ **Açıklama:** {aciklama}\n"
    )

    keyboard = [
        [InlineKeyboardButton(f"⭐ Yıldız ile Satın Al ({fiyat} Yıldız)", callback_data=f"satin_{urun_id}")],
        [InlineKeyboardButton("🔙 Kataloğa Dön", callback_data="katalog")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def yildiz_fatura_gonder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    urun_id = int(query.data.split("_")[1])
    conn = sqlite3.connect("magaza.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ad, fiyat, stok FROM urunler WHERE id = ?", (urun_id,))
    urun = cursor.fetchone()
    conn.close()

    if not urun:
        await query.answer("Ürün bulunamadı!", show_alert=True)
        return

    ad, fiyat, stok = urun
    if stok <= 0:
        await query.answer("❌ Üzgünüz, bu ürünün stoğu tükenmiştir!", show_alert=True)
        return

    title = f"Ürün: {ad}"
    description = f"{ad} dijital ürünü satın alımı."
    payload = f"urun_satin_alim_{urun_id}"
    currency = "XTR"
    prices = [LabeledPrice(ad, fiyat)]

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency=currency,
        prices=prices,
    )

async def pre_checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    
    if payload.startswith("urun_satin_alim_"):
        urun_id = int(payload.split("_")[3])
        user = update.effective_user
        user_id = user.id

        conn = sqlite3.connect("magaza.db")
        cursor = conn.cursor()
        cursor.execute("SELECT ad, fiyat FROM urunler WHERE id = ?", (urun_id,))
        urun = cursor.fetchone()

        if urun:
            ad, fiyat = urun
            cursor.execute("UPDATE urunler SET stok = stok - 1 WHERE id = ?", (urun_id,))
            cursor.execute("INSERT INTO siparisler (user_id, urun_adi, fiyat) VALUES (?, ?, ?)", (user_id, ad, fiyat))
            cursor.connection.commit()
            
            # Veritabanından eklenen siparişin tarihini al
            cursor.execute("SELECT tarih FROM siparisler WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            siparis_tarih = cursor.fetchone()[0]

            # Kanala "Sipariş Var!" mesajı gönder
            try:
                kanal_mesaji = (
                    "🚨 **YENİ SİPARİŞ VAR!** 📦\n\n"
                    f"👤 **Müşteri:** {user.full_name} (@{user.username or 'Kullanıcı adı yok'})\n"
                    f"🆔 **Kullanıcı ID:** `{user_id}`\n"
                    f"🛍️ **Ürün:** {ad}\n"
                    f"⭐ **Tutar:** {fiyat} Yıldız\n"
                    f"📅 **Tarih:** {siparis_tarih}"
                )
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=kanal_mesaji,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Kanala mesaj gönderilemedi: {e}")

        conn.close()
        
        # Kullanıcıya başarı mesajı gönder
        await update.message.reply_text(
            "🎉 **Ödeme Başarıyla Tamamlandı!**\n\n"
            f"📦 Ürün Adı: **{ad}**\n"
            "✅ Ödemeniz Telegram Yıldızları ile alındı. Ürününüz hesabınıza tanımlandı!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ana Menü", callback_data="anamenu")]])
        )

# ---------------- SİPARİŞ GEÇMİŞİ ----------------
async def siparislerim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    conn = sqlite3.connect("magaza.db")
    cursor = conn.cursor()
    cursor.execute("SELECT urun_adi, fiyat, tarih FROM siparisler WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    siparisler = cursor.fetchall()
    conn.close()

    if not siparisler:
        text = "📦 Henüz tamamlanmış bir siparişiniz bulunmamaktadır."
    else:
        text = "📦 **Sipariş Geçmişiniz:**\n\n"
        for s in siparisler:
            text += f"🔹 **{s[0]}**\n⭐ Tutar: {s[1]} Yıldız\n📅 Tarih: {s[2]}\n-------------------\n"

    keyboard = [[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="anamenu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ---------------- YARDIM ----------------
async def yardim_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    text = (
        "ℹ️ **Yardım ve Bilgilendirme**\n\n"
        "🔹 **Nasıl Ürün Alırım?**\n"
        "Katalogdan dilediğiniz ürünü seçip Telegram Yıldızları (⭐) ile anında ödeme yaparak satın alabilirsiniz."
    )
    keyboard = [[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="anamenu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ---------------- MAIN ----------------
def main():
    db_init()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("katalog", katalog_goster))
    app.add_handler(CommandHandler("siparislerim", siparislerim))
    app.add_handler(CommandHandler("yardim", yardim_menu))
    app.add_handler(CommandHandler("odemeal", odeme_al_komutu))

    # Buton Yöneticileri
    app.add_handler(CallbackQueryHandler(start, pattern="^anamenu$"))
    app.add_handler(CallbackQueryHandler(katalog_goster, pattern="^katalog$"))
    app.add_handler(CallbackQueryHandler(urun_detay_goster, pattern="^detay_|^tukendi_"))
    app.add_handler(CallbackQueryHandler(yildiz_fatura_gonder, pattern="^satin_"))
    app.add_handler(CallbackQueryHandler(siparislerim, pattern="^siparislerim$"))
    app.add_handler(CallbackQueryHandler(yardim_menu, pattern="^yardim$"))

    # Ödeme İşleyicileri
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    print("Tek Satırlık Ödeme Botu çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
