# Разработка и публикация

## Локальный запуск

Нужны Windows 10/11 x64 и Python 3.12 x64. Открой PowerShell в корне репозитория:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

В `app_config.json` уже задан публичный Discord Application ID проекта. Для собственного форка создай приложение на [Discord Developer Portal](https://discord.com/developers/applications) и укажи свой Application ID. Bot Token и Client Secret не нужны и не должны попадать в репозиторий.

## Проверки

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/reader.test.cjs
```

Для второй команды нужен Node.js. Тесты проверяют смену трека, паузу, фильтрацию URL, ограничение частоты обновлений, переподключение и чтение метаданных плеера.

Дополнительно проверяются временные метки, перемотка, выбор крупной обложки и возврат к исходной картинке при ошибке загрузки.

## Сборка EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Результат: `dist\SoundCloudRPC.exe`. Сборка включает Python и библиотеки; WebView2 Runtime остаётся системной зависимостью. EXE не подписан сертификатом издателя.

Иконка приложения хранится отдельно от логотипа: `assets/app.ico` содержит девять размеров. При изменении исходного логотипа её можно пересобрать командой `powershell -ExecutionPolicy Bypass -File scripts/build_icon.ps1`. Это не изменяет изображение для Discord.

## Устройство проекта

| Файл | Назначение |
| --- | --- |
| `app.py` | Окно WebView2, профиль сайта и фоновое чтение плеера |
| `reader.js` | Название, автор, обложка и состояние воспроизведения |
| `presence.py` | Проверка данных и управление Discord RPC |
| `app_config.json` | Публичный Application ID |
| `.github/workflows/windows.yml` | Тесты, сборка Windows и черновик релиза |

## Публикация версии

Обнови `CHANGELOG.md` и release notes. Проверь EXE вручную с реальной песней: смена трека, обложка, пауза, возобновление, переход между страницами, перезапуск Discord и закрытие приложения.

```powershell
git add .
git commit -m "Prepare release"
git push
git tag v0.1.8
git push origin v0.1.8
```

Тег `v*` запускает GitHub Actions. Workflow собирает EXE, вычисляет SHA-256 и создаёт черновик предварительного релиза. После проверки открой Releases и опубликуй его.

Если workflow уже подготовил релиз, редактируй существующий черновик вместо создания второго. Исходники GitHub прикладывает к релизам автоматически.

## Локальные данные

Профиль сайта, настройка первого запуска и журнал хранятся в `%LOCALAPPDATA%\SoundCloudRPC`. Их не нужно включать в Git. Для сброса закрой приложение и удали эту папку.
