# gunicorn.conf.py
workers = 1  # Mulai dengan 1 worker
timeout = 120  # Tingkatkan untuk proses lambat (OCR/API)
bind = "0.0.0.0:${PORT}"  # Gunakan port dari Railway
loglevel = "debug"
