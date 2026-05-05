# Diary App — JavaScript Version

Перенос приложения дневника на JavaScript-стек.

## Оригинал

Оригинальный проект: [RedX95/diary](https://github.com/RedX95/diary)  
Fork: [Itami00001/diary](https://github.com/Itami00001/diary)

## Предполагаемый стек технологий

### Backend

| Компонент | Технология |
|-----------|------------|
| Рантайм | **Node.js** (замена Expo/Metro) |
| Фреймворк | **Express.js** — REST API |
| База данных | **MongoDB** — документо-ориентированное хранилище |
| ODM | **Mongoose** — работа с MongoDB |
| Контейнеризация | **Docker** + **Docker Compose** |
| Веб-сервер | **Nginx** (reverse proxy, статика) |

### Frontend

| Компонент | Технология |
|-----------|------------|
| Язык | **JavaScript (ES6+)** |
| UI фреймворк | **React** — компонентный интерфейс |
| Стилизация | **CSS Modules** или **Tailwind CSS** |
| State Management | **Redux Toolkit** или **Zustand** |
| HTTP клиент | **Axios** |
| Дата/время | **date-fns** или **dayjs** |

### Инфраструктура

| Компонент | Технология |
|-----------|------------|
| Контейнеризация | Docker |
| Оркестрация | Docker Compose |
| База данных | MongoDB |
| Кэш (опционально) | Redis |

## Структура проекта

```
.
├── docker-compose.yml      # Конфигурация Docker
├── backend/
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── server.js
│   │   ├── routes/
│   │   ├── models/
│   │   └── controllers/
│   └── .env
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   └── pages/
    └── .env
```

## TODO

- [ ] Настроить Docker и Docker Compose
- [ ] Создать Express backend с MongoDB
- [ ] Создать React frontend
- [ ] Реализовать CRUD для записей дневника
- [ ] Добавить авторизацию (JWT)
- [ ] Деплой

## Ветка

`JavaScript` — активная ветка разработки
