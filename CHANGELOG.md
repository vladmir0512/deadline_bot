# Changelog

Все значимые изменения в проекте Deadline Bot будут документированы на этой странице.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
и этот проект придерживается [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Добавлена поддержка релизов в GitHub Actions
- Улучшена документация по release процессу

### Fixed
- Исправлены мелкие баги в health check

### Changed
- Обновлена структура CI/CD pipeline

## [1.0.0] - 2025-12-16

### Added
- ✅ Полная система управления дедлайнами
- ✅ Интеграция с Telegram Bot API
- ✅ Синхронизация с Yonote через CSV API
- ✅ Автоматические уведомления о дедлайнах
- ✅ Docker контейнеризация
- ✅ Health check и мониторинг
- ✅ CI/CD через GitHub Actions
- ✅ Полная документация для развертывания

### Changed
- Переход с systemd на Docker-based развертывание
- Улучшенная архитектура с разделением на сервисы

### Technical
- Python 3.11, aiogram 3.x, SQLAlchemy 2.0
- Docker multi-stage builds
- Структурированное логирование
- Автоматическое резервное копирование

---

## Типы изменений

- `Added` - для новых функций
- `Changed` - для изменений в существующем функционале
- `Deprecated` - для функций, которые будут удалены в будущем
- `Removed` - для удаленных функций
- `Fixed` - для исправления багов
- `Security` - для исправлений безопасности
