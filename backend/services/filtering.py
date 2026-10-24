from fastapi import FastAPI
from typing import Optional
from .common import connect
app=FastAPI(title="MarketDock Filter API",description="Product search and filtering")
@app.get("/health")
def health(): return {"service":"filter-api","status":"healthy"}
@app.get("/filter")
def filter_products(q:Optional[str]=None, category:Optional[str]=None, min_price:Optional[float]=None, max_price:Optional[float]=None):
    sql="SELECT id,name,description,category,price,stock FROM products WHERE 1=1"; args=[]
    if q: sql+=" AND (name ILIKE %s OR description ILIKE %s)"; args += [f"%{q}%",f"%{q}%"]
    if category: sql+=" AND category=%s"; args.append(category)
    if min_price is not None: sql+=" AND price >= %s"; args.append(min_price)
    if max_price is not None: sql+=" AND price <= %s"; args.append(max_price)
    sql+=" ORDER BY id"
    with connect() as c: rows=c.execute(sql,args).fetchall()
    return {"items":rows,"count":len(rows)}
