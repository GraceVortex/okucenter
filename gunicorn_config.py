"""
Gunicorn configuration file for okucenter project
"""

import multiprocessing

# Привязка к IP-адресу и порту
bind = "0.0.0.0:8000"

# Количество рабочих процессов
workers = multiprocessing.cpu_count() * 2 + 1

# Тип рабочих процессов
worker_class = "sync"

# Таймаут для рабочих процессов
timeout = 120

# Максимальное количество запросов для рабочего процесса
max_requests = 1000
max_requests_jitter = 50

# Логирование
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"

# Перезагрузка при изменении кода (только для разработки)
reload = False

# Демонизация процесса (запуск в фоновом режиме)
daemon = False

# Путь к файлу с PID процесса
pidfile = "logs/gunicorn.pid"
