from telegram import Update, File
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler, ContextTypes
import os
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")  # Use environment variable for security
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set this to your Render public URL

app = ApplicationBuilder().token(TOKEN).build()

# Flask app for handling webhooks
flask_app = Flask(__name__)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    await app.process_update(update)
    return "OK", 200

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a file to convert!")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure the downloads directory exists
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    file = None
    file_name = None

    # Handle documents
    if update.message.document:
        file = await update.message.document.get_file()
        file_name = update.message.document.file_name
    # Handle images
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()  # Get the highest resolution photo
        file_name = f"photo_{update.message.photo[-1].file_unique_id}.jpg"

    if file and file_name:
        file_path = f"downloads/{file_name}"
        await file.download_to_drive(file_path)

        context.user_data['file_path'] = file_path
        await update.message.reply_text(f"File received: {file_path}\nTo which format do you want to convert? (e.g., 'jpg', 'docx')")
    else:
        await update.message.reply_text("Unsupported file type. Please send a document or an image.")

async def handle_conversion_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_path = context.user_data.get('file_path')
    if not file_path:
        await update.message.reply_text("Please send a file first.")
        return

    target_format = update.message.text.lower()
    converted_path = f"{os.path.splitext(file_path)[0]}.{target_format}"

    # Notify the user that conversion is in progress
    await update.message.reply_text("Conversion in progress. Please wait...")

    # --- Add logic based on format ---
    if file_path.endswith('.pdf') and target_format == 'docx':
        from pdf2docx import Converter
        cv = Converter(file_path)
        cv.convert(converted_path)
        cv.close()
    elif file_path.endswith(('.png', '.jpg', '.jpeg', 'webp')) and target_format in ['png', 'jpg', 'webp', 'jpeg']:
        from PIL import Image
        img = Image.open(file_path)
        img.save(converted_path)
    else:
        await update.message.reply_text("Unsupported format or conversion.")
        return

    try:
        await update.message.reply_document(document=open(converted_path, 'rb'))
    except FileNotFoundError:
        await update.message.reply_text("An error occurred during the conversion. The converted file could not be found.")
        return

    # Safely remove the specific files
    for path in [file_path, converted_path]:
        try:
            os.remove(path)
        except FileNotFoundError:
            print(f"File not found for deletion: {path}")

# Add your existing handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_conversion_format))

if __name__ == "__main__":
    # Set the webhook
    app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))