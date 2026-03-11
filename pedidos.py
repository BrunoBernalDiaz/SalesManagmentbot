from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
import database as db

# Estados crear
(SEL_NEGOCIO, SEL_CLIENTE, BUSCAR_CLIENTE, AGREGAR_PRODUCTOS,
 SEL_PRODUCTO, CANTIDAD, CONFIRMAR) = range(7)

# Estados gestionar
(G_LISTAR, G_SEL_PEDIDO, G_SEL_ACCION, G_NUEVO_ESTADO) = range(7, 11)

ESTADOS_PEDIDO = ["pendiente", "confirmado", "entregado", "cancelado"]
ESTADOS_EMOJI = {
    "pendiente": "🕐",
    "confirmado": "✅",
    "entregado": "📦",
    "cancelado": "❌"
}


def _resumen_pedido(pedido_id):
    p = db.pedido_get(pedido_id)
    items = db.pedido_items_get(pedido_id)
    texto = (
        f"🧾 *Pedido #{p['id']}*\n"
        f"Cliente: {p['cliente_nombre']}\n"
        f"Negocio: {p['negocio_nombre']}\n"
        f"Estado: {ESTADOS_EMOJI.get(p['estado'], '')} {p['estado']}\n\n"
        f"*Productos:*\n"
    )
    for it in items:
        subtotal = it["cantidad"] * it["precio_unit"]
        texto += f"  • {it['producto_nombre']} x{it['cantidad']} = {subtotal:.2f}\n"
    texto += f"\n*Total: {p['total']:.2f}*"
    return texto


# ─── CREAR PEDIDO ─────────────────────────────────────────────────────────────

async def nuevo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    negocios = db.negocio_listar()
    if not negocios:
        await update.message.reply_text("No hay negocios. Crea uno con /nuevo_negocio.")
        return ConversationHandler.END
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(n["nombre"], callback_data=f"ped_neg_{n['id']}")] for n in negocios]
    )
    await update.message.reply_text("¿De qué negocio es el pedido?", reply_markup=keyboard)
    return SEL_NEGOCIO


async def sel_negocio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nid = int(query.data.split("_")[-1])
    context.user_data["ped_neg"] = nid
    await query.edit_message_text(
        "¿Buscar cliente existente o crear nuevo?\n"
        "Escribe el nombre o número para buscar, o /nuevo_cliente_rapido para crearlo."
    )
    return BUSCAR_CLIENTE


async def buscar_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    resultados = db.cliente_buscar(texto)
    if not resultados:
        await update.message.reply_text(
            "No encontré ese cliente. Escribe otro nombre o /nuevo_cliente_rapido."
        )
        return BUSCAR_CLIENTE
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"{c['nombre']} {c['telefono'] or ''}", callback_data=f"ped_cli_{c['id']}")]
         for c in resultados]
    )
    await update.message.reply_text("Selecciona el cliente:", reply_markup=keyboard)
    return SEL_CLIENTE


async def nuevo_cliente_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¿Nombre del nuevo cliente?")
    context.user_data["ped_modo_cli"] = "rapido"
    return SEL_CLIENTE


async def sel_cliente_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("ped_modo_cli") == "rapido":
        nombre = update.message.text.strip()
        cid = db.cliente_crear(nombre)
        context.user_data["ped_cli"] = cid
        context.user_data.pop("ped_modo_cli")
        return await _iniciar_productos(update, context)
    return BUSCAR_CLIENTE


async def sel_cliente_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    context.user_data["ped_cli"] = cid
    # Crear pedido en BD
    pid = db.pedido_crear(cid, context.user_data["ped_neg"])
    context.user_data["ped_id"] = pid
    await query.edit_message_text("Pedido iniciado. Ahora agrega productos.")
    return await _mostrar_productos(query, context)


async def _iniciar_productos(update, context):
    cid = context.user_data["ped_cli"]
    nid = context.user_data["ped_neg"]
    pid = db.pedido_crear(cid, nid)
    context.user_data["ped_id"] = pid
    await update.message.reply_text("Pedido iniciado. Ahora agrega productos.")
    return await _mostrar_productos(update, context)


