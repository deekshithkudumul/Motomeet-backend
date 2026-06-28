from dotenv import load_dotenv
load_dotenv()

import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from groq import Groq as GroqClient
import models, auth
from database import engine, get_db, Base
from data.routes_data import ROUTES_DATA
from pydantic import BaseModel

Base.metadata.create_all(bind=engine)

# ── Seed Routes ───────────────────────────────────────
def seed_routes(db: Session):
    if db.query(models.Route).count() == 0:
        for r in ROUTES_DATA:
            route = models.Route(
                name=r["name"], slug=r["slug"],
                distance_km=r["distance_km"], difficulty=r["difficulty"],
                duration_days=r["duration_days"], start_point=r["start_point"],
                end_point=r["end_point"], states=r["states"],
                best_months=r["best_months"], description=r["description"],
                highlights=r["highlights"], warnings=r["warnings"],
                elevation_gain=r["elevation_gain"], waypoints=r["waypoints"],
                image_url=r["image_url"]
            )
            db.add(route)
            db.flush()
            for cp in r["waypoints"]:
                checkpoint = models.Checkpoint(
                    route_id=route.id, name=cp["name"],
                    lat=cp["lat"], lng=cp["lng"], order=cp["order"]
                )
                db.add(checkpoint)
        db.commit()
        print("✓ Routes seeded")

@asynccontextmanager
async def lifespan(app):
    db = next(get_db())
    seed_routes(db)
    yield
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"Access-Control-Allow-Origin": "*"}
    )

