# Webcam Mic EQ & Audio Diagnostics (`USB Camera MIC`)

Системная (работает **во всех приложениях сразу** — Discord, Telegram, Zoom, браузер, OBS, игры) коррекция звука микрофона вебкамеры (`USB\VID_0C45&PID_6301`) с набором скриптов для спектрального анализа и замеров «до/после».

---

## Что было не так с исходным звуком (замеры)

Анализ сырого сигнала ([metrics/dry_metrics.json](metrics/dry_metrics.json)) на `48000 Hz / 16-bit mono`:

- **Жёсткий перекос в гул и «бочку»:** пики на **125 Гц** (`+11.2 dB`) и **400 Гц** (`+9.8 dB`).
- **Низкий центр спектра:** `spectral_centroid = 379 Гц`, **85%** всей энергии до `475 Гц`, **95%** — до `604 Гц`.
- **Провал в разборчивости и верхах:** после `1.25 кГц` резкий обвал, глубокая дыра на **4 кГц** (`-39.7 dB` относительно середины), верх `5–12 кГц` провален на `-37..-42 dB`.
- **Инфранизкий шум:** основной фоновый гул сидел в `20–80 Гц` (SNR всего `3.6 dB`).
- **Потенциал капсюля:** физически слышит до `12.5–16 кГц` (на `12.5 кГц` SNR `+9.2 dB`), сетевого фона `50/60/100 Гц` нет.

### Результат после коррекции (живые замеры на Windows через Equalizer APO)

| Метрика | Исходник (`dry`) | Снизу + EQ (`live_test3`) | Сверху на мониторе + EQ (`live_top_eq`) |
|---|---:|---:|---:|
| **Центр спектра** | `379 Гц` | `1269 Гц` | `1048 Гц` |
| **95% энергии до** | `604 Гц` | `3481 Гц` | `3188 Гц` |
| **Коробка `400 Гц`** | `+9.78 dB` | `+4.57 dB` | `-3.86 dB` (ушёл отскок от стола) |
| **Дыра `4 кГц`** | `-39.70 dB` | `-19.28 dB` | `-18.40 dB` |
| **Верх `5–8 кГц`** | `-37.64 dB` | `-17.09 dB` | `-20.25 dB` |
| **Клиппинг** | `0` | `0` | `0` |

> **Наблюдение по размещению камеры:** перенос камеры с выступа под монитором на верхнюю рамку монитора (микрофоном вниз в сторону лица) сам по себе убрал отражение от столешницы и «бочку» на `400 Гц` (`+4.57 -> -3.86 dB`), поэтому в финальном профиле `mic-top.txt` вырез низа ослаблен и компенсирован `780 Гц` + `2–5.5 кГц`.

---

## Структура репозитория

- [analyze_mic.py](analyze_mic.py) — Python-скрипт (`numpy`) для расчёта шумовой полки, SNR, проверки фона `50/60/100/150 Гц`, спектра по полосам и третьоктавной АЧХ.
- [windows/config.txt](windows/config.txt) — корневой конфиг Equalizer APO (`Device: USB Camera MIC`, `Include: mic.txt`).
- [windows/mic-top.txt](windows/mic-top.txt) — финальный профиль под размещение **сверху на мониторе**.
- [windows/mic-bottom.txt](windows/mic-bottom.txt) — профиль под размещение **под монитором / на столе**.
- [linux/99-webcam-eq.conf](linux/99-webcam-eq.conf) — нативный профиль для **PipeWire `filter-chain`** на Linux.
- [linux/AGENT_INSTALL.md](linux/AGENT_INSTALL.md) — пошаговый runbook для AI-агента по автоматической установке, маршрутизации и проверке на Linux.
- [metrics/](metrics/) — сохранённые JSON-метрики замеров.

---

## Настройка на Windows (Equalizer APO)

### 1. Параметры устройства в Windows (`mmsys.cpl`)
Вкладка **Запись** -> **`Микрофон (USB Camera MIC)`** -> **Свойства** -> **Дополнительно**:
- Формат по умолчанию: **`1 канал, 16 бит, 48000 Гц (Диск DVD)`** (если выбрать 16 кГц, верх выше 8 кГц физически не пишется).
- **Снять** обе галочки в разделе **Монопольный режим**, чтобы приложения не обходили APO.

### 2. Установка Equalizer APO
В PowerShell **от имени администратора**:
```powershell
choco install equalizerapo -y
```

