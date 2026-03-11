import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import database as db
from handlers import negocios, productos, clientes, pedidos, reportes

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Falta BOT_TOKEN en variables de entorno")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "👋 *SalesGestor*\n\n"
        "*Negocios*\n"
        "/nuevo\\_negocio — Registrar negocio\n"
        "/editar\\_negocio — Editar/activar negocio\n"
        "/negocios — Ver todos\n\n"
        "*Productos*\n"
        "/nuevo\\_producto — Agregar producto\n"
        "/editar\\_producto — Editar precio/stock/etc\n"
        "/stock — Ver catálogo con stock\n\n"
        "*Clientes*\n"
        "/nuevo\\_cliente — Registrar cliente\n"
        "/editar\\_cliente — Editar cliente\n"
        "/clientes — Ver todos\n\n"
        "*Pedidos*\n"
        "/nuevo\\_pedido — Crear pedido\n"
        "/gestionar\\_pedidos — Ver y cambiar estado\n\n"
        "*Reportes*\n"
        "/reporte — Ventas y ganancia por negocio\n\n"
        "Escribe /cancelar en cualquier momento para salir de un flujo."
    )
    await update.message.reply_text(texto, parse_mode="Markdown")


def main():
    db.init_db()
    logger.info("Base de datos inicializada.")

    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos base
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("negocios", negocios.listar))
    app.add_handler(CommandHandler("clientes", clientes.listar))

    # ConversationHandlers — negocios
    app.add_handler(negocios.conv_nuevo())
    app.add_handler(negocios.conv_editar())

    # ConversationHandlers — productos
    app.add_handler(productos.conv_nuevo())
    app.add_handler(productos.conv_editar())
    for h in productos.cb_stock_handler():
        app.add_handler(h)

    # ConversationHandlers — clientes
    app.add_handler(clientes.conv_nuevo())
    app.add_handler(clientes.conv_editar())

    # ConversationHandlers — pedidos
    app.add_handler(pedidos.conv_nuevo())
    app.add_handler(pedidos.conv_gestionar())

    # Reportes
    for h in reportes.handlers():
        app.add_handler(h)

    logger.info("Bot iniciado en modo polling.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
