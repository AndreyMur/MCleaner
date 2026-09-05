# Запуск MCleaner на Windows

> Инструкция по локальному запуску и сборке. Русский язык.

## Готовность

- Код приложения завершён: все 10 фаз плана замержены в `main`.
- Публичного релиза пока нет — на [GitHub Releases](https://github.com/AndreyMur/MCleaner/releases) инсталлятор не опубликован (нет git-тега `v*`).

## Требуемое окружение

| Компонент                                            | Назначение              | Когда нужен                             |
| ---------------------------------------------------- | ----------------------- | --------------------------------------- |
| Node.js 20+ (npm)                                    | Frontend (React + Vite) | всегда                                  |
| Rust (rustup, stable)                                | Tauri/Rust-оболочка     | вариант B, сборка                       |
| VS Build Tools 2022 («Desktop development with C++») | MSVC linker для Rust    | вариант B, сборка                       |
| WebView2                                             | Рендер Tauri-окна       | вариант B (предустановлен в Windows 11) |
| Python 3.x                                           | Тесты Python-адаптеров  | опционально                             |

Проверка установленного окружения:

```cmd
node --version
npm --version
rustc --version
python --version
```

## Вариант A — Frontend в браузере (быстро, без Rust)

UI работает на реалистичных мок-данных — подходит для UI-разработки.

```cmd
cd src\frontend
npm ci
npm run dev
```

Открыть http://localhost:1420.

## Вариант B — Полное десктоп-приложение (Tauri, пакетный менеджер `winget`)

Требует доустановки Rust и MSVC Build Tools, если их нет:

1. Установите Rust: https://rustup.rs (`rustup-init.exe`, профиль `default`).
2. Установите **Visual Studio Build Tools 2022** с нагрузкой «Desktop development with C++».
3. WebView2 предустановлен в Windows 11 / свежих Windows 10.

Дальше:

```cmd
cd src\frontend
npm ci
```

Запуск приложения из корня репозитория (поднимает vite dev-сервер и открывает окно Tauri):

```cmd
node src\frontend\node_modules\@tauri-apps\cli\tauri.js dev
```

## Вариант C — Установщик NSIS (после публикации релиза)

Релиз публикуется CI по git-тегу `v*`:

```cmd
git tag v0.1.0
git push origin v0.1.0
```

CI соберёт `MCleaner_0.1.0_x64-setup.exe`, прогонит smoke-тест и опубликует в GitHub Releases. Далее просто скачать и запустить установщик.

## Сборка установщика локально

```cmd
node src\frontend\node_modules\@tauri-apps\cli\tauri.js build --bundles nsis
```

Результат: `src-tauri\target\release\bundle\nsis\*.exe`.

## Тесты

```cmd
cd src\frontend
npm run build                  :: type-check + сборка frontend
npx vitest run                 :: unit-тесты frontend
python -m pytest ..\tests -q   :: тесты Python-адаптеров
```

Rust unit-тесты (нужен Rust):

```cmd
cd src-tauri
cargo test
```
