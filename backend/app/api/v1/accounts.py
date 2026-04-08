from fastapi import APIRouter

router = APIRouter(prefix="/accounts", tags=["账号管理"])


# TODO: 实现账号管理 API
# GET    /accounts
# POST   /accounts
# GET    /accounts/{id}
# DELETE /accounts/{id}
# POST   /accounts/{id}/oauth/callback
# PUT    /accounts/{id}/cookie
# GET    /accounts/{id}/status
# POST   /accounts/{id}/sync-profile
# PUT    /accounts/{id}/persona
# PUT    /accounts/{id}/proxy
