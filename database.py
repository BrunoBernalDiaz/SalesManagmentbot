import os
import logging
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta DATABASE_URL en variables de entorno")


def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS negocios (
                    id          SERIAL PRIMARY KEY,
                    nombre      TEXT NOT NULL,
                    contacto    TEXT,
                    activo      BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS productos (
                    id             SERIAL PRIMARY KEY,
                    negocio_id     INTEGER NOT NULL REFERENCES negocios(id),
                    nombre         TEXT NOT NULL,
                    precio_compra  NUMERIC(12,2) NOT NULL DEFAULT 0,
                    precio_venta   NUMERIC(12,2) NOT NULL DEFAULT 0,
                    stock          INTEGER NOT NULL DEFAULT 0,
                    categoria      TEXT,
                    activo         BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS clientes (
                    id          SERIAL PRIMARY KEY,
                    nombre      TEXT NOT NULL,
                    telefono    TEXT,
                    notas       TEXT,
                    activo      BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS pedidos (
                    id          SERIAL PRIMARY KEY,
                    cliente_id  INTEGER NOT NULL REFERENCES clientes(id),
                    negocio_id  INTEGER NOT NULL REFERENCES negocios(id),
                    estado      TEXT NOT NULL DEFAULT 'pendiente',
                    total       NUMERIC(12,2) NOT NULL DEFAULT 0,
                    notas       TEXT,
                    fecha       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS pedido_items (
                    id              SERIAL PRIMARY KEY,
                    pedido_id       INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                    producto_id     INTEGER NOT NULL REFERENCES productos(id),
                    cantidad        INTEGER NOT NULL DEFAULT 1,
                    precio_unit     NUMERIC(12,2) NOT NULL,
                    precio_compra   NUMERIC(12,2) NOT NULL
                );
            """)
        conn.commit()
    logger.info("Tablas verificadas/creadas en PostgreSQL.")


def _fetchall(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetchone(cur):
    if cur.description is None:
        return None
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None


# ─── NEGOCIOS ────────────────────────────────────────────────────────────────

def negocio_crear(nombre, contacto=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO negocios (nombre, contacto) VALUES (%s, %s) RETURNING id",
                (nombre, contacto)
            )
            nid = cur.fetchone()[0]
        conn.commit()
    return nid


def negocio_listar(solo_activos=True):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if solo_activos:
                cur.execute("SELECT * FROM negocios WHERE activo=TRUE ORDER BY nombre")
            else:
                cur.execute("SELECT * FROM negocios ORDER BY nombre")
            return _fetchall(cur)


def negocio_get(negocio_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM negocios WHERE id=%s", (negocio_id,))
            return _fetchone(cur)


def negocio_editar(negocio_id, nombre=None, contacto=None):
    campos, valores = [], []
    if nombre is not None:
        campos.append("nombre=%s"); valores.append(nombre)
    if contacto is not None:
        campos.append("contacto=%s"); valores.append(contacto)
    if not campos:
        return
    valores.append(negocio_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE negocios SET {', '.join(campos)} WHERE id=%s", valores)
        conn.commit()


def negocio_toggle_activo(negocio_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE negocios SET activo = NOT activo WHERE id=%s", (negocio_id,))
        conn.commit()


# ─── PRODUCTOS ───────────────────────────────────────────────────────────────

def producto_crear(negocio_id, nombre, precio_compra, precio_venta, stock=0, categoria=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO productos (negocio_id, nombre, precio_compra, precio_venta, stock, categoria)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (negocio_id, nombre, precio_compra, precio_venta, stock, categoria)
            )
            pid = cur.fetchone()[0]
        conn.commit()
    return pid


def producto_listar(negocio_id, solo_activos=True):
    with get_conn() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM productos WHERE negocio_id=%s"
            params = [negocio_id]
            if solo_activos:
                q += " AND activo=TRUE"
            q += " ORDER BY nombre"
            cur.execute(q, params)
            return _fetchall(cur)


def producto_get(producto_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM productos WHERE id=%s", (producto_id,))
            return _fetchone(cur)


def producto_editar(producto_id, nombre=None, precio_compra=None, precio_venta=None,
                    stock=None, categoria=None):
    campos, valores = [], []
    if nombre is not None:
        campos.append("nombre=%s"); valores.append(nombre)
    if precio_compra is not None:
        campos.append("precio_compra=%s"); valores.append(precio_compra)
    if precio_venta is not None:
        campos.append("precio_venta=%s"); valores.append(precio_venta)
    if stock is not None:
        campos.append("stock=%s"); valores.append(stock)
    if categoria is not None:
        campos.append("categoria=%s"); valores.append(categoria)
    if not campos:
        return
    valores.append(producto_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE productos SET {', '.join(campos)} WHERE id=%s", valores)
        conn.commit()


def producto_ajustar_stock(producto_id, delta):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE productos SET stock = stock + %s WHERE id=%s",
                (delta, producto_id)
            )
        conn.commit()


def producto_toggle_activo(producto_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE productos SET activo = NOT activo WHERE id=%s", (producto_id,))
        conn.commit()


# ─── CLIENTES ────────────────────────────────────────────────────────────────

def cliente_crear(nombre, telefono=None, notas=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO clientes (nombre, telefono, notas) VALUES (%s, %s, %s) RETURNING id",
                (nombre, telefono, notas)
            )
            cid = cur.fetchone()[0]
        conn.commit()
    return cid


def cliente_listar(solo_activos=True):
    with get_conn() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM clientes"
            if solo_activos:
                q += " WHERE activo=TRUE"
            q += " ORDER BY nombre"
            cur.execute(q)
            return _fetchall(cur)


def cliente_buscar(texto):
    with get_conn() as conn:
        with conn.cursor() as cur:
            like = f"%{texto}%"
            cur.execute(
                "SELECT * FROM clientes WHERE activo=TRUE AND (nombre ILIKE %s OR telefono ILIKE %s)",
                (like, like)
            )
            return _fetchall(cur)


def cliente_get(cliente_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clientes WHERE id=%s", (cliente_id,))
            return _fetchone(cur)


def cliente_editar(cliente_id, nombre=None, telefono=None, notas=None):
    campos, valores = [], []
    if nombre is not None:
        campos.append("nombre=%s"); valores.append(nombre)
    if telefono is not None:
        campos.append("telefono=%s"); valores.append(telefono)
    if notas is not None:
        campos.append("notas=%s"); valores.append(notas)
    if not campos:
        return
    valores.append(cliente_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE clientes SET {', '.join(campos)} WHERE id=%s", valores)
        conn.commit()


def cliente_toggle_activo(cliente_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE clientes SET activo = NOT activo WHERE id=%s", (cliente_id,))
        conn.commit()


# ─── PEDIDOS ─────────────────────────────────────────────────────────────────

def pedido_crear(cliente_id, negocio_id, notas=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pedidos (cliente_id, negocio_id, notas) VALUES (%s, %s, %s) RETURNING id",
                (cliente_id, negocio_id, notas)
            )
            pid = cur.fetchone()[0]
        conn.commit()
    return pid


def pedido_agregar_item(pedido_id, producto_id, cantidad):
    p = producto_get(producto_id)
    if not p:
        raise ValueError("Producto no existe")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, cantidad FROM pedido_items WHERE pedido_id=%s AND producto_id=%s",
                (pedido_id, producto_id)
            )
            existing = _fetchone(cur)
            if existing:
                cur.execute(
                    "UPDATE pedido_items SET cantidad=%s WHERE id=%s",
                    (existing["cantidad"] + cantidad, existing["id"])
                )
            else:
                cur.execute(
                    """INSERT INTO pedido_items (pedido_id, producto_id, cantidad, precio_unit, precio_compra)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (pedido_id, producto_id, cantidad, p["precio_venta"], p["precio_compra"])
                )
            cur.execute(
                "SELECT SUM(cantidad * precio_unit) FROM pedido_items WHERE pedido_id=%s",
                (pedido_id,)
            )
            total = cur.fetchone()[0] or 0
            cur.execute("UPDATE pedidos SET total=%s WHERE id=%s", (total, pedido_id))
        conn.commit()


def pedido_quitar_item(pedido_id, item_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pedido_items WHERE id=%s AND pedido_id=%s",
                (item_id, pedido_id)
            )
            cur.execute(
                "SELECT SUM(cantidad * precio_unit) FROM pedido_items WHERE pedido_id=%s",
                (pedido_id,)
            )
            total = cur.fetchone()[0] or 0
            cur.execute("UPDATE pedidos SET total=%s WHERE id=%s", (total, pedido_id))
        conn.commit()


def pedido_cambiar_estado(pedido_id, estado):
    estados_validos = ("pendiente", "confirmado", "entregado", "cancelado")
    if estado not in estados_validos:
        raise ValueError(f"Estado inválido. Opciones: {estados_validos}")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE pedidos SET estado=%s WHERE id=%s", (estado, pedido_id))
            if estado == "confirmado":
                cur.execute(
                    "SELECT producto_id, cantidad FROM pedido_items WHERE pedido_id=%s",
                    (pedido_id,)
                )
                items = _fetchall(cur)
                for item in items:
                    cur.execute(
                        "UPDATE productos SET stock = stock - %s WHERE id=%s",
                        (item["cantidad"], item["producto_id"])
                    )
        conn.commit()


def pedido_get(pedido_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.*, c.nombre as cliente_nombre, n.nombre as negocio_nombre
                   FROM pedidos p
                   JOIN clientes c ON c.id = p.cliente_id
                   JOIN negocios n ON n.id = p.negocio_id
                   WHERE p.id=%s""",
                (pedido_id,)
            )
            return _fetchone(cur)


def pedido_items_get(pedido_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT pi.*, pr.nombre as producto_nombre
                   FROM pedido_items pi
                   JOIN productos pr ON pr.id = pi.producto_id
                   WHERE pi.pedido_id=%s""",
                (pedido_id,)
            )
            return _fetchall(cur)


def pedido_listar(negocio_id=None, estado=None, limite=20):
    with get_conn() as conn:
        with conn.cursor() as cur:
            q = """SELECT p.*, c.nombre as cliente_nombre, n.nombre as negocio_nombre
                   FROM pedidos p
                   JOIN clientes c ON c.id = p.cliente_id
                   JOIN negocios n ON n.id = p.negocio_id
                   WHERE 1=1"""
            params = []
            if negocio_id:
                q += " AND p.negocio_id=%s"; params.append(negocio_id)
            if estado:
                q += " AND p.estado=%s"; params.append(estado)
            q += " ORDER BY p.fecha DESC LIMIT %s"
            params.append(limite)
            cur.execute(q, params)
            return _fetchall(cur)


# ─── REPORTES ────────────────────────────────────────────────────────────────

def reporte_por_negocio(desde=None, hasta=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            q = """
                SELECT
                    n.nombre as negocio,
                    COUNT(DISTINCT p.id) as total_pedidos,
                    SUM(pi.cantidad * pi.precio_unit)   as ventas,
                    SUM(pi.cantidad * pi.precio_compra) as costo
                FROM pedidos p
                JOIN negocios n ON n.id = p.negocio_id
                JOIN pedido_items pi ON pi.pedido_id = p.id
                WHERE p.estado IN ('confirmado', 'entregado')
            """
            params = []
            if desde:
                q += " AND p.fecha >= %s"; params.append(desde)
            if hasta:
                q += " AND p.fecha <= %s"; params.append(hasta)
            q += " GROUP BY n.id, n.nombre ORDER BY ventas DESC"
            cur.execute(q, params)
            return _fetchall(cur)

