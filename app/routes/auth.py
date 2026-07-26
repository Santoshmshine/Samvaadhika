"""
Samvaadhika - Authentication routes
Login, logout, register, token endpoint.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import (
    authenticate_user, create_access_token, get_password_hash,
    get_optional_user,
)
from app.config import TEMPLATES_DIR
from app.database import get_db
from app.models import AuditLog, User

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )
    if not user.is_approved:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Your account is pending admin approval."},
            status_code=403,
        )
    if not user.is_active:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Your account has been deactivated."},
            status_code=403,
        )

    token = create_access_token({"sub": user.username})
    user.last_login = datetime.utcnow()

    # Audit log
    log = AuditLog(user_id=user.id, action="login", ip_address=request.client.host)
    db.add(log)
    db.commit()

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=28800,  # 8 hours
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse("/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match."},
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Password must be at least 8 characters."},
        )
    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username or email already registered."},
        )

    new_user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
        role="user",
        is_active=True,
        is_approved=False,  # Pending admin approval
    )
    db.add(new_user)
    log = AuditLog(action="register", detail=f"New user: {username}", ip_address=request.client.host)
    db.add(log)
    db.commit()

    return templates.TemplateResponse(
        "register.html",
        {"request": request, "success": "Registration submitted. An admin will approve your account shortly."},
    )


# JSON token endpoint for API clients
@router.post("/token")
async def token_endpoint(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username, password)
    if not user or not user.is_approved:
        raise HTTPException(status_code=401, detail="Invalid credentials or account not approved")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
