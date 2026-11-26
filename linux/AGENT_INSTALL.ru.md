# Инструкция для AI-агента: установка и настройка на Linux (в т.ч. Omarchy / Arch)

[🇬🇧 English](AGENT_INSTALL.md) | **Русский**

Этот файл предназначен для автономного запуска AI-агентом в среде Linux (особенно **Omarchy / Arch + Hyprland + PipeWire + WirePlumber**, а также Ubuntu, Fedora, Debian) на том же железе — USB-вебкамере `VID_0C45:PID_6301` (`USB Camera MIC`).

Цель: развернуть **системную** обработку микрофона (работает во всех приложениях: Discord, Telegram, Zoom, браузер, OBS, игры) с минимальной задержкой, привязать к физическому устройству, выставить его микрофоном по умолчанию и проверить результат замером спектра.

---

## Правила для агента

1. **Не угадывай имя устройства** — сначала получи точный идентификатор источника из PipeWire / WirePlumber (`wpctl status`, `pactl list short sources`).
2. **Не создавай петлю маршрутизации:** в `linux/99-webcam-eq.conf` обязательно раскомментируй и задай `target.object` равным точному `node.name` физической вебкамеры (`alsa_input...`), прежде чем делать виртуальный источник `USB Camera MIC (EQ)` дефолтным.
3. **Не ставь Python-пакеты через глобальный `pip`** (на Arch/Omarchy действует PEP 668): для `analyze_mic.py` используй либо системный пакет `python-numpy` (`sudo pacman -S --needed ffmpeg python-numpy`), либо локальный `.venv`.
4. **На Omarchy / Arch всегда перезапускай вместе с `wireplumber`:** `systemctl --user restart pipewire pipewire-pulse wireplumber`.
5. **Не запускай запись микрофона внезапно** — перед записью предупреди пользователя, чтобы он успел помолчать 3 сек (шумовая полка) и сказать тестовую фразу.

---

## Шаг 1. Проверка окружения и аудиостека

Выполни диагностику:

```bash
systemctl --user is-active pipewire pipewire-pulse wireplumber
pactl info | grep -E "Server Name|Default Source"
lsusb | grep -i 0c45 || true
```

- Если `pipewire`, `pipewire-pulse` и `wireplumber` активны (стандарт для **Omarchy**) — используй сценарий ниже.
- Если в системе чистый PulseAudio без PipeWire, предложи пользователю либо перейти на PipeWire, либо настроить EasyEffects/PulseEffects вручную по параметрам из `README.ru.md`.

---

## Шаг 2. Поиск физической вебкамеры и проверка частоты (48 кГц)

Найди точное имя аппаратного источника (игнорируй `.monitor`):

```bash
pactl list short sources
wpctl status
```

Ищи источник с `0c45` / `6301` / `USB_Camera` (обычно вида `alsa_input.usb-0c45_6301-02.mono-fallback` или похожее).

Проверь поддерживаемый формат и громкость:

```bash
pactl list sources | grep -A 15 -E "Name: .*0c45|Name: .*USB_Camera"
```

Убедись, что:
- частота `48000Hz` (не `16000Hz`, иначе верх физически обрезается на 8 кГц);
- источник не замьючен (`Mute: no`).

Если найдено несколько USB-микрофонов или непонятно, какой именно физический источник относится к камере, уточни у пользователя перед правкой конфига. Также уточни, где стоит камера:
- **сверху на мониторе** (по умолчанию в `linux/99-webcam-eq.conf`) — микрофоном вниз в сторону лица;
- **под монитором / на столе** — тогда параметры фильтров нужно заменить на значения из `windows/mic-bottom.txt` (`HP 92`, `125: -6.5`, `380: -8.0`, `2050: +7.5 Q=1.0`, `4500: +9.5 Q=1.4`, `HS 6200: +8.5`, убрать `780`).

---

## Шаг 3. Установка PipeWire `filter-chain` конфига

1. Создай директорию пользовательских конфигов PipeWire и скопируй профиль:
   ```bash
   mkdir -p ~/.config/pipewire/pipewire.conf.d
   cp linux/99-webcam-eq.conf ~/.config/pipewire/pipewire.conf.d/99-webcam-eq.conf
   ```
