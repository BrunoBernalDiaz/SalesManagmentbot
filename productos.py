from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
import database as db

# Estados crear
(SEL_NEGOCIO, NOMBRE, PRECIO_COMPRA, PRECIO_VENTA, STOCK, CATEGORIA) = range(6)
# Estados editar
(E_SEL_NEGOCIO, E_SEL_PRODUCTO, E_SEL_CAMPO,
 E_NOMBRE, E_PRECIO_COMPRA, E_PRECIO_VENTA, E_STOCK, E_CATEGORIA) = range(6, 14)


def _teclado_negocios(prefix):
    negocios = db.negocio_listar()
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(n["nombre"], callback_data=f"{prefix}{n['id']}")] for n in negocios]
    )


# ─── LISTAR STOCK ─────────────────────────────────────────────────────────────

async def stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    negocios = db.negocio_listar()
    if not negocios:
        await update.message.reply_text("No hay negocios activos.")
        return
    keyboard = _teclado_negocios("stk_neg_")
    await update.message.reply_text("¿De qué negocio ves el stock?", reply_markup=keyboard)


async def stock_mostrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nid = int(query.data.split("_")[-1])
    productos = db.producto_listar(nid, solo_activos=False)
    negocio = db.negocio_get(nid)

    if not productos:
        await query.edit_message_text(f"No hay productos en *{negocio['nombre']}*.", parse_mode="Markdown")
        return

    texto = f"📦 *Stock — {negocio['nombre']}*\n\n"
    for p in productos:
        estado = "✅" if p["activo"] else "❌"
        margen = p["precio_venta"] - p["precio_compra"]
        texto += (
            f"{estado} [{p['id']}] *{p['nombre']}*\n"
            f"   Compra: {p['precio_compra']:.2f} | Venta: {p['precio_venta']:.2f} | Margen: {margen:.2f}\n"
            f"   Stock: {p['stock']} uds"
            + (f" | Cat: {p['categoria']}" if p["categoria"] else "")
            + "\n\n"
        )
    await query.edit_message_text(texto, parse_mode="Markdown")


# ─── CREAR PRODUCTO ───────────────────────────────────────────────────────────

async def nuevo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    negocios = db.negocio_listar()
    if not negocios:
        await update.message.reply_text("Primero agrega un negocio con /nuevo_negocio.")
        return ConversationHandler.END
    await update.message.reply_text("¿A qué negocio pertenece el producto?",
                                    reply_markup=_teclado_negocios("prod_neg_"))
    return SEL_NEGOCIO


async def nuevo_negocio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["prod_neg"] = int(query.data.split("_")[-1])
    await query.edit_message_text("¿Nombre del producto?")
    return NOMBRE


async def nuevo_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prod_nombre"] = update.message.text.strip()
    await update.message.reply_text("¿Precio de compra (lo que te cuesta)?")
    return PRECIO_COMPRA


async def nuevo_precio_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["prod_pcompra"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Escribe un número válido, ej: 150 o 150.50")
        return PRECIO_COMPRA
    await update.message.reply_text("¿Precio de venta?")
    return PRECIO_VENTA


async def nuevo_precio_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["prod_pventa"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Escribe un número válido.")
        return PRECIO_VENTA
    await update.message.reply_text("¿Stock inicial? (cantidad disponible ahora)")
    return STOCK


async def nuevo_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["prod_stock"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Escribe un número entero, ej: 10")
        return STOCK
    await update.message.reply_text("¿Categoría? (Envía /saltar si no aplica)")
    return CATEGORIA


async def nuevo_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categoria = update.message.text.strip()
    await _finalizar_crear(update, context, categoria)
    return ConversationHandler.END


async def nuevo_saltar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _finalizar_crear(update, context, None)
    return ConversationHandler.END


async def _finalizar_crear(update, context, categoria):
    d = context.user_data
    pid = db.producto_crear(
        negocio_id=d.pop("prod_neg"),
        nombre=d.pop("prod_nombre"),
        precio_compra=d.pop("prod_pcompra"),
        precio_venta=d.pop("prod_pventa"),
        stock=d.pop("prod_stock"),
        categoria=categoria
    )
    await update.message.reply_text(f"✅ Producto creado con ID `{pid}`.", parse_mode="Markdown")


# ─── EDITAR PRODUCTO ──────────────────────────────────────────────────────────

async def editar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    negocios = db.negocio_listar()
    if not negocios:
        await update.message.reply_text("No hay negocios activos.")
        return ConversationHandler.END
    await update.message.reply_text("¿De qué negocio es el producto?",
                                    reply_markup=_teclado_negocios("eprod_neg_"))
    return E_SEL_NEGOCIO


async def editar_sel_negocio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nid = int(query.data.split("_")[-1])
    context.user_data["eprod_neg"] = nid
    productos = db.producto_listar(nid, solo_activos=False)
    if not productos:
        await query.edit_message_text("Este negocio no tiene productos.")
        return ConversationHandler.END
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"{p['nombre']} (stock:{p['stock']})", callback_data=f"eprod_p_{p['id']}")]
         for p in productos]
    )
    await query.edit_message_text("¿Qué producto editas?", reply_markup=keyboard)
    return E_SEL_PRODUCTO


