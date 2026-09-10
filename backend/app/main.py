from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth_routes, orgs, risk, assets, controls, dataquality, compare

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Control-Effectiveness Dashboard API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/api")
app.include_router(orgs.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(controls.router, prefix="/api")
app.include_router(dataquality.router, prefix="/api")
app.include_router(compare.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
