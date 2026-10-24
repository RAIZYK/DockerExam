
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis import Redis


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://marketuser:marketpass@localhost:5432/marketdb",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

cache: Optional[Redis] = None


def connect():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=5,
    )


def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'Other',
                price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
                stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                customer_name TEXT NOT NULL,
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                total NUMERIC(10, 2) NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        count = conn.execute(
            "SELECT COUNT(*) AS n FROM products"
        ).fetchone()["n"]

        if count == 0:
            products = [
                (
                    "Mechanical Keyboard",
                    "Compact keyboard for everyday work",
                    "Accessories",
                    59.99,
                    18,
                ),
                (
                    "Wireless Mouse",
                    "Ergonomic wireless mouse",
                    "Accessories",
                    24.50,
                    35,
                ),
                (
                    "USB-C Hub",
                    "Six-port hub for laptops",
                    "Electronics",
                    39.00,
                    12,
                ),
                (
                    "Desk Lamp",
                    "LED lamp with adjustable brightness",
                    "Home",
                    31.25,
                    9,
                ),
            ]

            # executemany belongs to the cursor, not the connection.
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO products
                        (name, description, category, price, stock)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    products,
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache

    last_error = None

    for _ in range(20):
        try:
            init_db()

            cache = Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            cache.ping()
            break

        except Exception as exc:
            last_error = exc

            if cache is not None:
                try:
                    cache.close()
                except Exception:
                    pass
                cache = None

            time.sleep(2)

    else:
        raise RuntimeError(
            f"Could not connect to database/cache: {last_error}"
        )

    yield

    if cache is not None:
        cache.close()


app = FastAPI(
    title="MarketDock API",
    description="Demo shop API with PostgreSQL and Redis",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    category: str = "Other"
    price: float = Field(ge=0)
    stock: int = Field(ge=0)


class OrderIn(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    product_id: int
    quantity: int = Field(gt=0, le=100)


@app.get("/")
def root():
    return {
        "app": "MarketDock",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")

    if cache is None:
        raise HTTPException(503, "Redis is not initialized")

    cache.ping()

    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
    }


@app.get("/products")
def list_products(
    category: Optional[str] = None,
    q: Optional[str] = None,
):
    if cache is None:
        raise HTTPException(503, "Redis is not initialized")

    cache_key = f"products:{category or '*'}:{q or '*'}"
    cached = cache.get(cache_key)

    if cached:
        return {
            "items": json.loads(cached),
            "cached": True,
        }

    sql = """
        SELECT id, name, description, category, price, stock, created_at
        FROM products
        WHERE 1=1
    """
    params = []

    if category:
        sql += " AND category = %s"
        params.append(category)

    if q:
        sql += " AND (name ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])

    sql += " ORDER BY id"

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []

    for row in rows:
        item = dict(row)
        item["price"] = float(item["price"])
        item["created_at"] = item["created_at"].isoformat()
        result.append(item)

    cache.setex(cache_key, 30, json.dumps(result))

    return {
        "items": result,
        "cached": False,
    }


@app.post("/products", status_code=201)
def create_product(product: ProductIn):
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO products
                (name, description, category, price, stock)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                product.name,
                product.description,
                product.category,
                product.price,
                product.stock,
            ),
        ).fetchone()

    if cache is not None:
        keys = list(cache.scan_iter(match="products:*"))
        if keys:
            cache.delete(*keys)

    return dict(row)


@app.get("/categories")
def categories():
    with connect() as conn:
        rows = conn.execute("""
            SELECT category, COUNT(*) AS product_count
            FROM products
            GROUP BY category
            ORDER BY category
        """).fetchall()

    return {"items": [dict(row) for row in rows]}


@app.post("/orders", status_code=201)
def create_order(order: OrderIn):
    with connect() as conn:
        with conn.transaction():
            product = conn.execute(
                "SELECT * FROM products WHERE id = %s FOR UPDATE",
                (order.product_id,),
            ).fetchone()

            if not product:
                raise HTTPException(404, "Product not found")

            if product["stock"] < order.quantity:
                raise HTTPException(400, "Not enough stock")

            total = float(product["price"]) * order.quantity

            conn.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s",
                (order.quantity, order.product_id),
            )

            row = conn.execute(
                """
                INSERT INTO orders
                    (customer_name, product_id, quantity, total)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (
                    order.customer_name,
                    order.product_id,
                    order.quantity,
                    total,
                ),
            ).fetchone()

    if cache is not None:
        cache.flushdb()

    return dict(row)


@app.get("/orders")
def list_orders():
    with connect() as conn:
        rows = conn.execute("""
            SELECT
                o.id,
                o.customer_name,
                o.product_id,
                p.name AS product_name,
                o.quantity,
                o.total,
                o.status,
                o.created_at
            FROM orders o
            JOIN products p ON p.id = o.product_id
            ORDER BY o.id DESC
        """).fetchall()

    return {"items": [dict(row) for row in rows]}


@app.get("/admin/stats")
def admin_stats():
    with connect() as conn:
        products = conn.execute("""
            SELECT
                COUNT(*) AS count,
                COALESCE(SUM(stock), 0) AS stock
            FROM products
        """).fetchone()

        orders = conn.execute("""
            SELECT
                COUNT(*) AS count,
                COALESCE(SUM(total), 0) AS revenue
            FROM orders
        """).fetchone()

    return {
        "products_count": products["count"],
        "items_in_stock": products["stock"],
        "orders_count": orders["count"],
        "revenue": float(orders["revenue"]),
    }
