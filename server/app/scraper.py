"""Errores comunes de los catálogos públicos de imágenes."""


class ScraperError(Exception):
    def __init__(self, message, *, stop_batch=False):
        super().__init__(message)
        self.stop_batch = stop_batch