async def _mostrar_productos(obj, context):
    nid = context.user_data["ped_neg"]
    pid = context.user_data["ped_id"]
    productos = db.producto_listar(nid)
    productos_con_stock = [p for p in productos if p["stock"] > 0]

    items_actuales = db.pedido_items_get(pid)
    resumen = ""
    if items_actuales:
        resumen = "\n*En el pedido:*\n"
        for it in items_actuales:
            resumen += f"  • {it['producto_nombre']} x{it['cantidad']}\n"

    if not productos_con_stock:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirmar pedido", callback_data="ped_confirmar")],
            [InlineKeyboardButton("❌ Cancelar pedido", callback_data="ped_cancelar_todo")],
        ])
        msg = f"No hay más productos con stock.{resumen}"
        if hasattr(obj, "edit_message_text"):
            await obj.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await obj.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
        return CONFIRMAR

    keyboard_rows = [
        [InlineKeyboardButton(
            f"{p['nombre']} ({p['stock']} disp.) — {p['precio_venta']:.2f}",
            callback_data=f"ped_prod_{p['id']}"
        )] for p in productos_con_stock
    ]
    keyboard_rows.append([InlineKeyboardButton("✅ Confirmar pedido", callback_data="ped_confirmar")])
    keyboard_rows.append([InlineKeyboardButton("❌ Cancelar pedido", callback_data="ped_cancelar_todo")])

    msg = f"Agrega productos al pedido:{resumen}"
    if hasattr(obj, "edit_message_text"):
        await obj.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode="Markdown")
    else:
        await obj.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode="Markdown")
    return AGREGAR_PRODUCTOS


async def sel_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[-1])
    context.user_data["ped_prod_sel"] = prod_id
    p = db.producto_get(prod_id)
    await query.edit_message_text(f"¿Cuántas unidades de *{p['nombre']}*? (máx {p['stock']})",
                                  parse_mode="Markdown")
    return CANTIDAD


async def cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cant = int(update.message.text.strip())
        if cant <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Escribe un número entero positivo.")
        return CANTIDAD

    pid = context.user_data["ped_id"]
    prod_id = context.user_data["ped_prod_sel"]
    p = db.producto_get(prod_id)

    if cant > p["stock"]:
        await update.message.reply_text(f"Solo hay {p['stock']} en stock. Escribe otro número.")
        return CANTIDAD

    db.pedido_agregar_item(pid, prod_id, cant)
    await update.message.reply_text(f"Agregado: *{p['nombre']}* x{cant}", parse_mode="Markdown")
    return await _mostrar_productos(update, context)


async def confirmar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = context.user_data["ped_id"]
    items = db.pedido_items_get(pid)

    if not items:
        await query.edit_message_text("El pedido está vacío. Agrega productos primero.")
        return await _mostrar_productos(query, context)

    resumen = _resumen_pedido(pid)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Sí, guardar", callback_data="ped_guardar")],
        [InlineKeyboardButton("✏️ Seguir editando", callback_data="ped_seguir")],
    ])
    await query.edit_message_text(resumen + "\n\n¿Confirmas el pedido?",
                                  reply_markup=keyboard, parse_mode="Markdown")
    return CONFIRMAR


async def guardar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = context.user_data.pop("ped_id")
    context.user_data.pop("ped_neg", None)
    context.user_data.pop("ped_cli", None)
    await query.edit_message_text(
        f"✅ Pedido #{pid} guardado en estado *pendiente*.\n"
        f"Usa /gestionar_pedidos para cambiar su estado.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancelar_pedido_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = context.user_data.pop("ped_id", None)
    if pid:
        db.pedido_cambiar_estado(pid, "cancelado")
    context.user_data.pop("ped_neg", None)
    context.user_data.pop("ped_cli", None)
    await query.edit_message_text("Pedido cancelado.")
    return ConversationHandler.END


# ─── GESTIONAR PEDIDOS ────────────────────────────────────────────────────────

async def gestionar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    negocios = db.negocio_listar()
    keyboard = [
        [InlineKeyboardButton("Todos los negocios", callback_data="gped_neg_0")],
    ] + [
        [InlineKeyboardButton(n["nombre"], callback_data=f"gped_neg_{n['id']}")] for n in negocios
    ]
    await update.message.reply_text("¿De qué negocio ver los pedidos?",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    return G_LISTAR


async def gestionar_listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nid = int(query.data.split("_")[-1]) or None
    context.user_data["gped_neg"] = nid

    estados_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{ESTADOS_EMOJI[e]} {e}", callback_data=f"gped_est_{e}")] for e in ESTADOS_PEDIDO
    ] + [[InlineKeyboardButton("Todos", callback_data="gped_est_todos")]])

    await query.edit_message_text("¿Filtrar por estado?", reply_markup=estados_keyboard)
    return G_SEL_PEDIDO


