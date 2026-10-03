"""Canonical Jan-e Jaraid source registry.

This file is the backend counterpart of the press directory.  Every outlet we
want to monitor belongs here even when it has no usable RSS yet.  The ingestion
pipeline can progressively attach RSS/API/custom collectors without losing
visibility of the remaining queue.

Important: source-level editorial exclusions in app.ingestion.service still
apply to every collector.
"""
PRESS_REGISTRY = [
    # name, homepage, language, scope
    ("Press TV","https://www.presstv.ir","en","iran-agency"),
    ("Tehran Times","https://www.tehrantimes.com","en","iran-paper"),
    ("Al-Alam","https://www.alalam.ir","ar","iran-agency"),
    ("Al-Monitor","https://www.al-monitor.com","en","world"),
    ("Al Jazeera","https://www.aljazeera.com","en","world"),
    ("BBC","https://www.bbc.com/news","en","world"),
    ("The Guardian","https://www.theguardian.com","en","world"),
    ("El País","https://elpais.com","es","world"),
    ("France 24","https://www.france24.com","fr","world"),
    ("RFI","https://www.rfi.fr","fr","world"),
    ("Anadolu Ajansı","https://www.aa.com.tr","tr","world"),
]

# Registry policy: a directory entry without a collector is a tracked backlog,
# not an implicitly active source.  UI status must be based on actual ingestion
# logs / exported story counts.