### 3. Привязка к микрофону (`DeviceSelector.exe`)
В Equalizer APO `1.4.2` при запуске из произвольной папки может падать ошибка Qt (`no Qt platform plugin could be initialized`), поэтому запускаем из каталога установки с явными переменными Qt (от администратора):
```powershell
cd "C:\Program Files\EqualizerAPO"
$env:QT_PLUGIN_PATH = "C:\Program Files\EqualizerAPO\qt"
$env:QT_QPA_PLATFORM_PLUGIN_PATH = "C:\Program Files\EqualizerAPO\qt\platforms"
.\DeviceSelector.exe
```
В окне:
1. Вкладка **Capture devices** -> поставить галочку на **`USB Camera MIC` (`Микрофон`)**.
2. Кликнуть по строке -> **Troubleshooting options** -> если обычный `Pre-mix` не сработает, выбрать **`SFX/EFX`**.
3. Нажать **OK** (дождаться перезапуска аудиослужбы или перезагрузить ПК).

### 4. Подключение конфига
> **Важно про права доступа:** служба звука Windows (`NT AUTHORITY\LocalService`) не может читать файлы из пользовательских папок вроде `C:\Users\<user>\...`, поэтому файлы конфига нужно класть прямо в `C:\Program Files\EqualizerAPO\config\` (на неё у пользователей уже есть права).

```powershell
Copy-Item .\windows\config.txt "C:\Program Files\EqualizerAPO\config\config.txt" -Force
Copy-Item .\windows\mic-top.txt "C:\Program Files\EqualizerAPO\config\mic.txt" -Force
```
Изменения в `mic.txt` подхватываются Equalizer APO мгновенно на лету без перезагрузки.

---

## Настройка на Linux (на том же железе)

> **Для AI-агента:** подробный детерминированный runbook с командами диагностики, привязкой `target.object` и живой верификацией лежит в [linux/AGENT_INSTALL.md](linux/AGENT_INSTALL.md).

На современном Linux (Ubuntu 22.10+, Fedora, Arch, Debian 12+) используются те же самые биквадратные фильтры через **PipeWire** — без стороннего софта, без задержки и системно для всех программ.

### Вариант A: Нативный PipeWire `filter-chain` (аналог Equalizer APO, без GUI)

1. **Найди точное имя микрофона вебкамеры:**
   ```bash
   pactl list short sources
   # или: wpctl status
   ```
   Ищи строку с `0c45` / `6301` / `USB_Camera` (обычно что-то вроде `alsa_input.usb-0c45_6301-02.mono-fallback`).
2. **Проверь формат (48 кГц):** PipeWire по умолчанию работает на `48000 Hz`.
3. **Установи конфиг:**
   ```bash
   mkdir -p ~/.config/pipewire/pipewire.conf.d
   cp linux/99-webcam-eq.conf ~/.config/pipewire/pipewire.conf.d/99-webcam-eq.conf
   ```
   При необходимости раскомментируй `target.object = "..."` в файле и впиши туда имя источника из шага 1.
4. **Перезапусти PipeWire:**
   ```bash
   systemctl --user restart pipewire pipewire-pulse
   ```
5. **Сделай виртуальный источник `USB Camera MIC (EQ)` микрофоном по умолчанию:**
   ```bash
   wpctl status
   wpctl set-default <ID_источника_USB_Camera_MIC_(EQ)>
   ```
   После этого все приложения (Discord, Telegram, браузер, OBS) будут сразу получать обработанный голос. *(Уровень входного усиления при необходимости добавляется в `pavucontrol` или `wpctl set-volume`.)*

### Вариант B: Через GUI (EasyEffects)

Если хочется крутить кривую мышкой или добавить компрессор / шумодав (RNNoise):
1. Установи **EasyEffects** (Flatpak `com.github.wwmm.easyeffects` или пакет из репозитория дистрибутива) + `lsp-plugins`.
2. На вкладке **Input** добавь эффект **Equalizer** и вбей те же 7 точек (`mic-top.txt`):
   - `HPF` 90 Hz (12 dB/oct)
   - `Peak` 125 Hz, `-4.5 dB`, `Q 1.5`
   - `Peak` 380 Hz, `-4.0 dB`, `Q 1.1`
   - `Peak` 780 Hz, `-3.5 dB`, `Q 1.6`
   - `Peak` 2000 Hz, `+9.0 dB`, `Q 1.3`
   - `Peak` 4200 Hz, `+9.5 dB`, `Q 1.4`
   - `High-Shelf` 5500 Hz, `+8.5 dB`, `Q 0.71`
   - Выходное усиление (`Output`): `+3.5 dB`
3. Включи автозапуск сервиса в настройках EasyEffects (`easyeffects --gapplication-service`).

---

## Замер и анализ звука (`analyze_mic.py`)

Зависимости: `ffmpeg` и Python (`numpy`).

**Windows:**
```powershell
ffmpeg -y -f dshow -sample_rate 48000 -channels 1 -i audio="Микрофон (USB Camera MIC)" -t 20 -c:a pcm_s16le test.wav
python analyze_mic.py test.wav --json-out metrics/test.json
```

**Linux (PipeWire / PulseAudio):**
```bash
ffmpeg -y -f pulse -ac 1 -ar 48000 -i default -t 20 -c:a pcm_s16le test.wav
python3 analyze_mic.py test.wav --json-out metrics/test.json
```