async def gestionar_sel_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    estado = query.data.split("_")[-1]
    if estado == "todos":
        estado = None
    nid = context.user_data.get("gped_neg")
    pedidos = db.pedido_listar(negocio_id=nid, estado=estado, limite=15)

    if not pedidos:
        await query.edit_message_text("No hay pedidos con ese filtro.")
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"#{p['id']} {ESTADOS_EMOJI.get(p['estado'],'')} {p['cliente_nombre']} — {p['total']:.2f}",
            callback_data=f"gped_p_{p['id']}"
        )] for p in pedidos
    ])
    await query.edit_message_text("Selecciona un pedido:", reply_markup=keyboard)
    return G_SEL_PEDIDO


async def gestionar_sel_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    context.user_data["gped_pid"] = pid
    resumen = _resumen_pedido(pid)
    p = db.pedido_get(pid)

    opciones_estado = [e for e in ESTADOS_PEDIDO if e != p["estado"]]
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"→ {ESTADOS_EMOJI[e]} {e}", callback_data=f"gped_cambiar_{e}")]
         for e in opciones_estado]
    )
    await query.edit_message_text(resumen + "\n\n¿Cambiar estado?",
                                  reply_markup=keyboard, parse_mode="Markdown")
    return G_SEL_ACCION


async def gestionar_cambiar_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nuevo_estado = query.data.split("_")[-1]
    pid = context.user_data["gped_pid"]
    db.pedido_cambiar_estado(pid, nuevo_estado)
    await query.edit_message_text(
        f"✅ Pedido #{pid} → *{nuevo_estado}* {ESTADOS_EMOJI.get(nuevo_estado,'')}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# ─── CONVERSATION HANDLERS ───────────────────────────────────────────────────

def conv_nuevo():
    return ConversationHandler(
        entry_points=[CommandHandler("nuevo_pedido", nuevo_start)],
        states={
            SEL_NEGOCIO:      [CallbackQueryHandler(sel_negocio, pattern=r"^ped_neg_\d+$")],
            BUSCAR_CLIENTE:   [
                MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_cliente),
                CommandHandler("nuevo_cliente_rapido", nuevo_cliente_rapido),
            ],
            SEL_CLIENTE:      [
                CallbackQueryHandler(sel_cliente_cb, pattern=r"^ped_cli_\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sel_cliente_rapido),
            ],
            AGREGAR_PRODUCTOS: [
                CallbackQueryHandler(sel_producto, pattern=r"^ped_prod_\d+$"),
                CallbackQueryHandler(confirmar_pedido, pattern=r"^ped_confirmar$"),
                CallbackQueryHandler(cancelar_pedido_todo, pattern=r"^ped_cancelar_todo$"),
            ],
            CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, cantidad)],
            CONFIRMAR: [
                CallbackQueryHandler(guardar_pedido, pattern=r"^ped_guardar$"),
                CallbackQueryHandler(cancelar_pedido_todo, pattern=r"^ped_cancelar_todo$"),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )


def conv_gestionar():
    return ConversationHandler(
        entry_points=[CommandHandler("gestionar_pedidos", gestionar_start)],
        states={
            G_LISTAR:     [CallbackQueryHandler(gestionar_listar, pattern=r"^gped_neg_\d+$")],
            G_SEL_PEDIDO: [
                CallbackQueryHandler(gestionar_sel_estado, pattern=r"^gped_est_"),
                CallbackQueryHandler(gestionar_sel_pedido, pattern=r"^gped_p_\d+$"),
            ],
            G_SEL_ACCION: [CallbackQueryHandler(gestionar_cambiar_estado, pattern=r"^gped_cambiar_")],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

