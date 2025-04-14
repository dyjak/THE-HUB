@echo off
cd backend-fastapi
call venv\Scripts\activate
start cmd /k "uvicorn app.main:app --reload"
cd ../frontend-next
start cmd /k "npm run dev"
exit
