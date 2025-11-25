# PrismaLite_Video_Module

## 1. Назначение

Видеомодуль обеспечивает:
- приём видеопотоков от DVR/IP-камер (RTSP);
- проксирование и трансформацию потоков (RTSP→HLS/WebRTC);
- безопасный доступ к live и архиву через backend;
- синхронизацию видео с кассовыми событиями и инцидентами;
- мониторинг состояния DVR и обработку ошибок.

## 2. Архитектура (RTSP → Proxy → HLS → UI)

```
[IP CAM / DVR] --RTSP--> [Video Proxy] --> [Transcoder/Segmenter] --> [HLS Store]
                                             |                                |
                                             | HTTP/HLS + Auth                |
                                             v                                |
                                        [Backend API]  <---->             [Web UI]
```

Элементы:
- **RTSP Source**: камеры или DVR (Hikvision, Dahua, CSI).
- **Video Proxy Service**: поддерживает RTSP-сессии, управляет драйверами.
- **Transcoder/Segmenter**: ffmpeg/gstreamer, режет поток на HLS сегменты (TS/fMP4).
- **HLS Store**: локальный диск, NFS, S3-совместимое хранилище.
- **Backend API**: выдаёт временные токены/URL, применяет ACL.
- **UI**: HLS.js или WebRTC player.

## 3. Live поток

1. UI запрашивает `GET /api/video/live?camera_id=...`.
2. Backend проверяет ACL, лицензии, лимиты.
3. Backend генерирует токен (`exp ≤ 60s`) и URL вида `/hls/live/{camera}/index.m3u8?token=...`.
4. Плеер загружает плейлист и сегменты.
5. Video Proxy поддерживает постоянную RTSP-сессию с DVR.

## 4. Архив (replay)

1. UI запрашивает `GET /api/video/replay?camera_id=&from=&to=`.
2. Backend обращается к DVR API или локальному архиву.
3. Если архив на DVR:
   - DVR выдаёт RTSP с параметрами времени.
   - Proxy/Transcoder режет на сегменты on-the-fly.
4. Если архив локален:
   - Backend находит сегменты в HLS Store и формирует плейлист.

## 5. DVR API и драйверы

### 5.1 Общий интерфейс
```python
class DvrDriver:
    def connect(self, host, port, login, password): ...
    def get_live_rtsp(self, channel_id) -> str: ...
    def get_replay_rtsp(self, channel_id, from_ts, to_ts) -> str: ...
    def list_channels(self) -> list: ...
    def get_recording_ranges(self, channel_id, day) -> list: ...
    def health_check(self) -> bool: ...
```

### 5.2 Hikvision
- Протокол: ISAPI + RTSP.
- Live: `rtsp://user:pass@ip:554/Streaming/Channels/101/`.
- Replay: `rtsp://.../Streaming/tracks/101/?starttime=...&endtime=...`.
- Дополнительно: API для списка каналов, авторизация digest/basic.

### 5.3 Dahua
- Протокол: CGI + RTSP.
- Live: `rtsp://user:pass@ip:554/cam/realmonitor?channel=1&subtype=0`.
- Replay: `rtsp://.../cam/playback?...`.
- Особенности: нестабильность при нагрузке → retry, ограничение сессий.

### 5.4 CSI
- Приватное API (см. интеграционную документацию).
- Требования: выдача RTSP live/replay, health-check endpoint.

## 6. Ошибки и обработка

Классы ошибок:
1. `NetworkError` — таймаут/недоступен DVR.
2. `AuthError` — неверные креды, блокировка.
3. `StreamError` — DVR не отдаёт поток.
4. `NotFoundError` — нет архива за период.
5. `OverloadError` — лимит сессий.
6. `InternalError` — ошибки proxy/transcoder.

