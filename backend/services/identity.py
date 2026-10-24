from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .common import connect
app=FastAPI(title="MarketDock Identity API", description="Demo identity service")
class UserIn(BaseModel): username:str=Field(min_length=3,max_length=80); password:str=Field(min_length=4,max_length=120)
@app.on_event("startup")
def init():
    with connect() as c: c.execute("CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_demo TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())")
@app.get("/health")
def health(): return {"service":"identity-api","status":"healthy"}
@app.post("/register")
def register(u:UserIn):
    try:
        with connect() as c: row=c.execute("INSERT INTO users(username,password_demo) VALUES(%s,%s) RETURNING id,username,created_at",(u.username,u.password)).fetchone()
        return row
    except Exception as e: raise HTTPException(409,"Username already exists")
@app.post("/login")
def login(u:UserIn):
    with connect() as c: row=c.execute("SELECT id,username FROM users WHERE username=%s AND password_demo=%s",(u.username,u.password)).fetchone()
    if not row: raise HTTPException(401,"Invalid demo credentials")
    return {"authenticated":True,"user":row}
