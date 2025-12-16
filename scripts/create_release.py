#!/usr/bin/env python3
"""
Скрипт для автоматизации процесса создания релиза.
"""

import os
import sys
import subprocess
import re
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from version import get_version

def run_command(cmd, check=True):
    """Выполняет команду и возвращает результат."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"❌ Команда провалилась: {cmd}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return False, result.stdout, result.stderr
        return True, result.stdout, result.stderr
    except Exception as e:
        print(f"❌ Ошибка выполнения команды: {e}")
        return False, "", str(e)

def get_current_branch():
    """Получает текущую git ветку."""
    success, stdout, stderr = run_command("git branch --show-current")
    return stdout.strip() if success else None

def get_latest_tag():
    """Получает последний тег."""
    success, stdout, stderr = run_command("git describe --tags --abbrev=0")
    return stdout.strip() if success else "v0.0.0"

def get_commits_since_tag(tag):
    """Получает коммиты с момента последнего тега."""
    success, stdout, stderr = run_command(f"git log --oneline {tag}..HEAD")
    return stdout.strip().split('\n') if success and stdout.strip() else []

def parse_commit_message(commit_line):
    """Парсит сообщение коммита для определения типа изменения."""
    commit_hash, message = commit_line.split(' ', 1)

    # Определяем тип изменения по ключевым словам
    if any(word in message.lower() for word in ['feat:', 'feature:', 'add:', 'new:']):
        return 'Added', message
    elif any(word in message.lower() for word in ['fix:', 'bug:', 'hotfix:']):
        return 'Fixed', message
    elif any(word in message.lower() for word in ['refactor:', 'perf:', 'improve:']):
        return 'Changed', message
    elif any(word in message.lower() for word in ['docs:', 'readme:', 'changelog:']):
        return 'Changed', message
    else:
        return 'Changed', message

def generate_changelog_section(commits):
    """Генерирует секцию changelog на основе коммитов."""
    changes = {'Added': [], 'Fixed': [], 'Changed': []}

    for commit in commits:
        if commit.strip():
            change_type, message = parse_commit_message(commit)
            # Очищаем сообщение от префиксов типа feat:, fix: и т.д.
            clean_message = re.sub(r'^(feat|fix|refactor|perf|docs|style|test|chore):?\s*', '', message, flags=re.IGNORECASE)
            changes[change_type].append(f"- {clean_message}")

    # Формируем секцию changelog
    sections = []
    for change_type, items in changes.items():
        if items:
            sections.append(f"### {change_type}")
            sections.extend(items)

    return '\n'.join(sections)

def update_version_file(new_version):
    """Обновляет файл version.py с новой версией."""
    version_file = Path(__file__).parent.parent / "version.py"

    content = version_file.read_text()
    # Обновляем версию
    content = re.sub(r'__version__ = "[^"]*"', f'__version__ = "{new_version}"', content)

    version_file.write_text(content)
    print(f"✅ Обновлена версия в version.py: {new_version}")

def update_changelog(new_version, changelog_content):
    """Обновляет CHANGELOG.md с новой версией."""
    changelog_file = Path(__file__).parent.parent / "CHANGELOG.md"

    # Читаем текущий changelog
    content = changelog_file.read_text()

    # Создаем новую запись
    date = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"""## [{new_version}] - {date}

{changelog_content}
"""

    # Находим позицию после "## [Unreleased]" и вставляем новую запись
    if "## [Unreleased]" in content:
        content = content.replace("## [Unreleased]", f"## [Unreleased]\n\n{new_entry}", 1)
    else:
        # Если нет Unreleased секции, добавляем в начало
        content = f"# Changelog\n\n{new_entry}\n{content}"

    changelog_file.write_text(content)
    print(f"✅ Обновлен CHANGELOG.md для версии {new_version}")

def create_release_branch(version):
    """Создает ветку релиза."""
    branch_name = f"release/v{version}"

    # Проверяем, что мы в develop ветке
    current_branch = get_current_branch()
    if current_branch != "develop":
        print(f"❌ Вы должны находиться в ветке develop. Текущая ветка: {current_branch}")
        return False

    # Создаем ветку релиза
    success, stdout, stderr = run_command(f"git checkout -b {branch_name}")
    if not success:
        print(f"❌ Не удалось создать ветку {branch_name}")
        return False

    print(f"✅ Создана ветка релиза: {branch_name}")
    return True

def main():
    """Главная функция создания релиза."""
    print("🚀 Создание нового релиза Deadline Bot")
    print("=" * 50)

    # Получаем текущую версию
    current_version = get_version()
    print(f"Текущая версия: {current_version}")

    # Спрашиваем новую версию
    new_version = input("Введите новую версию (например: 1.1.0): ").strip()
    if not new_version:
        print("❌ Версия не указана")
        return

    # Валидация версии
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        print("❌ Неверный формат версии. Используйте MAJOR.MINOR.PATCH")
        return

    print(f"Создание релиза v{new_version}")
    print("-" * 30)

    # Получаем коммиты для changelog
    latest_tag = get_latest_tag()
    commits = get_commits_since_tag(latest_tag)

    if not commits:
        print(f"⚠️  Не найдено новых коммитов с момента тега {latest_tag}")
        if not input("Продолжить? (y/N): ").lower().startswith('y'):
            return

    # Генерируем changelog
    changelog_content = generate_changelog_section(commits)
    print("Сгенерированный changelog:")
    print(changelog_content)
    print()

    if not input("Продолжить с этим changelog? (y/N): ").lower().startswith('y'):
        return

    # Создаем ветку релиза
    if not create_release_branch(new_version):
        return

    # Обновляем файлы
    update_version_file(new_version)
    update_changelog(new_version, changelog_content)

    # Коммитим изменения
    print("📝 Коммитим изменения...")
    success, stdout, stderr = run_command('git add .')
    if not success:
        print("❌ Ошибка при git add")
        return

    success, stdout, stderr = run_command(f'git commit -m "Release v{new_version}"')
    if not success:
        print("❌ Ошибка при git commit")
        return

    print("✅ Изменения закоммичены")

    # Отправляем ветку
    print("📤 Отправляем ветку на GitHub...")
    success, stdout, stderr = run_command(f'git push origin release/v{new_version}')
    if not success:
        print("❌ Ошибка при git push")
        return

    print("✅ Ветка релиза отправлена на GitHub")
    print()
    print("🎉 Релиз подготовлен!")
    print()
    print("Дальнейшие шаги:")
    print(f"1. Создайте Pull Request из release/v{new_version} в main")
    print("2. После ревью и тестирования слейте PR"
    print(f"3. Создайте тег: git tag -a v{new_version} -m 'Release v{new_version}'")
    print(f"4. Отправьте тег: git push origin v{new_version}")
    print(f"5. Создайте GitHub Release для тега v{new_version}")
    print("6. CI/CD автоматически соберет и задеплоит новую версию"

if __name__ == "__main__":
    main()
