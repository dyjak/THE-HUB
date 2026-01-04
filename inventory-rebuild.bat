cd backend-fastapi

uvicorn app.main:app --reload



python -c "from app.air.inventory.inventory import build_inventory; build_inventory(deep=True)"