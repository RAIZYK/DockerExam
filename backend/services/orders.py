from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .common import connect
app=FastAPI(title="MarketDock Order API", description="Order processing microservice")
class OrderIn(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    product_id: int
    quantity: int = Field(gt=0, le=100)
@app.get("/health")
def health():
    with connect() as c: c.execute("SELECT 1")
    return {"service":"order-api","status":"healthy"}
@app.get("/orders")
def orders():
    with connect() as c:
        rows=c.execute("SELECT o.id,o.customer_name,o.product_id,p.name AS product_name,o.quantity,o.total,o.status,o.created_at FROM orders o JOIN products p ON p.id=o.product_id ORDER BY o.id DESC").fetchall()
    return {"items":rows}
@app.post("/orders")
def create_order(data: OrderIn):
    with connect() as c:
        with c.transaction():
            p=c.execute("SELECT id,name,price,stock FROM products WHERE id=%s FOR UPDATE",(data.product_id,)).fetchone()
            if not p: raise HTTPException(404,"Product not found")
            if p['stock'] < data.quantity: raise HTTPException(400,"Not enough stock")
            total=p['price']*data.quantity
            c.execute("UPDATE products SET stock=stock-%s WHERE id=%s",(data.quantity,p['id']))
            row=c.execute("INSERT INTO orders(customer_name,product_id,quantity,total,status) VALUES(%s,%s,%s,%s,'created') RETURNING id,customer_name,product_id,quantity,total,status",(data.customer_name,p['id'],data.quantity,total)).fetchone()
    return row
