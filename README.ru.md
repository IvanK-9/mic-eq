# Webcam Mic EQ & Diagnostics (`USB Camera MIC`)

[🇬🇧 English](README.md) | **Русский**

Системная коррекция звука микрофона USB-вебкамеры — работает **во всех приложениях сразу** (Discord, Telegram, Zoom, браузер, OBS, игры) с нулевой задержкой, без виртуальных кабелей и с набором скриптов для замера АЧХ и шума «до/после».

Проверено и замерено на USB-вебкамере (`USB\VID_0C45&PID_6301`, `"USB Camera MIC"`) для **Windows (Equalizer APO)** и **Linux / Omarchy (PipeWire `filter-chain` и EasyEffects)**.

---

## Почему звук был плохим (замеры «до и после»)

Анализ сырого сигнала ([metrics/dry_metrics.json](metrics/dry_metrics.json)) в `48000 Гц / 16 бит моно` выявил две проблемы:
1. **Перекос в гул и «бочку»:** жирные пики на **125 Гц** (`+11.2 dB`) и **400 Гц** (`+9.8 dB`), из-за чего `95%` всей энергии голоса сидело ниже `604 Гц` (`spectral_centroid = 379 Гц`).
2. **Обвал разборчивости и верха:** резкий спад после `1.25 кГц` и глубокая дыра на **4 кГц** (`-39.7 dB` от середины), хотя физически капсюль ловит до `12.5–16 кГц` и сетевого фона `50/60/100 Гц` нет.

Перенос камеры с выступа под монитором **на верхнюю рамку монитора** (отверстием микрофона вниз на лицо) сам по себе убрал отражение от стола на `400 Гц`, а 6-полосный параметрический EQ вытянул ясность и верх без клиппинга:

| Метрика | Исходник (`dry`) | Снизу + EQ (`live_test3`) | Сверху на мониторе + EQ (`live_top_eq`) |
|---|---:|---:|---:|
| **Центр спектра** | `379 Гц` | `1269 Гц` | `1048 Гц` |
| **95% энергии до** | `604 Гц` | `3481 Гц` | `3188 Гц` |
| **Коробка `400 Гц`** | `+9.78 dB` | `+4.57 dB` | `-3.86 dB` |
| **Дыра `4 кГц`** | `-39.70 dB` | `-19.28 dB` | `-18.40 dB` |
| **Верх `5–8 кГц`** | `-37.64 dB` | `-17.09 dB` | `-20.25 dB` |
| **Клиппинг** | `0` | `0` | `0` |

---

## Структура репозитория

```text
.
├── analyze_mic.py              # Скрипт спектрального и шумового анализа (Python + numpy)
├── windows/
│   ├── config.txt              # Корневой роутер Equalizer APO (Device: USB Camera MIC)
│   ├── mic-top.txt             # Профиль для размещения сверху на мониторе (основной)
│   └── mic-bottom.txt          # Профиль для размещения под монитором / на столе
├── linux/
│   ├── 99-webcam-eq.conf       # Нативный конфиг PipeWire filter-chain (та же математика)
│   ├── AGENT_INSTALL.md        # Пошаговый runbook для AI-агента на Linux/Omarchy (EN)
│   └── AGENT_INSTALL.ru.md     # Пошаговый runbook для AI-агента на Linux/Omarchy (RU)
└── metrics/                    # JSON-отчёты замеров (локальные .wav в .gitignore)
```

---

## Быстрый старт: Windows (Equalizer APO)

### 1. Параметры микрофона в Windows (`mmsys.cpl`)
Вкладка **Запись** -> **`Микрофон (USB Camera MIC)`** -> **Свойства** -> **Дополнительно**:
- **Формат по умолчанию:** **`1 канал, 16 бит, 48000 Гц (Диск DVD)`** *(важно: в телефонном режиме 16 кГц всё выше 8 кГц физически обрезано)*.
- **Снимите** обе галочки в разделе **Монопольный режим**, чтобы приложения не обходили системную обработку.

### 2. Установка Equalizer APO
В **PowerShell от имени администратора**:
```powershell
choco install equalizerapo -y
```

### 3. Привязка к микрофону (`DeviceSelector.exe`)
> **Нюанс Equalizer APO 1.4.2:** при запуске `DeviceSelector.exe` из другой папки может вылетать ошибка `no Qt platform plugin could be initialized`. Запускайте из каталога установки с явными путями Qt (от администратора):

```powershell
cd "C:\Program Files\EqualizerAPO"
$env:QT_PLUGIN_PATH = "C:\Program Files\EqualizerAPO\qt"
$env:QT_QPA_PLATFORM_PLUGIN_PATH = "C:\Program Files\EqualizerAPO\qt\platforms"
.\DeviceSelector.exe
```

В окне **Device Selector**:
1. Перейдите на вкладку **Capture devices** и поставьте галочку на **`USB Camera MIC`**.
2. Если обычный режим `Pre-mix` не сработает — выделите строку -> **Troubleshooting options** -> выберите **`SFX/EFX`**.
3. Нажмите **OK** (дождитесь перезапуска службы звука или перезагрузите ПК).

