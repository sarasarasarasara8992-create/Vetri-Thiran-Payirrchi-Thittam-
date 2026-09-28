import json
from pathlib import Path
from typing import Annotated

from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form
)

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    JSONResponse
)

from fastapi.templating import Jinja2Templates

from fastapi.staticfiles import StaticFiles

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session

from sqlalchemy import (
    select,
    desc
)

from app.config import settings

from app.database import (
    Base,
    engine,
    get_db
)

from app.models import (
    User,
    RecommendationHistory
)

from app.schemas import (
    RegisterRequest,
    LoginRequest,
    HomeRequest,
    PartyRequest,
    JewelryRequest
)

from app.auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    COOKIE_NAME
)

from app.services import (
    home_recommendations,
    party_recommendations,
    jewelry_recommendations
)


BASE_DIR = Path(__file__).resolve().parent

TEMPLATES_DIR = BASE_DIR / "templates"

STATIC_DIR = BASE_DIR / "static"

UPLOAD_DIR = BASE_DIR.parent / "uploads"

UPLOAD_DIR.mkdir(
    exist_ok=True
)


Base.metadata.create_all(
    bind=engine
)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0"
)


app.add_middleware(

    CORSMiddleware,

    allow_origins=settings.origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


app.mount(
    "/static",
    StaticFiles(
        directory=STATIC_DIR
    ),
    name="static"
)


templates = Jinja2Templates(
    directory=TEMPLATES_DIR
)


@app.get("/health")
def health():

    return {

        "status": "ok",

        "app":
            settings.app_name,

        "mock_ai":
            (
                settings.mock_ai
                or not bool(
                    settings.gemini_api_key
                )
            ),

        "model":
            settings.gemini_model
    }


def save_history(
    db: Session,
    user_id: int,
    planner: str,
    request_data: dict,
    response_data: dict
):

    row = RecommendationHistory(

        user_id=user_id,

        planner=planner,

        request_json=json.dumps(
            request_data
        ),

        response_json=json.dumps(
            response_data
        )
    )

    db.add(row)

    db.commit()


def render(
    request: Request,
    template: str,
    **context
):

    return templates.TemplateResponse(

        request=request,

        name=template,

        context=context
    )


# ---------------------------------------------------------
# PAGES
# ---------------------------------------------------------

@app.get(
    "/",
    response_class=HTMLResponse
)
def home(
    request: Request
):

    return render(
        request,
        "index.html"
    )


@app.get(
    "/register",
    response_class=HTMLResponse
)
def register_page(
    request: Request
):

    return render(
        request,
        "register.html"
    )


@app.get(
    "/login",
    response_class=HTMLResponse
)
def login_page(
    request: Request
):

    return render(
        request,
        "login.html"
    )


@app.get(
    "/dashboard",
    response_class=HTMLResponse
)
def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):

    try:

        user = get_current_user(
            request,
            db
        )

    except HTTPException:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    rows = db.scalars(

        select(
            RecommendationHistory
        )

        .where(
            RecommendationHistory.user_id
            == user.id
        )

        .order_by(
            desc(
                RecommendationHistory.created_at
            )
        )

        .limit(5)

    ).all()

    return render(
        request,
        "dashboard.html",
        user=user,
        history=rows
    )


@app.get(
    "/planner/{planner}",
    response_class=HTMLResponse
)
def planner_page(
    planner: str,
    request: Request
):

    if planner not in {
        "home",
        "party",
        "jewelry"
    }:

        raise HTTPException(
            404,
            "Unknown planner"
        )

    return render(
        request,
        f"{planner}_planner.html",
        planner=planner
    )


@app.get(
    "/history",
    response_class=HTMLResponse
)
def history_page(
    request: Request,
    db: Session = Depends(get_db)
):

    try:

        user = get_current_user(
            request,
            db
        )

    except HTTPException:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    rows = db.scalars(

        select(
            RecommendationHistory
        )

        .where(
            RecommendationHistory.user_id
            == user.id
        )

        .order_by(
            desc(
                RecommendationHistory.created_at
            )
        )

    ).all()

    return render(
        request,
        "history.html",
        user=user,
        history=rows
    )


# ---------------------------------------------------------
# AUTH
# ---------------------------------------------------------

