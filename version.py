"""
Управление версиями проекта Deadline Bot.
"""

__version__ = "1.0.0"
__version_info__ = tuple(map(int, __version__.split(".")))

def get_version():
    """Возвращает текущую версию проекта."""
    return __version__

def get_version_info():
    """Возвращает информацию о версии в виде кортежа."""
    return __version_info__

if __name__ == "__main__":
    print(f"Deadline Bot v{__version__}")
