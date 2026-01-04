# Ubij uvicorn/serwer (jeśli działa pod takim procesem)
Get-Process -Name uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force

# Ubij python uruchomiony dla backendu (ostrożnie, zamknie inne pythonowe rzeczy)
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force

# Ubij node (frontend dev server)
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force