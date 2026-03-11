from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from datetime import datetime, timedelta
import database as db


def _rango(opcion):
    hoy = datetime.now()
    if opcion == "hoy":
        desde = hoy.strftime("%Y-%m-%d 00:00:00")
        hasta = hoy.strftime("%Y-%m-%d 23:59:59")
    elif opcion == "semana":
        lunes = hoy - timedelta(days=hoy.weekday())
        desde = lunes.strftime("%Y-%m-%d 00:00:00")
        hasta = hoy.strftime("%Y-%m-%d 23:59:59")
    elif opcion == "mes":
        desde = hoy.strftime("%Y-%m-01 00:00:00")
        hasta = hoy.strftime("%Y-%m-%d 23:59:59")
    else:  # total
        desde = None
        hasta = None
    return desde, hasta


async def reporte_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hoy", callback_data="rep_hoy")],
        [InlineKeyboardButton("📆 Esta semana", callback_data="rep_semana")],
        [InlineKeyboardButton("🗓 Este mes", callback_data="rep_mes")],
        [InlineKeyboardButton("📊 Total histórico", callback_data="rep_total")],
    ])
    await update.message.reply_text("¿Qué período quieres ver?", reply_markup=keyboard)


async def reporte_mostrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    periodo = query.data.split("_")[-1]
    desde, hasta = _rango(periodo)

    datos = db.reporte_por_negocio(desde, hasta)

    if not datos:
        await query.edit_message_text("No hay ventas registradas en ese período.")
        return

    labels = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes", "total": "Total histórico"}
    texto = f"📊 *Reporte — {labels[periodo]}*\n\n"

    total_ventas = 0
    total_ganancia = 0

    for row in datos:
        ventas = row["ventas"] or 0
        costo = row["costo"] or 0
        ganancia = ventas - costo
        total_ventas += ventas
        total_ganancia += ganancia
        margen_pct = (ganancia / ventas * 100) if ventas > 0 else 0

        texto += (
            f"🏢 *{row['negocio']}*\n"
            f"   Pedidos: {row['total_pedidos']}\n"
            f"   Ventas:  {ventas:.2f}\n"
            f"   Costo:   {costo:.2f}\n"
            f"   Ganancia: *{ganancia:.2f}* ({margen_pct:.1f}%)\n\n"
        )

    texto += f"─────────────\n*Total ventas: {total_ventas:.2f}*\n*Total ganancia: {total_ganancia:.2f}*"
    await query.edit_message_text(texto, parse_mode="Markdown")


def handlers():
    return [
        CommandHandler("reporte", reporte_start),
        CallbackQueryHandler(reporte_mostrar, pattern=r"^rep_"),
    ]