# ── App ───────────────────────────────────────────────
app = FastAPI(title="MotoMeet API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────
class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    bike_model: Optional[str] = ""
    experience: Optional[str] = "Beginner"
    city: Optional[str] = ""

class BatchCreate(BaseModel):
    route_id: int
    title: str
    start_date: str
    end_date: str
    max_riders: Optional[int] = 10
    description: Optional[str] = ""

class MessageCreate(BaseModel):
    content: str

class ProgressUpdate(BaseModel):
    checkpoint_id: int
    completed: bool

class AIGuideRequest(BaseModel):
    route_name: str
    difficulty: str
    distance_km: float
    duration_days: int
    states: str
    highlights: str
    experience_level: str = "Beginner"

# ── Auth Routes ───────────────────────────────────────
@app.post("/api/auth/register")
def register(user: UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = models.User(
        name=user.name, email=user.email,
        password_hash=auth.hash_password(user.password),
        bike_model=user.bike_model, experience=user.experience,
        city=user.city
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    token = auth.create_token({"sub": str(new_user.id)})
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": new_user.id, "name": new_user.name, "email": new_user.email}}

@app.post("/api/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form.username).first()
    if not user or not auth.verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth.create_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email,
                     "bike_model": user.bike_model, "experience": user.experience,
                     "city": user.city, "total_km": user.total_km}}

@app.get("/api/auth/me")
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return {"id": current_user.id, "name": current_user.name,
            "email": current_user.email, "bike_model": current_user.bike_model,
            "experience": current_user.experience, "city": current_user.city,
            "total_km": current_user.total_km}

# ── Routes API ────────────────────────────────────────
@app.get("/api/routes")
def get_routes(db: Session = Depends(get_db)):
    routes = db.query(models.Route).all()
    return [{"id": r.id, "name": r.name, "slug": r.slug,
             "distance_km": r.distance_km, "difficulty": r.difficulty,
             "duration_days": r.duration_days, "start_point": r.start_point,
             "end_point": r.end_point, "states": r.states,
             "best_months": r.best_months, "description": r.description,
             "highlights": r.highlights, "warnings": r.warnings,
             "elevation_gain": r.elevation_gain, "waypoints": r.waypoints,
             "image_url": r.image_url} for r in routes]

@app.get("/api/routes/{slug}")
def get_route(slug: str, db: Session = Depends(get_db)):
    route = db.query(models.Route).filter(models.Route.slug == slug).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    checkpoints = db.query(models.Checkpoint).filter(
        models.Checkpoint.route_id == route.id
    ).order_by(models.Checkpoint.order).all()
    return {"id": route.id, "name": route.name, "slug": route.slug,
            "distance_km": route.distance_km, "difficulty": route.difficulty,
            "duration_days": route.duration_days, "start_point": route.start_point,
            "end_point": route.end_point, "states": route.states,
            "best_months": route.best_months, "description": route.description,
            "highlights": route.highlights, "warnings": route.warnings,
            "elevation_gain": route.elevation_gain, "waypoints": route.waypoints,
            "image_url": route.image_url,
            "checkpoints": [{"id": c.id, "name": c.name, "lat": c.lat,
                             "lng": c.lng, "order": c.order} for c in checkpoints]}

# ── Batch API ─────────────────────────────────────────
@app.get("/api/batches")
def get_batches(route_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Batch)
    if route_id:
        query = query.filter(models.Batch.route_id == route_id)
    batches = query.filter(models.Batch.status == "open").all()
    result = []
    for b in batches:
        route = db.query(models.Route).filter(models.Route.id == b.route_id).first()
        creator = db.query(models.User).filter(models.User.id == b.creator_id).first()
        members = db.query(models.BatchMember).filter(models.BatchMember.batch_id == b.id).count()
        result.append({
            "id": b.id, "title": b.title, "route_id": b.route_id,
            "route_name": route.name if route else "",
            "start_date": b.start_date, "end_date": b.end_date,
            "max_riders": b.max_riders, "current_riders": members,
            "description": b.description, "status": b.status,
            "creator_name": creator.name if creator else ""
        })
    return result

@app.post("/api/batches")
def create_batch(batch: BatchCreate, db: Session = Depends(get_db),
                 current_user: models.User = Depends(auth.get_current_user)):
    new_batch = models.Batch(
        route_id=batch.route_id, creator_id=current_user.id,
        title=batch.title, start_date=batch.start_date,
        end_date=batch.end_date, max_riders=batch.max_riders,
        description=batch.description
    )
    db.add(new_batch)
    db.flush()
    member = models.BatchMember(
        batch_id=new_batch.id, user_id=current_user.id, role="leader"
    )
    db.add(member)
    db.commit()
    return {"id": new_batch.id, "message": "Batch created successfully"}

@app.post("/api/batches/{batch_id}/join")
def join_batch(batch_id: int, db: Session = Depends(get_db),
               current_user: models.User = Depends(auth.get_current_user)):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    existing = db.query(models.BatchMember).filter(
        models.BatchMember.batch_id == batch_id,
        models.BatchMember.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    count = db.query(models.BatchMember).filter(
        models.BatchMember.batch_id == batch_id).count()
    if count >= batch.max_riders:
        raise HTTPException(status_code=400, detail="Batch is full")
    member = models.BatchMember(
        batch_id=batch_id, user_id=current_user.id, role="rider"
    )
    db.add(member)
    if count + 1 >= batch.max_riders:
        batch.status = "full"
    db.commit()
    return {"message": "Joined batch successfully"}

@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    members = db.query(models.BatchMember).filter(
        models.BatchMember.batch_id == batch_id).all()
    messages = db.query(models.Message).filter(
        models.Message.batch_id == batch_id
    ).order_by(models.Message.created_at).all()
    route = db.query(models.Route).filter(models.Route.id == batch.route_id).first()
    return {
        "id": batch.id, "title": batch.title,
        "route": {"id": route.id, "name": route.name, "slug": route.slug} if route else None,
        "start_date": batch.start_date, "end_date": batch.end_date,
        "max_riders": batch.max_riders, "status": batch.status,
        "description": batch.description,
        "members": [{"user_id": m.user_id, "role": m.role,
                     "name": db.query(models.User).filter(
                         models.User.id == m.user_id).first().name} for m in members],
        "messages": [{"id": msg.id, "content": msg.content,
                      "created_at": str(msg.created_at),
                      "user_name": db.query(models.User).filter(
                          models.User.id == msg.user_id).first().name,
                      "user_id": msg.user_id} for msg in messages]
    }

@app.post("/api/batches/{batch_id}/messages")
def send_message(batch_id: int, msg: MessageCreate,
                 db: Session = Depends(get_db),
                 current_user: models.User = Depends(auth.get_current_user)):
    member = db.query(models.BatchMember).filter(
        models.BatchMember.batch_id == batch_id,
        models.BatchMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a batch member")
    message = models.Message(
        batch_id=batch_id, user_id=current_user.id, content=msg.content
    )
    db.add(message)
    db.commit()
    return {"message": "Sent"}

# ── Progress API ──────────────────────────────────────
@app.get("/api/progress")
def get_progress(db: Session = Depends(get_db),
                 current_user: models.User = Depends(auth.get_current_user)):
    progress = db.query(models.UserProgress).filter(
        models.UserProgress.user_id == current_user.id).all()
    return [{"route_id": p.route_id, "status": p.status,
             "completed_checkpoints": p.completed_checkpoints} for p in progress]

@app.post("/api/progress/{route_id}/checkpoint")
def update_checkpoint(route_id: int, update: ProgressUpdate,
                      db: Session = Depends(get_db),
                      current_user: models.User = Depends(auth.get_current_user)):
    progress = db.query(models.UserProgress).filter(
        models.UserProgress.user_id == current_user.id,
        models.UserProgress.route_id == route_id
    ).first()
    if not progress:
        progress = models.UserProgress(
            user_id=current_user.id, route_id=route_id,
            completed_checkpoints=[], status="in_progress",
            started_at=datetime.utcnow()
        )
        db.add(progress)
        db.flush()
    completed = progress.completed_checkpoints or []
    if update.completed and update.checkpoint_id not in completed:
        completed.append(update.checkpoint_id)
    elif not update.completed and update.checkpoint_id in completed:
        completed.remove(update.checkpoint_id)
    progress.completed_checkpoints = completed
    total = db.query(models.Checkpoint).filter(
        models.Checkpoint.route_id == route_id).count()
    if len(completed) == total:
        progress.status = "completed"
        progress.completed_at = datetime.utcnow()
    db.commit()
    return {"completed_checkpoints": completed, "status": progress.status}

# ── Dashboard API ─────────────────────────────────────
@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db),
                  current_user: models.User = Depends(auth.get_current_user)):
    progress = db.query(models.UserProgress).filter(
        models.UserProgress.user_id == current_user.id).all()
    completed_routes = [p for p in progress if p.status == "completed"]
    batches = db.query(models.BatchMember).filter(
        models.BatchMember.user_id == current_user.id).all()
    total_km = sum(
        db.query(models.Route).filter(models.Route.id == p.route_id).first().distance_km
        for p in completed_routes
        if db.query(models.Route).filter(models.Route.id == p.route_id).first()
    )
    return {
        "total_routes_completed": len(completed_routes),
        "total_routes_started": len(progress),
        "total_km": total_km,
        "total_batches": len(batches),
        "completed_routes": [p.route_id for p in completed_routes]
    }

# ── AI Guide API ──────────────────────────────────────
@app.post("/api/ai/route-guide")
def get_ai_guide(req: AIGuideRequest):
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")
        client = GroqClient(api_key=api_key)
        prompt = f"""You are an expert Indian motorcycle touring guide with 20 years of experience.

A rider is planning the following route:
- Route: {req.route_name}
- States: {req.states}
- Distance: {req.distance_km} km
- Duration: {req.duration_days} days
- Difficulty: {req.difficulty}
- Highlights: {req.highlights}
- Rider Experience: {req.experience_level}

Give a personalized riding guide with exactly these 4 sections:
1. PREPARATION (what to prepare, bike check, documents)
2. RIDING TIPS (specific tips for this route, road conditions, best riding times)
3. MUST STOPS (3-4 specific places to stop and why)
4. SAFETY WARNINGS (specific dangers on this route)

Keep each section to 3-4 bullet points. Be specific to this route, not generic.
Use Indian context — mention dhabas, petrol pumps, local conditions."""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800, temperature=0.7
        )
        return {"guide": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Root ──────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "MotoMeet API is running 🏍️ v2"}