#!/usr/bin/env python3
"""Контроль доступности сервиса во время развёртывания.

Непрерывно опрашивает адрес /api/version через шлюз и считает ответы по версиям.
Любой ответ, отличный от 200, или сетевая ошибка считается отказом.

    loadcheck.py <адрес> <длительность, с> [запросов в секунду]
"""
import json
import ssl
import sys
import time
import urllib.request
from collections import Counter

base_url = sys.argv[1].rstrip("/")
duration = float(sys.argv[2])
rate = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
ca_cert = __import__("os").environ.get("CA_CERT")

context = ssl.create_default_context(cafile=ca_cert) if ca_cert else ssl.create_default_context()
# Корневой сертификат учебного стенда выпущен без расширения keyUsage, строгая проверка
# X.509 его отклоняет. Цепочка и имя узла по-прежнему проверяются.
context.verify_flags &= ~ssl.VERIFY_X509_STRICT
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
)

versions: Counter[str] = Counter()
instances: set[str] = set()
failures: list[str] = []
timeline: list[tuple[int, str]] = []
slowest = 0.0
started = time.monotonic()
total = 0
while (elapsed := time.monotonic() - started) < duration:
    t0 = time.monotonic()
    total += 1
    try:
        with opener.open(f"{base_url}/api/version", timeout=5) as response:
            info = json.load(response)
        versions[info["version"]] += 1
        instances.add(info["instance"])
        second = int(elapsed)
        if not timeline or timeline[-1][1] != info["version"]:
            timeline.append((second, info["version"]))
    except Exception as error:  # noqa: BLE001 - любой сбой фиксируется как отказ
        failures.append(f"{elapsed:6.1f} c  {type(error).__name__}: {error}")
    took = time.monotonic() - t0
    slowest = max(slowest, took)
    time.sleep(max(0.0, 1.0 / rate - took))

print(f"Адрес: {base_url}")
print(f"Длительность: {duration:.0f} с, запросов: {total}, отказов: {len(failures)}")
print(f"Самый долгий ответ: {slowest * 1000:.0f} мс, экземпляров серверной части: {len(instances)}")
for version, count in versions.most_common():
    print(f"  версия {version}: {count} ответов")
print("Смена версии в ответах (секунда от начала, версия):")
for second, version in timeline[:40]:
    print(f"  {second:4d} c  {version}")
for line in failures[:20]:
    print("  ОТКАЗ", line)
sys.exit(1 if failures else 0)
