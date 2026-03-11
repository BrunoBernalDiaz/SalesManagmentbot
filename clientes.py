from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
import database as db

(NOMBRE, TELEFONO, NOTAS,
 E_SEL, E_CAMPO, E_NOMBRE, E_TELEFONO, E_NOTAS) = range(8)


# ─── LISTAR ──────────────────────────────────────────────────────────────────

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clientes = db.cliente_listar(solo_activos=False)
    if not clientes:
        await update.message.reply_text("No hay clientes. Usa /nuevo_cliente.")
        return
    texto = "👤 *Clientes:*\n\n"
    for c in clientes:
        estado = "✅" if c["activo"] else "❌"
        texto += f"{estado} [{c['id']}] *{c['nombre']}*  {c['telefono'] or ''}\n"
        if c["notas"]:
            texto += f"   _{c['notas']}_\n"
        texto += "\n"
    await update.message.reply_text(texto, parse_mode="Markdown")


# ─── CREAR ───────────────────────────────────────────────────────────────────

async def nuevo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¿Nombre del cliente?")
    return NOMBRE


async def nuevo_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cli_nombre"] = update.message.text.strip()
    await update.message.reply_text("¿Teléfono? (o /saltar)")
    return TELEFONO


async def nuevo_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cli_tel"] = update.message.text.strip()
    await update.message.reply_text("¿Alguna nota? (o /saltar)")
    return NOTAS


async def nuevo_notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cli_notas"] = update.message.text.strip()
    await _finalizar(update, context)
    return ConversationHandler.END


async def saltar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    estado = context.user_data.get("_conv_estado_cli", TELEFONO)
    if estado == TELEFONO:
        context.user_data["cli_tel"] = None
        await update.message.reply_text("¿Alguna nota? (o /saltar)")
        context.user_data["_conv_estado_cli"] = NOTAS
        return NOTAS
    else:
        context.user_data["cli_notas"] = None
        await _finalizar(update, context)
        return ConversationHandler.END


async def _finalizar(update, context):
    d = context.user_data
    cid = db.cliente_crear(
        nombre=d.pop("cli_nombre"),
        telefono=d.pop("cli_tel", None),
        notas=d.pop("cli_notas", None)
    )
    d.pop("_conv_estado_cli", None)
    await update.message.reply_text(f"✅ Cliente creado con ID `{cid}`.", parse_mode="Markdown")


# ─── EDITAR ──────────────────────────────────────────────────────────────────

async def editar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clientes = db.cliente_listar()
    if not clientes:
        await update.message.reply_text("No hay clientes activos.")
        return ConversationHandler.END
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"{c['nombre']}", callback_data=f"ecli_{c['id']}")] for c in clientes]
    )
    await update.message.reply_text("¿Qué cliente editas?", reply_markup=keyboard)
    return E_SEL


async def editar_sel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    context.user_data["ecli_id"] = cid
    c = db.cliente_get(cid)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Nombre", callback_data="eclic_nombre")],
        [InlineKeyboardButton("Teléfono", callback_data="eclic_telefono")],
        [InlineKeyboardButton("Notas", callback_data="eclic_notas")],
        [InlineKeyboardButton("Activar/Desactivar", callback_data="eclic_toggle")],
    ])
    await query.edit_message_text(
        f"*{c['nombre']}*  |  {c['telefono'] or '—'}\n¿Qué campo editas?",
        reply_markup=keyboard, parse_mode="Markdown"
    )
    return E_CAMPO


CAMPO_ESTADO = {"nombre": E_NOMBRE, "telefono": E_TELEFONO, "notas": E_NOTAS}
CAMPO_PROMPT = {"nombre": "Nuevo nombre:", "telefono": "Nuevo teléfono:", "notas": "Nueva nota:"}


async def editar_campo_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    campo = query.data[len("eclic_"):]

    if campo == "toggle":
        cid = context.user_data["ecli_id"]
        db.cliente_toggle_activo(cid)
        c = db.cliente_get(cid)
        estado = "activado ✅" if c["activo"] else "desactivado ❌"
        await query.edit_message_text(f"Cliente *{c['nombre']}* {estado}.", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["ecli_campo"] = campo
    await query.edit_message_text(CAMPO_PROMPT[campo])
    return CAMPO_ESTADO[campo]


async def editar_guardar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()
    campo = context.user_data["ecli_campo"]
    cid = context.user_data["ecli_id"]
    db.cliente_editar(cid, **{campo: valor})
    await update.message.reply_text(f"✅ *{campo}* actualizado.", parse_mode="Markdown")
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# ─── CONVERSATION HANDLERS ───────────────────────────────────────────────────

def conv_nuevo():
    return ConversationHandler(
        entry_points=[CommandHandler("nuevo_cliente", nuevo_start)],
        states={
            NOMBRE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_nombre)],
            TELEFONO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_telefono),
                CommandHandler("saltar", saltar),
            ],
            NOTAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_notas),
                CommandHandler("saltar", saltar),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )


def conv_editar():
    text_h = MessageHandler(filters.TEXT & ~filters.COMMAND, editar_guardar)
    return ConversationHandler(
        entry_points=[CommandHandler("editar_cliente", editar_start)],
        states={
            E_SEL:     [CallbackQueryHandler(editar_sel, pattern=r"^ecli_\d+$")],
            E_CAMPO:   [CallbackQueryHandler(editar_campo_cb, pattern=r"^eclic_")],
            E_NOMBRE:   [text_h],
            E_TELEFONO: [text_h],
            E_NOTAS:    [text_h],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