### 4. Подключение конфига
> **Важно про права доступа:** служба звука Windows (`NT AUTHORITY\LocalService`) не имеет прав читать файлы из `C:\Users\<user>\...`, поэтому кладите конфиг прямо в `C:\Program Files\EqualizerAPO\config\` (права на запись туда у пользователей открыты).

```powershell
Copy-Item .\windows\config.txt "C:\Program Files\EqualizerAPO\config\config.txt" -Force
Copy-Item .\windows\mic-top.txt "C:\Program Files\EqualizerAPO\config\mic.txt" -Force
```

Правки в `mic.txt` подхватываются **мгновенно на лету** без перезагрузки.

<details>
<summary>Если камера стоит снизу под монитором / на столе</summary>

Скопируйте `windows\mic-bottom.txt` в `mic.txt` вместо `mic-top.txt` — там сильнее прибраны `125 Гц` (`-6.5 dB`) и `380 Гц` (`-8.0 dB`) под отражение от столешницы.

</details>

---

## Быстрый старт: Linux / Omarchy (PipeWire)

> **Настраиваете через AI-агента?** Дайте агенту прочитать [linux/AGENT_INSTALL.ru.md](linux/AGENT_INSTALL.ru.md) (или [linux/AGENT_INSTALL.md](linux/AGENT_INSTALL.md)) — он сам найдёт устройство, пропишет `target.object` без петель и проверит результат по спектру.

### Вариант A: Нативный PipeWire `filter-chain` (без GUI и лишних программ)

Современные дистрибутивы (включая **Omarchy / Arch + Hyprland**, Ubuntu 22.10+, Fedora, Debian 12+) работают на PipeWire со встроенными биквадратными фильтрами (`bq_highpass`, `bq_peaking`, `bq_highshelf`) с той же математикой, что и в Equalizer APO.

1. **Узнайте точное имя источника камеры** (игнорируйте `.monitor`):
   ```bash
   pactl list short sources
   ```
   Ищите устройство вида `alsa_input.usb-0c45_6301-02.mono-fallback`.
2. **Скопируйте конфиг:**
   ```bash
   mkdir -p ~/.config/pipewire/pipewire.conf.d
   cp linux/99-webcam-eq.conf ~/.config/pipewire/pipewire.conf.d/99-webcam-eq.conf
   ```
   Раскомментируйте `target.object = "..."` в `capture.props` и впишите туда точное имя `alsa_input...`, чтобы избежать петли маршрутизации.
3. **Перезапустите PipeWire и WirePlumber:**
   ```bash
   systemctl --user restart pipewire pipewire-pulse wireplumber
   ```
4. **Назначьте `USB Camera MIC (EQ)` микрофоном по умолчанию:**
   ```bash
   wpctl status
   wpctl set-default <ID_источника>
   ```
   *(Теперь Discord, Telegram, браузер и OBS берут обработанный сигнал автоматически. Громкость при необходимости регулируется через `pavucontrol` или `wpctl set-volume`.)*

<details>
<summary>Вариант Б: EasyEffects GUI (если хочется крутить ползунки или добавить шумодав/компрессор)</summary>

1. Установите **EasyEffects** (`com.github.wwmm.easyeffects` во Flatpak или из репозитория) + `lsp-plugins`.
2. В разделе **Input -> Equalizer** вбейте 7 точек из `windows/mic-top.txt`:
   - `HPF` `90 Hz` (12 dB/oct)
   - `Peak` `125 Hz`, `-4.5 dB`, `Q 1.5`
   - `Peak` `380 Hz`, `-4.0 dB`, `Q 1.1`
   - `Peak` `780 Hz`, `-3.5 dB`, `Q 1.6`
   - `Peak` `2000 Hz`, `+9.0 dB`, `Q 1.3`
   - `Peak` `4200 Hz`, `+9.5 dB`, `Q 1.4`
   - `High-Shelf` `5500 Hz`, `+8.5 dB`, `Q 0.71`
   - Выходное усиление (`Output`): `+3.5 dB`
3. Включите автозапуск сервиса (`easyeffects --gapplication-service`).

</details>

---

## Замер и калибровка под свой голос (`analyze_mic.py`)

Нужны `ffmpeg` и Python `numpy`. Запишите ~3–4 сек тишины + ~15 сек обычной речи:

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

---

## Полезные мелочи без покупки стоек

- **Сверху монитора лучше, чем снизу:** пропадает «бочка» от столешницы, тень от клавиатуры/рук и стук клавиш.
- **Следите за отверстием микрофона:** шторка приватности или край рамки не должны перекрывать дырочку капсюля, и лучше чуть наклонить камеру на лицо.
- **Отключите агрессивный AGC в звонилках:** автоусиление в Discord/Zoom/Telegram в паузах любит вытягивать шум вентиляторов поверх чистого EQ.
