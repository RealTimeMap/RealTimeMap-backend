"""Человекочитаемое имя устройства из User-Agent.

Намеренно грубый разбор по подстрокам, без внешней библиотеки: строка нужна
только чтобы пользователь узнал своё устройство в списке сессий ("Chrome на
Windows"), а не для аналитики. Полный User-Agent хранится рядом — если разбор
ошибётся, исходные данные не потеряны.

Порядок проверок важен: многие браузеры маскируются под Chrome и Safari, а
почти все мобильные UA содержат "Mozilla", поэтому более специфичные маркеры
проверяются первыми.
"""

from typing import Optional

# (маркер в User-Agent, отображаемое имя). Порядок = приоритет.
_BROWSERS: tuple[tuple[str, str], ...] = (
    ("YaBrowser", "Yandex Browser"),
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Opera", "Opera"),
    ("SamsungBrowser", "Samsung Internet"),
    ("Firefox", "Firefox"),
    ("Chrome", "Chrome"),
    ("Safari", "Safari"),
)

_OS: tuple[tuple[str, str], ...] = (
    ("Windows", "Windows"),
    ("Android", "Android"),
    # iPhone/iPad проверяются до Mac OS X: в их UA встречается "like Mac OS X".
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Linux", "Linux"),
)


def parse_device_name(user_agent: Optional[str]) -> Optional[str]:
    """Собирает короткое имя устройства вида "Chrome на Windows".

    Возвращает None, если строка пустая или ничего не опознано: пустое
    значение честнее выдуманного, а подстановку текста для читателя делает
    клиент.
    """
    if not user_agent:
        return None

    browser = next(
        (name for marker, name in _BROWSERS if marker in user_agent),
        None,
    )
    os_name = next(
        (name for marker, name in _OS if marker in user_agent),
        None,
    )

    if browser and os_name:
        return f"{browser} на {os_name}"
    if browser:
        return browser
    if os_name:
        return os_name
    return None
