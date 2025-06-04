import json
import re
import time
import asyncio
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,       # ← aggiunto qui
    filters,
    ContextTypes,
    ConversationHandler
)
from concurrent.futures import ThreadPoolExecutor
import subprocess

BOT_TOKEN = "7878367599:AAGHIvYFy8ngzqRc-DJoikc4XxozC3WzqwY"
FILE_JSON = "utenti.json"
SCELTA_RUOLO, INSERISCI_PASSWORD, OPERATIVO = range(3)
SEMAPHORE = asyncio.Semaphore(10)
TIMEOUT = 40

def carica_utenti():
    try:
        with open(FILE_JSON) as f:
            return json.load(f)
    except:
        return {}

def salva_utente(uid, ruolo):
    u = carica_utenti()
    u[str(uid)] = {'ruolo': ruolo, 'verificato': True}
    with open(FILE_JSON, 'w') as f:
        json.dump(u, f, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton('Agente', callback_data='agente')],
        [InlineKeyboardButton('Cliente', callback_data='cliente')],
        [InlineKeyboardButton('Seller', callback_data='seller')],
        [InlineKeyboardButton('Admin', callback_data='admin')],
    ]
    msg = update.message or update.callback_query.message
    await msg.reply_text('Seleziona il tuo ruolo:', reply_markup=InlineKeyboardMarkup(kb))
    return SCELTA_RUOLO

async def ruolo_sel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ruolo = q.data
    context.user_data['ruolo'] = ruolo
    if ruolo in ['agente','seller','admin']:
        kb = [[InlineKeyboardButton('🔙 Indietro', callback_data='back')]]
        await q.edit_message_text(f'Inserisci password per {ruolo}:', reply_markup=InlineKeyboardMarkup(kb))
        return INSERISCI_PASSWORD
    else:
        salva_utente(q.from_user.id, ruolo)
        await q.edit_message_text('Accesso come cliente ✅')
        return OPERATIVO

async def pw_ins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip().lower()
    if t == 'back':
        return await start(update, context)
    r = context.user_data['ruolo']
    if t == {'agente':'147','seller':'369','admin':'190503'}.get(r):
        salva_utente(update.effective_user.id, r)
        await update.message.reply_text(f'Accesso {r}')
        return OPERATIVO
    await update.message.reply_text('❌ Password errata')
    return INSERISCI_PASSWORD

async def bg_scrape(chat_id, msg_id, ordine, ruolo, bot):
    await asyncio.sleep(0)  # cede il controllo
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, 'estrattore.py', ordine, ruolo,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        if err:
            txt = f'❌ Errore: {err.decode().strip()}'
        else:
            data = json.loads(out.decode())
            txt = '\n'.join(f'🔹 {k}: {v}' for k, v in data.items())
        await bot.edit_message_text(txt, chat_id, msg_id)
    except asyncio.TimeoutError:
        await bot.edit_message_text('⏱️ Timeout', chat_id, msg_id)
    finally:
        SEMAPHORE.release()

async def gestisci_ordine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ordine = update.message.text.strip()
    if not re.match(r"^\d{3}-\d{7}-\d{7}$", ordine):
        await update.message.reply_text('❌ Formato non valido.')
        return
    u = carica_utenti().get(str(update.effective_user.id))
    if not u:
        await update.message.reply_text('❌ Usa /start')
        return
    if SEMAPHORE.locked():
        await update.message.reply_text('⚠️ Tutte le sessioni sono occupate.')
        return
    await SEMAPHORE.acquire()
    msg = await update.message.reply_text('🔍 Elaborazione...')
    # avvia il subprocess in background
    context.application.create_task(
        bg_scrape(msg.chat_id, msg.message_id, ordine, u['ruolo'], context.bot)
    )
    return OPERATIVO

async def cambia_ruolo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = carica_utenti()
    u.pop(str(update.effective_user.id), None)
    with open(FILE_JSON, 'w') as f:
        json.dump(u, f, indent=2)
    await update.message.reply_text('🔁 Ruolo cancellato')
    return await start(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SCELTA_RUOLO: [CallbackQueryHandler(ruolo_sel)],
            INSERISCI_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pw_ins),
                CallbackQueryHandler(start, pattern='^back$')
            ],
            OPERATIVO: [MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_ordine)]
        },
        fallbacks=[CommandHandler('cambia_ruolo', cambia_ruolo)]
    )
    app.add_handler(conv)
    print("🤖 Bot avviato")
    app.run_polling()

if __name__ == '__main__':
    main()
