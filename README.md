# Distributed Search Pipeline

Курсова робота з дисципліни "Паралельні обчислення" — пошукова система з паралельною побудовою інвертованого індексу та інтеграцією LLM (Ollama) для розширення пошукових запитів.

## Технології

- Java 21, Spring Boot
- Власна реалізація ThreadPool та потокобезпечної хеш-таблиці
- Ollama (query expansion)
- Docker Compose

## Запуск проєкту

1. Підняти сервіси:

docker compose up -d


2. Завантажити LLM-модель для Ollama (лише при першому запуску — модель зберігається в docker volume і не потребує повторного завантаження при наступних запусках):

docker exec -it ollama ollama pull llama3.2:1b


3. Перевірити, що все працює:

curl http://localhost:8080/api/health


Очікувана відповідь: `{"status":"ok","ollama":true}`

## Датасет

Проєкт очікує датасет у форматі `.jsonl` (JSON Lines) у папці `search-server/data/batched_dataset/` — кожен рядок файлу є окремим JSON-документом.

## API

- `GET /api/health` — стан сервера та доступність Ollama
- `POST /api/index` — побудова інвертованого індексу (`{"threads": N}`)
- `GET /api/stats` — статистика останньої побудови індексу
- `POST /api/search` — пошук (`{"query": "...", "mode": "keyword"}`)