# PrismaLite_UI_Guide

## 1. Введение

Документ описывает UI/UX PrismaLite: основные экраны, навигацию, взаимодействия и требования к визуальным компонентам. Целевая аудитория — frontend-разработчики и UX-дизайнеры.

## 2. Общая структура

Навигация слева/сверху (вкладки):
1. Dashboard
2. Analytics
3. Live Monitoring
4. Incidents
5. Rules
6. Administration
7. Reports

Авторизация через login/password (JWT). Поддержка светлой/тёмной темы.

## 3. Dashboard

- **Верхняя панель**: фильтр по tenant/store, статус лицензии.
- **Карточки**: количество активных инцидентов, магазинов online/offline, событий за час.
- **Графики**: bar chart по нарушениям, line chart по событиям.
- **Список задач**: последние инциденты (severity color coding).

## 4. Analytics (чек + видео)

Layout:
```
┌──────────────────────────────┬───────────────────────────────┐
│          VIDEO PLAYER        │         CHECK DETAILS         │
│ (HLS.js, controls, timeline) │ (таблица позиций, totals)     │
├───────────────┬──────────────┴───────────────┬───────────────┤
│ EVENT LIST    │ FILTERS (drawer)             │ INCIDENT CARD │
└───────────────┴──────────────────────────────┴───────────────┘
```

- **Video player**: play/pause, 10s rewind, speed (0.5x/1x/2x), picture-in-picture.
- **Event list**: timeline с цветами (обычные, подозрительные). Клик → видео перематывается.
- **Filters**: магазин, касса, кассир, дата/время, SKU, тип события, тип нарушения.
- **Инструменты**: добавить заметку, создать инцидент, экпорт чека в PDF.

## 5. Live Monitoring

- **Grid view**: 4/9/16 камер, каждая плитка показывает статус (цвет рамки), имя камеры.
- **Sidebar**: список камер/магазинов, поиск, избранные.
- **Alerts panel**: всплывающие уведомления о новых инцидентах (toast или боковая панель).
- **Actions**: переключение качества (main/sub stream), mute/unmute, snapshot, переход к архиву.
- **Hotkeys**: стрелки для навигации по камерам, Enter — открыть камеру в полном экране.

## 6. Incidents

- Таблица:
  - Колонки: ID, Rule, Severity, Store, POS, Cashier, Timestamp, Status, Assignee.
  - Иконки severity (цвет: зелёный/желтый/оранжевый/красный).
- Фильтры: rule, severity, статус, диапазон дат, магазин, кассир.
- **Карточка** (справа или modal):
  - Детали правила.
  - События до/после.
  - Видео-превью (iframe).
  - Комментарии/история изменений.
  - Кнопки: подтверждать/отклонять, назначить, изменить статус.

## 7. Rules Management

- Список правил: таблица с колонками `code`, `category`, `severity`, `enabled`, `scope`, `last_updated`.
- Фильтры: категория, статус (enabled/disabled), tenant.
- **Редактор**:
  - Основные поля.
  - JSON/формы для параметров (thresholds, time windows).
  - Исключения (SKU whitelist, кассиры).
  - Preview/симуляция (в roadmap).
- Валидация: обязательные поля, уникальный `code`.

## 8. Administration

### 8.1 Shops & Registers
- Таблица магазинов (название, адрес, статус).
- Вкладка касс — фильтр по магазину, статус агента, тип интеграции.
- Форма добавления кассы (POS ID, магазин, тип, IP, привязка камеры).

### 8.2 Cameras
- Карточки камер (мини-превью, статус DVR).
- Добавление камеры: nombre, vendor, RTSP URL, канал, магазин, связанная касса.
- Тест подключения (кнопка, результат).

### 8.3 Users & Roles
- Таблица пользователей (логин, роль, магазины).
- Создание пользователя: логин, роль, временный пароль, scope.
- Сброс пароля, блокировка.

### 8.4 Licensing
- Виджет статуса (использовано/доступно).
- Кнопка «Активировать ключ».
- Logs по проверке лицензий.

## 9. Reports

- Список отчётов: Incidents, Cashiers, Stores, Video, Custom.
- UI генерации:
  - Выбор периода, фильтры, формат (PDF/Excel/CSV).
  - Кнопка «Generate».
  - История отчётов (статус, ссылка на скачивание).
- Visualization: графики/таблицы (Post-processing на UI или backend).

## 10. UX Guidelines

- **Цвета severity**: Info (#1890FF), Low (#52C41A), Medium (#FAAD14), High (#FA541C), Critical (#F5222D).
- **Фон**: нейтральный, контраст не менее 4.5:1.
- **Иконки**: Feather/Material (векторные).
- **Loading states**: skeleton/спиннеры.
- **Empty states**: иконка + текст + CTA (например, «Нет инцидентов, попробуйте изменить фильтр»).
- **Notifications**: toast (success/warning/error) с автоотключением.

## 11. Accessibility

- Навигация с клавиатуры (tab order, focus styles).
- ARIA labels для кнопок и таблиц.
- Поддержка экранных читалок (semantics).
- Контраст текста и фона ≥ 4.5:1.
- Видеоплеер: управление клавиатурой, описания.

## 12. Диаграмма UX-потоков (пример)

### Flow: Аналитика → Инцидент
```
Search check → Select event → Video auto-sync → Click "Create Incident" →
Fill form → Submit → Toast success → Incident appears in list
```

### Flow: Live → Архив
```
Live grid → Click camera → Fullscreen → Button "Go to archive" →
Pick time range → Replay player loads → Controls as in Analytics
```

### Flow: Add camera
```
Admin/Cameras → "Add camera" → Form → Test connection → Save →
Camera card appears with status ONLINE
```

## 13. Компоненты

- **Tables**: сортировка, фильтры, пагинация. Желательно использовать компонентную библиотеку (например, Ant Design) с кастомизацией.
- **Forms**: многошаговые (wizard) для сложных сущностей (кассы, DVR).
- **Modals/Drawer**: для карточек инцидентов и настроек.
- **Charts**: Recharts/ECharts (инциденты, статистика).
- **Maps** (опционально): расположение магазинов.

## 14. Device Support

- Desktop (основной сценарий).
- Tablet (адаптивные брейкпоинты ≥ 1024px).
- Mobile — только просмотр (в roadmap).

## 15. Тесты UI

- Snapshot тесты на компоненты.
- Cypress/Playwright для ключевых сценариев: логин, поиск чека, live просмотр, изменение правила.
- Регрессионные визуальные тесты (per release).

Документ обновляется при изменении UX/дизайна и новых требованиях. Макеты и дизайн-системы хранятся в Figma/дизайн-репозитории.