@app.post("/api/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):

    email = data.email.lower().strip()

    existing = db.scalar(

        select(User).where(
            User.email == email
        )
    )

    if existing:

        raise HTTPException(
            409,
            "An account with this email already exists"
        )

    user = User(

        email=email,

        password_hash=hash_password(
            data.password
        )
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    token = create_token(
        user.id
    )

    response = JSONResponse({

        "message":
            "Registered successfully"
    })

    response.set_cookie(

        COOKIE_NAME,

        token,

        httponly=True,

        samesite="lax",

        secure=settings.cookie_secure,

        max_age=86400
    )

    return response


@app.post("/api/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):

    email = data.email.lower().strip()

    user = db.scalar(

        select(User).where(
            User.email == email
        )
    )

    if (
        not user
        or not verify_password(
            data.password,
            user.password_hash
        )
    ):

        raise HTTPException(
            401,
            "Invalid email or password"
        )

    token = create_token(
        user.id
    )

    response = JSONResponse({

        "message":
            "Login successful"
    })

    response.set_cookie(

        COOKIE_NAME,

        token,

        httponly=True,

        samesite="lax",

        secure=settings.cookie_secure,

        max_age=86400
    )

    return response


@app.post("/api/logout")
def logout():

    response = JSONResponse({

        "message":
            "Logged out"
    })

    response.delete_cookie(
        COOKIE_NAME
    )

    return response


@app.get("/token")
def token_endpoint(
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_current_user(
        request,
        db
    )

    return {

        "access_token":
            create_token(
                user.id
            ),

        "token_type":
            "bearer"
    }


@app.get("/session-info")
def session_info(
    request: Request,
    db: Session = Depends(get_db)
):

    try:

        user = get_current_user(
            request,
            db
        )

        return {

            "authenticated":
                True,

            "user_id":
                user.id,

            "email":
                user.email
        }

    except HTTPException:

        return {

            "authenticated":
                False
        }


@app.get("/session-data")
def session_data(
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_current_user(
        request,
        db
    )

    return {

        "user_id":
            user.id,

        "email":
            user.email,

        "history_count":
            len(user.histories)
    }


# ---------------------------------------------------------
# HOME PLANNER
# ---------------------------------------------------------

@app.post("/generate-home")
def generate_home(
    data: HomeRequest,
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_current_user(
        request,
        db
    )

    result = home_recommendations(
        data.model_dump()
    )

    save_history(

        db,

        user.id,

        "home",

        data.model_dump(),

        result
    )

    return result


# ---------------------------------------------------------
# PARTY PLANNER
# ---------------------------------------------------------

@app.post("/generate-party")
def generate_party(
    data: PartyRequest,
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_current_user(
        request,
        db
    )

    result = party_recommendations(
        data.model_dump()
    )

    save_history(

        db,

        user.id,

        "party",

        data.model_dump(),

        result
    )

    return result


# ---------------------------------------------------------
# JEWELRY PLANNER
# ---------------------------------------------------------

@app.post("/generate-jewelry")
async def generate_jewelry(

    request: Request,

    budget: Annotated[
        float,
        Form(gt=0)
    ],

    occasion: Annotated[
        str,
        Form(min_length=2)
    ],

    style: Annotated[
        str,
        Form(min_length=2)
    ],

    outfit_color: Annotated[
        str,
        Form()
    ] = "",

    outfit_image: UploadFile | None =
        File(default=None),

    db: Session =
        Depends(get_db),
):

    user = get_current_user(
        request,
        db
    )

    data = JewelryRequest(

        budget=budget,

        occasion=occasion,

        style=style,

        outfit_color=outfit_color
    )

    image_bytes = None

    mime_type = None

    if (
        outfit_image
        and outfit_image.filename
    ):

        allowed = {

            "image/jpeg",

            "image/png",

            "image/webp"
        }

        if (
            outfit_image.content_type
            not in allowed
        ):

            raise HTTPException(

                400,

                "Only JPEG, PNG or WebP "
                "images are supported"
            )

        image_bytes = (
            await outfit_image.read()
        )

        if len(image_bytes) > 10 * 1024 * 1024:

            raise HTTPException(

                413,

                "Image must be 10 MB or smaller"
            )

        mime_type = (
            outfit_image.content_type
        )

    result = jewelry_recommendations(

        data.model_dump(),

        image_bytes,

        mime_type
    )

    save_history(

        db,

        user.id,

        "jewelry",

        data.model_dump(),

        result
    )

    return result


# ---------------------------------------------------------
# RECOMMENDATION DETAILS
# ---------------------------------------------------------

@app.get(
    "/recommendations-details/{history_id}"
)
def recommendation_details(

    history_id: int,

    request: Request,

    db: Session = Depends(get_db)
):

    user = get_current_user(
        request,
        db
    )

    row = db.get(
        RecommendationHistory,
        history_id
    )

    if (
        not row
        or row.user_id != user.id
    ):

        raise HTTPException(
            404,
            "Recommendation not found"
        )

    return json.loads(
        row.response_json
    )


@app.get(
    "/history/{history_id}"
)
def history_api(

    history_id: int,

    request: Request,

    db: Session = Depends(get_db)
):

    return recommendation_details(
        history_id,
        request,
        db
    )


@app.on_event("startup")
def startup():

    Base.metadata.create_all(
        bind=engine
    )