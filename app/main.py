from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="Transfer Availability & Booking Service")
app.include_router(router)