async def editar_sel_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    context.user_data["eprod_id"] = pid
    p = db.producto_get(pid)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Nombre", callback_data="eprod_c_nombre")],
        [InlineKeyboardButton("Precio compra", callback_data="eprod_c_precio_compra")],
        [InlineKeyboardButton("Precio venta", callback_data="eprod_c_precio_venta")],
        [InlineKeyboardButton("Stock (ajuste manual)", callback_data="eprod_c_stock")],
        [InlineKeyboardButton("Categoría", callback_data="eprod_c_categoria")],
        [InlineKeyboardButton("Activar/Desactivar", callback_data="eprod_c_toggle")],
    ])
    margen = p["precio_venta"] - p["precio_compra"]
    await query.edit_message_text(
        f"*{p['nombre']}*\nCompra: {p['precio_compra']} | Venta: {p['precio_venta']} | Margen: {margen:.2f}\n"
        f"Stock: {p['stock']} | Cat: {p['categoria'] or '—'}\n\n¿Qué campo modificas?",
        reply_markup=keyboard, parse_mode="Markdown"
    )
    return E_SEL_CAMPO


CAMPO_ESTADO_MAP = {
    "nombre": E_NOMBRE,
    "precio_compra": E_PRECIO_COMPRA,
    "precio_venta": E_PRECIO_VENTA,
    "stock": E_STOCK,
    "categoria": E_CATEGORIA,
}

CAMPO_PROMPT = {
    "nombre": "Nuevo nombre:",
    "precio_compra": "Nuevo precio de compra:",
    "precio_venta": "Nuevo precio de venta:",
    "stock": "Nuevo stock absoluto (reemplaza el actual):",
    "categoria": "Nueva categoría:",
}


async def editar_campo_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    campo = query.data[len("eprod_c_"):]

    if campo == "toggle":
        pid = context.user_data["eprod_id"]
        db.producto_toggle_activo(pid)
        p = db.producto_get(pid)
        estado = "activado ✅" if p["activo"] else "desactivado ❌"
        await query.edit_message_text(f"Producto *{p['nombre']}* {estado}.", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["eprod_campo"] = campo
    await query.edit_message_text(CAMPO_PROMPT[campo])
    return CAMPO_ESTADO_MAP[campo]


async def editar_guardar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()
    campo = context.user_data["eprod_campo"]
    pid = context.user_data["eprod_id"]

    if campo in ("precio_compra", "precio_venta"):
        try:
            valor = float(valor.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Escribe un número válido.")
            return CAMPO_ESTADO_MAP[campo]
    elif campo == "stock":
        try:
            valor = int(valor)
        except ValueError:
            await update.message.reply_text("Escribe un número entero.")
            return E_STOCK

    db.producto_editar(pid, **{campo: valor})
    await update.message.reply_text(f"✅ *{campo}* actualizado.", parse_mode="Markdown")
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# ─── CONVERSATION HANDLERS ───────────────────────────────────────────────────

def conv_nuevo():
    return ConversationHandler(
        entry_points=[CommandHandler("nuevo_producto", nuevo_start)],
        states={
            SEL_NEGOCIO:  [CallbackQueryHandler(nuevo_negocio, pattern=r"^prod_neg_\d+$")],
            NOMBRE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_nombre)],
            PRECIO_COMPRA:[MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_precio_compra)],
            PRECIO_VENTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_precio_venta)],
            STOCK:        [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_stock)],
            CATEGORIA:    [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_categoria),
                CommandHandler("saltar", nuevo_saltar_categoria),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )


def conv_editar():
    text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, editar_guardar_texto)
    return ConversationHandler(
        entry_points=[CommandHandler("editar_producto", editar_start)],
        states={
            E_SEL_NEGOCIO:  [CallbackQueryHandler(editar_sel_negocio, pattern=r"^eprod_neg_\d+$")],
            E_SEL_PRODUCTO: [CallbackQueryHandler(editar_sel_producto, pattern=r"^eprod_p_\d+$")],
            E_SEL_CAMPO:    [CallbackQueryHandler(editar_campo_cb, pattern=r"^eprod_c_")],
            E_NOMBRE:        [text_handler],
            E_PRECIO_COMPRA: [text_handler],
            E_PRECIO_VENTA:  [text_handler],
            E_STOCK:         [text_handler],
            E_CATEGORIA:     [text_handler],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )


def cb_stock_handler():
    """Handler suelto para el botón de ver stock (no es conversación)."""
    return [
        CommandHandler("stock", stock_start),
        CallbackQueryHandler(stock_mostrar, pattern=r"^stk_neg_\d+$"),
    ]

