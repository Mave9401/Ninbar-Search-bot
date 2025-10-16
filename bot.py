import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler
)
from pymongo import MongoClient

# --- VARIABILI D’AMBIENTE ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHANNELS = os.getenv("CHANNELS").split(",") if os.getenv("CHANNELS") else []
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- DATABASE ---
client = MongoClient(MONGO_URI)
db = client["NinbarDB"]
files_collection = db["files"]

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Ciao {user.first_name}! 👋\n\n"
        "Sono il tuo bot di ricerca file 🔍\n"
        "Scrivi il nome del file che vuoi cercare."
    )

# --- Salva messaggi dei canali nel DB ---
async def save_channel_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message or not message.document:
        return

    file_name = message.document.file_name
    file_id = message.document.file_id

    # Salva nel database se non esiste già
    if not files_collection.find_one({"file_id": file_id}):
        files_collection.insert_one({
            "file_id": file_id,
            "file_name": file_name,
            "channel_id": message.chat_id,
            "message_id": message.message_id
        })

# --- Ricerca file ---
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        return

    results = list(files_collection.find({"file_name": {"$regex": query, "$options": "i"}}).limit(10))

    if not results:
        await update.message.reply_text("❌ Nessun file trovato.")
        return

    buttons = []
    for f in results:
        buttons.append(
            [InlineKeyboardButton(f["file_name"], callback_data=f['file_id'])]
        )

    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("📂 Risultati:", reply_markup=reply_markup)

# --- Invia file quando clicchi ---
async def send_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_id = query.data
    file = files_collection.find_one({"file_id": file_id})
    if not file:
        await query.message.reply_text("⚠️ File non trovato nel database.")
        return
    await query.message.reply_document(file_id)

# --- MAIN ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Comandi
    app.add_handler(CommandHandler("start", start))

    # Riceve messaggi da canali (solo se il bot è admin)
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.CHANNEL, save_channel_file))

    # Ricerca
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(send_file))

    print("✅ Bot avviato correttamente!")
    app.run_polling()

if __name__ == "__main__":
    main()