Стратегия:
- `NetworkError`: 3–5 retry с exponential backoff; при отказе — лог, уведомление.
- `AuthError`: немедленно 401 `DVR_AUTH_FAILED`, аудит.
- `StreamError`: одна повторная попытка, затем `502 VIDEO_STREAM_ERROR`.
- `NotFoundError`: `404 VIDEO_ARCHIVE_NOT_FOUND`.
- `OverloadError`: `503 DVR_OVERLOADED`, можно ставить в очередь.
- `InternalError`: `500 VIDEO_INTERNAL_ERROR`, лог с stacktrace.

Формат ответа:
```json
{
  "error": "DVR_OVERLOADED",
  "message": "DVR не может принять ещё одну сессию",
  "details": {
    "camera_id": "cam-01",
    "timestamp": "2025-11-24T12:00:00Z"
  }
}
```

## 7. Нагрузочные сценарии

### 7.1 Live просмотр
- 16 камер × 4 Мбит/с = 64 Мбит/с входящего RTSP.
- 10 операторов по 4 камеры (квадратор) → 40 HLS сессий.
- Требования: RTSP→HLS без падений, delay ≤ 3–4 секунды.

### 7.2 Массовый архив
- 5 аналитиков параллельно смотрят архив по 1–2 камерам.
- Нагрузка на DVR по поиску записей; нужно ограничение сессий, очередь.
- Кэширование недавно запрошенных диапазонов.

### 7.3 Пиковый инцидент
- Массовое открытие видео по одному типу инцидента.
- Требуется rate limiting, приоритет live над архивом, downgrade качества.

## 8. Оптимизации

- Субпотоки (substream) с низким битрейтом для квадратора.
- Адаптивный HLS (несколько качеств).
- Разделение воркеров трансформации (live vs archive).
- Горизонтальный масштаб Video Proxy (шардирование по магазинам/камерам).
- SSD/NVMe для кэша сегментов; S3 для долгого хранения.

## 9. Мониторинг и алерты

Метрики:
- `active_rtsp_sessions`
- `hls_sessions_total`
- `segment_latency_seconds`
- `dvr_errors_total` (по типам)
- размер/состояние HLS storage

Алерты:
- >80% лимита RTSP сессий.
- Резкий рост `DVR_OVERLOADED`.
- Падение Video Proxy/Transcoder.
- Наличие пропусков в сегментах (gap detection).

## 10. Безопасность

- Все запросы к `/video/*` проходят ACL, tenant isolation, лицензирование.
- Токены HLS подписываются backend'ом, single-use.
- Ограничения на IP-адреса DVR, отдельный VLAN/VPN.
- Логи доступа к видео попадают в `audit_log`.
- Возможность включить watermark на видео (roadmap).

## 11. Хранение и retention

- Сегменты HLS: хранятся 7–30 дней (зависит от политики/лицензии).
- Архивы старше retention — автоматически удаляются (batch job).
- При необходимости long-term storage: выгрузка в холодное хранилище (S3 Glacier и т.п.).
- Контроль свободного места; alert при <15%.

## 12. Связь с событиями и инцидентами

- Каждое событие может иметь запись в `video_links` со смещением ±N секунд.
- При создании инцидента сохраняется ссылка на video segment.
- UI: клик по событию → backend ищет `video_links` (если нет — запрос на построение on-demand).

## 13. Процессы обслуживания

- Проверка соединения с DVR каждые `N` минут (health-check).
- Ротация логов proxy/transcoder.
- Обновление драйверов DVR при выходе новых firmware.
- Нагрузочные тесты (см. `PrismaLite_Test_Plan.md`).

## 14. Открытые вопросы

| Тема | Вопрос | Ответственный |
|------|--------|---------------|
| WebRTC support | Нужен ли прямой WebRTC для live | Product + Frontend |
| Edge storage | Поддержка локальных хранилищ в магазинах | DevOps + Video |
| Watermark | Требования по водяным знакам/DRM | Security + Product |

Документ обновляется при изменении видеоподсистемы или добавлении новых DVR-поставщиков.

