from fastapi import FastAPI
from .common import connect
app=FastAPI(title="MarketDock Admin API",description="Administrative metrics")
@app.get("/health")
def health(): return {"service":"admin-api","status":"healthy"}
@app.get("/admin/stats")
def stats():
    with connect() as c:
        p=c.execute("SELECT COUNT(*) AS products_count,COALESCE(SUM(stock),0) AS items_in_stock FROM products").fetchone()
        o=c.execute("SELECT COUNT(*) AS orders_count,COALESCE(SUM(total),0) AS revenue FROM orders").fetchone()
    return {**p,**o}