2. В файле `~/.config/pipewire/pipewire.conf.d/99-webcam-eq.conf` внутри блока `capture.props` раскомментируй строку `target.object` и впиши точное `node.name` вебкамеры, найденное на Шаге 2:
   ```text
   target.object = "<EXACT_ALSA_INPUT_NODE_NAME>"
   ```
   *(Если в системе старый PipeWire `< 0.3.64`, где `target.object` не поддерживается, используй `node.target = "<EXACT_ALSA_INPUT_NODE_NAME>"`.)*

---

## Шаг 4. Запуск, выбор по умолчанию и проверка логов

Перезапусти пользовательский PipeWire **вместе с WirePlumber** и проверь, что нет ошибок в логах:

```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
sleep 2
systemctl --user is-active pipewire pipewire-pulse wireplumber
journalctl --user -u pipewire -u wireplumber -n 30 --no-pager
```

Убедись, что появился виртуальный источник `USB Camera MIC (EQ)` (`filter_chain.webcam_eq_out`), и сделай его источником по умолчанию через `wpctl` (WirePlumber сохранит выбор после перезагрузки):

```bash
wpctl status
# Найди ID источника "USB Camera MIC (EQ)" в разделе Audio -> Sources и выполни:
wpctl set-default <ID_источника_USB_Camera_MIC_(EQ)>
# Либо через Pulse-совместимый вызов:
# pactl set-default-source filter_chain.webcam_eq_out
```

Если установлен `pw-link`, проверь граф связей (вход цепочки должен быть подключён к аппаратному источнику вебкамеры):

```bash
pw-link -l | grep -A 3 -E "webcam_eq|0c45|USB_Camera" || true
```

---

## Шаг 5. Живой контрольный замер через `analyze_mic.py`

1. Проверь наличие `ffmpeg` и `numpy`:
   ```bash
   command -v ffmpeg
   python3 -c "import numpy; print(numpy.__version__)"
   ```
   Если `ffmpeg` или `numpy` отсутствуют на Omarchy / Arch, можно установить официальные пакеты (`sudo pacman -S --needed ffmpeg python-numpy`), либо для `numpy` создать локальный `.venv` (`python3 -m venv .venv && .venv/bin/pip install numpy`).
2. Предупреди пользователя: **«Сейчас запущу 20-секундную запись: 3 секунды помолчи для замера шума, потом говори обычным голосом (включая слова со свистящими с/ш/щ)»**.
3. После подтверждения пользователя запиши сигнал **с дефолтного источника** (`USB Camera MIC (EQ)`):
   ```bash
   ffmpeg -y -hide_banner -f pulse -ac 1 -ar 48000 -i default -t 20 -c:a pcm_s16le test_linux.wav
   python3 analyze_mic.py test_linux.wav --json-out metrics/test_linux.json
   ```
4. Оцени метрики из `metrics/test_linux.json` (сравни с `metrics/dry_metrics.json` и `metrics/live_top_eq_metrics.json`):
   - `sample_rate_hz == 48000`, `clipped_samples == 0`
   - `global_peak_dbfs` желательно в диапазоне `-10 .. -2 dBFS` (если тише `-10 dBFS` — слегка подними уровень аппаратного входа или виртуального источника через `pactl set-source-volume` / `wpctl set-volume`, не доводя до клиппинга; помни, что на Windows в `mic-top.txt` используется `Preamp: +3.5 dB`)
   - `spectral_centroid_hz` должен вырасти с исходных `~379 Гц` до `~900–1300 Гц`, `spectral_rolloff_95_hz` — до `~2800–3600 Гц`
   - `400 Гц` (`low_mid_mud_200_500`) не должен торчать горбом, провал на `4000 Гц` должен выправиться.
5. Удали временный `test_linux.wav` после проверки (либо оставь локально — `.wav` игнорируются в `.gitignore`).

---

## Шаг 6. Проверка в приложениях

Напомни пользователю:
- В Discord / Telegram / Zoom / Chrome / OBS устройство ввода должно быть **Default** или **`USB Camera MIC (EQ)`**.
- В звонилках желательно отключить агрессивное авто-усиление (AGC), если оно вытягивает шум комнаты в паузах.
