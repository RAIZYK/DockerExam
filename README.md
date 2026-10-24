# MarketDock — Docker Microservices Exam

Навчальний онлайн-магазин: власна реалізація з мікросервісною структурою, натхненна загальною ідеєю YellowShop. Архітектура й назви сервісів відрізняються.

## Архітектура (8 контейнерів)

- `gateway` — Nginx, роздає frontend та проксіює запити (порт хоста 8080).
- `productapi` — каталог товарів (FastAPI, PostgreSQL, Redis).
- `orderapi` — створення/перегляд замовлень; перевіряє склад і зменшує залишок у транзакції.
- `identity` — демонстраційна реєстрація та логін.
- `filter` — пошук і фільтрація за категорією/ціною.
- `admin` — статистика.
- `db` — PostgreSQL 16 з persistent volume.
- `redis` — Redis 7 з persistent volume.

Усі сервіси у приватній bridge-мережі `market-net`; DNS-імена Compose використовуються для зв'язку.

> Навчальний демо-проєкт: Identity зберігає demo-password як текст і не призначений для production.

## Запуск у VS Code

1. Розпакуйте архів та відкрийте папку проєкту у VS Code.
2. Запустіть Docker Desktop.
3. У терміналі в корені (де `docker-compose.yml`) виконайте:

```powershell
docker compose up --build -d
docker compose ps
```

Веб-магазин: http://localhost:8080
Swagger product API: http://localhost:8080/docs (проксі docs не налаштовано; product API docs доступний всередині мережі)
Filter API: `GET http://localhost:8080/filter?q=mouse`
Identity register: `POST http://localhost:8080/identity/register`
Admin stats: http://localhost:8080/admin/stats
Health: http://localhost:8080/health

Для API документації окремих сервісів можна тимчасово опублікувати їх порт у compose або звернутися зсередини мережі.

## Docker команди

```powershell
docker compose logs -f
docker compose logs -f orderapi
docker compose restart productapi
docker compose down
```

`docker compose down -v` видаляє volumes та всі дані бази — використовуйте лише якщо справді потрібно очистити дані.

## GitHub

Створіть порожній репозиторій, а в терміналі проєкту:

```powershell
git init
git add .
git commit -m "Build MarketDock Docker microservices exam"
git branch -M main
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

Якщо `origin` уже існує, перевірте його через `git remote -v`, не додавайте повторно.
