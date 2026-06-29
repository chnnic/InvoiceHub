from django.conf import settings
from django.shortcuts import redirect


LANGUAGE_ALIASES = {
    "zh": "zh-hans",
    "zh-cn": "zh-hans",
    "zh-hans": "zh-hans",
    "cn": "zh-hans",
    "en": "en",
    "id": "id",
    "in": "id",
    "id-id": "id",
}


class BrowserLanguageMiddleware:
    """Remember language choice and choose a first language from the browser."""

    excluded_prefixes = ("/i18n/", "/media/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supported = {code for code, _label in settings.LANGUAGES}
        path = request.path_info or "/"
        path_language = self._path_language(path, supported)

        if path_language:
            response = self.get_response(request)
            self._remember_language(response, request, path_language)
            return response

        if not self._is_excluded(path):
            language = self._preferred_language(request, supported)
            response = redirect(self._localized_path(path, language, request.META.get("QUERY_STRING", "")))
            self._remember_language(response, request, language)
            return response

        return self.get_response(request)

    def _is_excluded(self, path):
        return path == "/favicon.ico" or path.startswith(self.excluded_prefixes)

    def _path_language(self, path, supported):
        parts = path.split("/")
        if len(parts) > 1 and parts[1] in supported:
            return parts[1]
        return ""

    def _preferred_language(self, request, supported):
        cookie_language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, "")
        if cookie_language in supported:
            return cookie_language
        return self._language_from_header(request.META.get("HTTP_ACCEPT_LANGUAGE", ""), supported)

    def _language_from_header(self, header, supported):
        choices = []
        for index, raw_item in enumerate(header.split(",")):
            item = raw_item.strip()
            if not item:
                continue
            tag, *params = item.split(";")
            quality = 1.0
            for param in params:
                param = param.strip()
                if param.startswith("q="):
                    try:
                        quality = float(param[2:])
                    except ValueError:
                        quality = 0.0
            choices.append((-quality, index, tag.lower().replace("_", "-")))

        for _quality, _index, tag in sorted(choices):
            mapped = LANGUAGE_ALIASES.get(tag) or LANGUAGE_ALIASES.get(tag.split("-", 1)[0])
            if mapped in supported:
                return mapped
            if tag.startswith("zh") and "zh-hans" in supported:
                return "zh-hans"
        return settings.LANGUAGE_CODE

    def _localized_path(self, path, language, query_string):
        if path == "/":
            localized = f"/{language}/"
        else:
            localized = f"/{language}{path}"
        if query_string:
            localized = f"{localized}?{query_string}"
        return localized

    def _remember_language(self, response, request, language):
        if request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME) != language:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language, path="/")
