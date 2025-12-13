import os
import datetime
import logging
from typing import Any, Dict

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from x402.fastapi.middleware import require_payment
from x402.types import PaywallConfig

# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, filename="fastapi.log")
logger = logging.getLogger(__name__)

load_dotenv()

# Required / configurable env vars
ADDRESS = os.environ["ADDRESS"]  # fail fast if missing
SECRET_KEY = os.environ.get("JWT_SECRET", "change-me-in-production")
COOKIE_NAME = os.environ.get("COOKIE_NAME", "x402_auth_token")

# x402-specific config from env
X402_PRICE = os.environ.get("X402_PRICE", "$0.001")          # amount
X402_NETWORK = os.environ.get("X402_NETWORK", "base-sepolia")  # network
X402_APP_NAME = os.environ.get("X402_APP_NAME", "x402 Omniacs")
X402_APP_LOGO = os.environ.get("X402_APP_LOGO", "/x402static/omniacsdao_logo.png")
X402_CDP_CLIENT_KEY = os.environ.get("X402_CDP_CLIENT_KEY", "")

TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL_SECONDS", str(24 * 3600)))

# ---------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------

app = FastAPI()
app.mount("/x402static", StaticFiles(directory="x402static"), name="x402static")

# x402 middleware: reads amount/network from env
app.middleware("http")(
    require_payment(
        path="/auth",
        price=X402_PRICE,
        pay_to_address=ADDRESS,
        network=X402_NETWORK,
        paywall_config=PaywallConfig(
            cdp_client_key=X402_CDP_CLIENT_KEY,
            app_name=X402_APP_NAME,
            app_logo=X402_APP_LOGO,
        ),
    )
)

# ---------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------


def create_token(user_id: str = "anonymous") -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "exp": now + datetime.timedelta(seconds=TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def validate_token_or_401(token: str) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")

    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.info("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        logger.info("Invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------


@app.get("/auth", response_class=HTMLResponse)
async def authenticate(_: Request) -> HTMLResponse:
    """
    Called by x402 after successful payment.
    Issues a JWT, sets it as a cookie, then meta-refreshes back to "/".
    """
    logger.info("Processing /auth request")

    token = create_token()
    logger.info("Token generated")

    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta http-equiv="refresh" content="1;url=/" />
        <title>Loading…</title>
      </head>
      <body style="margin:0;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;background:#111827;color:#e5e7eb;text-align:center;">
        <div>
          <div style="font-size:1.1rem;font-weight:600;">Payment complete</div>
          <div style="margin-top:4px;">Loading…</div>
          <div style="margin-top:6px;font-size:0.9rem;">If nothing happens, <a href="/" style="color:#93c5fd;">click here</a>.</div>
        </div>
      </body>
    </html>
    """

    response = HTMLResponse(content=html, status_code=200)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # set True when behind HTTPS / in prod
        max_age=TOKEN_TTL_SECONDS,
        path="/",
        samesite="lax",
    )
    return response


@app.get("/validate")
async def validate(request: Request) -> Dict[str, Any]:
    """
    NGINX auth_request target.
    It receives the token via X-Token header from NGINX.
    """
    token = request.headers.get("X-Token")
    logger.info("Processing /validate request")
    validate_token_or_401(token)
    return {"status": "valid"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4021)
