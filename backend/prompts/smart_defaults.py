# ContentFactory - Smart Defaults
# When user selects an Etki, other settings auto-fill with the best combination
# User can override any of these

SMART_DEFAULTS = {
    "patlassin": {
        "karakter": "uzman",
        "yapi": "kurgulu",
        "uzunluk": "punch",
        "acilis": "otomatik",
        "bitis": "otomatik",
        "derinlik": "standart",
    },
    "konustursun": {
        "karakter": "iceriden",
        "yapi": "dogal",
        "uzunluk": "spark",
        "acilis": "tartisma",
        "bitis": "soru",
        "derinlik": "karsi_gorus",
    },
    "ogretsin": {
        "karakter": "otorite",
        "yapi": "kurgulu",
        "uzunluk": "punch",
        "acilis": "merak",
        "bitis": "dogal",
        "derinlik": "uzmanlik",
    },
    "iz_biraksin": {
        "karakter": "uzman",      # Not mentalist (Set 4 dersi: mentalist+cesur çelişti)
        "yapi": "dogal",           # Not cesur (Set 4 dersi: cesur çelişti)
        "uzunluk": "spark",
        "acilis": "hikaye",
        "bitis": "dogal",
        "derinlik": "standart",
    },
    "shitpost": {
        "karakter": "haberci",     # Ciddi format + absürt içerik = komedi
        "yapi": "dogal",
        "uzunluk": "micro",
        "acilis": "otomatik",
        "bitis": "dogal",
        "derinlik": "standart",
    },
}


def get_smart_defaults(etki_id: str) -> dict:
    """Return smart defaults for a given Etki selection.
    Returns empty dict if etki_id not found."""
    return SMART_DEFAULTS.get(etki_id, {})


# Export
__all__ = ['SMART_DEFAULTS', 'get_smart_defaults']
