
# bandit-tour-leads

Telegram-бот для клиентов **BanditTour** — парсит сообщения из TG-каналов/групп, ищет лиды по ключевым словам (экскурсии, туры, гиды и т.п.) и фильтрует их через Gemini с гео-правилом «только север Таиланда».

## Возможности (готовый бот, до деплоя на VPS)

- Real-time сканирование новых сообщений в подключённых каналах через Telethon
- Keyword-фильтр с границами слов для коротких английских (34+ слов)
- Gemini-классификатор (gemini-2.5-flash-lite) — отсеивает шум и спам
- Гео-правило: только север Таиланда (Чиангмай, Чианграй, Пай, Золотой треугольник, Мэхонгсон). Паттайя/Бангкок/Пхукет/Самуи/Краби/Хуахин → noise
- Категории: hot (прямой запрос), warm (потенциальный интерес), spam (конкуренты), noise (не лид)
- Inline-кнопки для управления через Telegram
- Дедупликация уведомлений по паре (канал, message_id) — не слать повторно про уже известный лид
- Хранение состояния в scan_state.json (last_id по каждому каналу)
- Логи в logs/bot_*.log
- Веб-дашборд (dashboard_server.py, только стандартная библиотека) — статистика и таблица лидов на http://127.0.0.1:8080
- Проверка без Telegram-ключей: python check_project.py
- Безопасность: session_user.session, session_bot.session, test_config.json, matches_found.json, scan_state.json в .gitignore

## Архитектура

```
Telegram-каналы -> Telethon events -> Keyword-фильтр -> Gemini классификатор -> Уведомление в Telegram
```

## Установка

### Требования
- Python 3.10+
- Telegram-аккаунт (для работы сканера через user-API)
- Telegram-бот (через @BotFather)
- Google AI Studio API-ключ (бесплатно)

### Шаги

```bash
git clone https://github.com/AlexBSCM/bandit-tour-leads.git
cd bandit-tour-leads
python -m pip install -r requirements.txt
copy config.example.json test_config.json
# Отредактировать test_config.json — вставить api_id, api_hash, gemini_api_key, bot_token, notify_chat_id
```

### Где взять значения

| Поле | Где получить |
|------|--------------|
| api_id, api_hash | https://my.telegram.org -> API development tools |
| gemini_api_key | https://aistudio.google.com/app/apikey |
| bot_token | @BotFather -> /newbot |
| notify_chat_id | @userinfobot -> ваш личный chat_id |

## Использование

### Быстрая проверка (без Telegram-ключей)

```bash
python check_project.py
```

Проверяет синтаксис, логику фильтров, mojibake-эвристику и установленные зависимости.
Зелёный итог = можно настраивать test_config.json и запускать бота.

### Запуск бота (real-time режим)

```bash
python bot.py
```

При первом запуске Telethon попросит:
1. Номер телефона (формат +79991234567)
2. Код из SMS / приложения Telegram
3. 2FA-пароль (если включён)

### Веб-дашборд

```bash
python dashboard_server.py
# открыть http://127.0.0.1:8080
```

Статистика и таблица лидов вживую из matches_found.json (первые 200).
Кнопка «🌐 Дашборд» в боте показывает адрес в локальной сети.
API: /api/leads, /api/stats.

### Запуск на Windows

- `run_bot.bat` — скрытый запуск бота (двойной клик)
- `run_dashboard_hidden.vbs` — скрытый запуск дашборда
- `watchdog.ps1` — проверка, что запущен именно bot.py, и автоперезапуск.
  Для периодического запуска используйте Планировщик заданий Windows (каждые 5 минут):
  `powershell -ExecutionPolicy Bypass -File watchdog.ps1`

### Команды бота

| Команда | Описание |
|---------|----------|
| /start | Главное меню с inline-кнопками |
| /stats | Статистика за сегодня и за сессию |
| /leads | Последние 10 найденных лидов |
| /pause | Поставить слушатель на паузу |
| /resume | Возобновить слушатель |

## Файлы проекта

| Файл | Назначение | В git |
|------|------------|-------|
| bot.py | Main-файл бота | Да |
| test_monitor.py | Stand-alone сканер | Да |
| dashboard_server.py | Веб-дашборд (stdlib, порт 8080) | Да |
| check_project.py | Проверка без Telegram-ключей | Да |
| run_bot.bat | Скрытый запуск бота (Windows) | Да |
| run_dashboard_hidden.vbs | Скрытый запуск дашборда (Windows) | Да |
| watchdog.ps1 | Автоперезапуск bot.py (Windows) | Да |
| requirements.txt | Python-зависимости | Да |
| config.example.json | Пример конфигурации | Да |
| .gitignore | Игнорируемые файлы | Да |
| README.md | Этот файл | Да |
| test_config.json | Реальная конфигурация с секретами | Нет (gitignored) |
| session_user.session | Сессия user-аккаунта (Telethon) | Нет (gitignored) |
| session_bot.session | Сессия bot-аккаунта (Telethon) | Нет (gitignored) |
| matches_found.json | Найденные лиды | Нет (gitignored) |
| scan_state.json | Состояние last_id по каналам | Нет (gitignored) |
| logs/ | Логи работы бота | Нет (gitignored) |

## Безопасность

- Все секреты исключены из git через .gitignore
- bot_token и notify_chat_id хранятся в test_config.json (не в коде)
- Рекомендуется периодически завершать активные TG-сессии через Telegram -> Настройки -> Устройства
- При компрометации session_user.session — завершить все сессии в Telegram, бот создаст новую при следующем запуске

## TODO (после деплоя на VPS)

- Деплой на Oracle Cloud Free Tier (ARM A1, 4 ядра, 24GB RAM)
- Auto-restart через systemd при сбое
- Мониторинг через Uptime Robot
- Backup matches_found.json и scan_state.json на Google Drive
- Web-дашборд для просмотра статистики (готово локально: dashboard_server.py)

## Контакты

BanditTour — туры на север Таиланда (Чиангмай, Чианграй, Пай, Золотой треугольник, Мэхонгсон).

---

Внимание: Бот использует user-API Telegram через Telethon. Не нарушайте ToS Telegram — иначе рискуете блокировкой аккаунта. Бот только читает публичные каналы, не спамит и не пишет от вашего имени.
