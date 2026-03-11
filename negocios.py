from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
import database as db

# Estados
(NOMBRE, CONTACTO,
 EDIT_SELECT_CAMPO, EDIT_NOMBRE, EDIT_CONTACTO) = range(5)

# ─── LISTAR ──────────────────────────────────────────────────────────────────

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    negocios = db.negocio_listar(solo_activos=False)
    if not negocios:
        await update.message.reply_text("No hay negocios registrados. Usa /nuevo_negocio para agregar uno.")
        return

    texto = "🏢 *Negocios registrados:*\n\n"
    for n in negocios:
        estado = "✅" if n["activo"] else "❌"
        contacto = n["contacto"] or "—"
        texto += f"{estado} [{n['id']}] *{n['nombre']}*\n   Contacto: {contacto}\n\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


# ─── CREAR ───────────────────────────────────────────────────────────────────

async def nuevo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¿Nombre del negocio?")
    return NOMBRE


async def nuevo_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["neg_nombre"] = update.message.text.strip()
    await update.message.reply_text(
        "¿Número de contacto del negocio? (Envía /saltar si no tienes)"
    )
    return CONTACTO


async def nuevo_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contacto = update.message.text.strip()
    _finalizar_crear(update, context, contacto)
    return ConversationHandler.END


async def nuevo_saltar_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _finalizar_crear(update, context, None)
    return ConversationHandler.END


def _finalizar_crear(update, context, contacto):
    nombre = context.user_data.pop("neg_nombre")
    nid = db.negocio_crear(nombre, contacto)
    import asyncio
    asyncio.ensure_future(
        update.message.reply_text(f"✅ Negocio *{nombre}* creado con ID `{nid}`.", parse_mode="Markdown")
    )


# ─── EDITAR ──────────────────────────────────────────────────────────────────

async def editar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    negocios = db.negocio_listar()
    if not negocios:
        await update.message.reply_text("No hay negocios activos.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(f"{n['nombre']}", callback_data=f"negcio_edit_{n['id']}")] for n in negocios]
    await update.message.reply_text("¿Qué negocio quieres editar?",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_SELECT_CAMPO


async def editar_seleccionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    negocio_id = int(query.data.split("_")[-1])
    context.user_data["neg_edit_id"] = negocio_id
    n = db.negocio_get(negocio_id)

    keyboard = [
        [InlineKeyboardButton("Nombre", callback_data="negcio_campo_nombre")],
        [InlineKeyboardButton("Contacto", callback_data="negcio_campo_contacto")],
        [InlineKeyboardButton("Activar/Desactivar", callback_data="negcio_campo_toggle")],
    ]
    await query.edit_message_text(
        f"Editando: *{n['nombre']}*\n¿Qué campo modificas?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return EDIT_SELECT_CAMPO


async def editar_campo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    campo = query.data.split("_")[-1]

    if campo == "toggle":
        nid = context.user_data["neg_edit_id"]
        db.negocio_toggle_activo(nid)
        n = db.negocio_get(nid)
        estado = "activado ✅" if n["activo"] else "desactivado ❌"
        await query.edit_message_text(f"Negocio *{n['nombre']}* {estado}.", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["neg_edit_campo"] = campo
    prompts = {"nombre": "Nuevo nombre:", "contacto": "Nuevo contacto:"}
    await query.edit_message_text(prompts[campo])
    return EDIT_NOMBRE if campo == "nombre" else EDIT_CONTACTO


async def editar_guardar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()
    nid = context.user_data["neg_edit_id"]
    campo = context.user_data["neg_edit_campo"]
    kwargs = {campo: valor}
    db.negocio_editar(nid, **kwargs)
    await update.message.reply_text(f"✅ Campo *{campo}* actualizado.", parse_mode="Markdown")
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# ─── CONVERSATION HANDLERS ───────────────────────────────────────────────────

def conv_nuevo():
    return ConversationHandler(
        entry_points=[CommandHandler("nuevo_negocio", nuevo_start)],
        states={
            NOMBRE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_nombre)],
            CONTACTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_contacto),
                CommandHandler("saltar", nuevo_saltar_contacto),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )


def conv_editar():
    return ConversationHandler(
        entry_points=[CommandHandler("editar_negocio", editar_start)],
        states={
            EDIT_SELECT_CAMPO: [
                CallbackQueryHandler(editar_seleccionar, pattern=r"^negcio_edit_\d+$"),
                CallbackQueryHandler(editar_campo_callback, pattern=r"^negcio_campo_"),
            ],
            EDIT_NOMBRE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_guardar)],
            EDIT_CONTACTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_guardar)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

