"""Расчёт режимов сварки полуавтоматом (MIG/MAG) по толщине металла.

Данные в таблицах — практические ориентиры для сварки сплошной проволокой
в нижнем положении. Реальные значения зависят от аппарата, газа, проволоки,
разделки кромок и навыка сварщика.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    """Строка таблицы режимов для одной толщины металла."""

    thickness: float
    current: tuple[int, int]          # А
    voltage: tuple[float, float]      # В
    wire: str                         # диаметр проволоки, мм
    feed: tuple[float, float]         # скорость подачи, м/мин
    gas_flow: tuple[int, int]         # расход газа, л/мин


@dataclass(frozen=True)
class Mode:
    """Режим сварки: материал + таблица толщин."""

    key: str
    title: str
    subtitle: str
    gas: str
    wire_type: str
    polarity: str
    stickout: str
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Calculation:
    """Готовый расчёт для конкретной толщины."""

    mode: Mode
    requested_thickness: float
    thickness: float
    current: tuple[int, int]
    voltage: tuple[float, float]
    wire: str
    feed: tuple[float, float]
    gas_flow: tuple[int, int]
    technique: str
    seam: str
    notes: tuple[str, ...]

    @property
    def is_clamped(self) -> bool:
        return abs(self.requested_thickness - self.thickness) > 1e-9


MODES: dict[str, Mode] = {
    "steel": Mode(
        key="steel",
        title="Сталь",
        subtitle="Конструкционная сталь · MIG/MAG, сплошная проволока",
        gas="Смесь Ar/CO₂ 82/18 (лучше) или CO₂",
        wire_type="Св-08Г2С / ER70S-6",
        polarity="DCEP (плюс на проволоке, минус на массе)",
        stickout="10–15 мм",
        rows=(
            Row(0.8, (35, 55), (15.0, 16.5), "0,6–0,8", (2.0, 3.0), (8, 10)),
            Row(1.0, (45, 65), (15.5, 17.0), "0,8", (2.5, 3.8), (8, 11)),
            Row(1.5, (65, 90), (16.5, 18.0), "0,8", (3.5, 5.0), (10, 12)),
            Row(2.0, (85, 115), (17.5, 19.0), "0,8", (4.0, 5.8), (10, 12)),
            Row(3.0, (115, 155), (19.0, 21.0), "0,8–1,0", (5.0, 7.5), (12, 14)),
            Row(4.0, (145, 190), (20.0, 22.0), "1,0", (6.0, 8.5), (12, 15)),
            Row(5.0, (175, 225), (21.0, 23.5), "1,0–1,2", (7.0, 10.0), (14, 16)),
            Row(6.0, (205, 260), (22.0, 25.0), "1,2", (8.0, 11.0), (14, 18)),
            Row(8.0, (250, 310), (24.0, 28.0), "1,2", (9.5, 13.0), (16, 20)),
            Row(10.0, (290, 360), (26.0, 30.0), "1,2", (11.0, 15.0), (18, 22)),
            Row(12.0, (330, 400), (28.0, 32.0), "1,2–1,6", (12.0, 16.0), (18, 22)),
        ),
    ),
    "stainless": Mode(
        key="stainless",
        title="Нержавейка",
        subtitle="Нержавеющая сталь · MIG, сплошная проволока",
        gas="Смесь Ar/CO₂ 98/2 или тримикс (Ar + He + CO₂)",
        wire_type="Св-08Х19Н10Г2Б / ER308L, ER316L",
        polarity="DCEP (плюс на проволоке, минус на массе)",
        stickout="10–15 мм",
        rows=(
            Row(0.8, (35, 50), (15.0, 16.5), "0,6–0,8", (2.0, 3.0), (10, 12)),
            Row(1.0, (40, 60), (15.5, 17.0), "0,8", (2.5, 3.8), (10, 12)),
            Row(1.5, (55, 80), (16.5, 18.0), "0,8", (3.5, 5.0), (10, 13)),
            Row(2.0, (75, 105), (17.5, 19.0), "0,8", (4.0, 5.8), (11, 13)),
            Row(3.0, (105, 145), (19.0, 21.0), "0,8–1,0", (5.0, 7.5), (12, 14)),
            Row(4.0, (135, 175), (20.0, 22.0), "1,0", (6.0, 8.5), (12, 15)),
            Row(5.0, (160, 205), (21.0, 23.5), "1,0–1,2", (7.0, 10.0), (14, 16)),
            Row(6.0, (190, 245), (22.0, 25.0), "1,2", (8.0, 11.0), (14, 18)),
            Row(8.0, (230, 285), (24.0, 27.0), "1,2", (9.5, 13.0), (16, 20)),
            Row(10.0, (265, 330), (26.0, 29.5), "1,2", (11.0, 15.0), (18, 22)),
            Row(12.0, (300, 370), (28.0, 32.0), "1,2–1,6", (12.0, 16.0), (18, 22)),
        ),
    ),
    "aluminium": Mode(
        key="aluminium",
        title="Алюминий",
        subtitle="Алюминий и сплавы · MIG, чистый аргон",
        gas="Аргон 99,99% (чистый Ar)",
        wire_type="ER4043 или ER5356 (Св-АМг5)",
        polarity="DCEP (плюс на проволоке, минус на массе)",
        stickout="12–18 мм",
        rows=(
            Row(0.8, (45, 65), (16.0, 18.0), "0,8", (3.0, 4.5), (12, 15)),
            Row(1.0, (55, 80), (17.0, 18.5), "0,8–1,0", (4.0, 6.0), (14, 16)),
            Row(1.5, (75, 105), (18.0, 20.0), "1,0", (5.0, 7.0), (14, 17)),
            Row(2.0, (95, 130), (19.0, 21.0), "1,0", (6.0, 8.0), (15, 18)),
            Row(3.0, (130, 175), (20.5, 23.0), "1,0–1,2", (7.0, 10.0), (16, 20)),
            Row(4.0, (165, 220), (22.0, 24.5), "1,2", (8.0, 11.0), (18, 22)),
            Row(5.0, (200, 260), (23.0, 26.0), "1,2", (9.0, 12.0), (18, 22)),
            Row(6.0, (235, 300), (24.5, 27.5), "1,2", (10.0, 13.0), (20, 24)),
            Row(8.0, (285, 360), (26.0, 29.5), "1,2–1,6", (11.0, 15.0), (22, 26)),
            Row(10.0, (330, 420), (28.0, 32.0), "1,6", (13.0, 17.0), (24, 28)),
            Row(12.0, (380, 470), (30.0, 34.0), "1,6", (15.0, 20.0), (24, 28)),
        ),
    ),
}

MODE_ORDER: tuple[str, ...] = ("steel", "stainless", "aluminium")
THICKNESS_BUTTONS: tuple[float, ...] = (1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12)


def fmt_num(value: float) -> str:
    """1.5 -> «1,5», 3.0 -> «3»."""

    if abs(value - round(value)) < 1e-9:
        return str(round(value))
    return f"{value:.1f}".replace(".", ",")


def fmt_thickness(value: float) -> str:
    return f"{fmt_num(value)} мм"


def _fmt_voltage(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _fmt_range(values: tuple[float, float], formatter) -> str:
    low, high = values
    if abs(low - high) < 1e-9:
        return formatter(low)
    return f"{formatter(low)}–{formatter(high)}"


def _lerp(low: float, high: float, ratio: float) -> float:
    return low + (high - low) * ratio


def _lerp_pair(low: tuple[float, float], high: tuple[float, float], ratio: float) -> tuple[float, float]:
    return (
        _lerp(low[0], high[0], ratio),
        _lerp(low[1], high[1], ratio),
    )


def _round_pair(values: tuple[float, float], step: float) -> tuple[float, float]:
    low = round(values[0] / step) * step
    high = round(values[1] / step) * step
    high = max(high, low)
    return low, high


def _interpolate(mode: Mode, thickness: float) -> tuple[Row, Row, float]:
    rows = mode.rows
    if thickness <= rows[0].thickness:
        return rows[0], rows[0], 0.0
    if thickness >= rows[-1].thickness:
        return rows[-1], rows[-1], 0.0

    for index, row in enumerate(rows):
        if abs(row.thickness - thickness) < 1e-9:
            return row, row, 0.0
        if row.thickness > thickness:
            low = rows[index - 1]
            high = row
            ratio = (thickness - low.thickness) / (high.thickness - low.thickness)
            return low, high, ratio
    return rows[-1], rows[-1], 0.0


def _technique(mode_key: str, thickness: float) -> str:
    if mode_key == "aluminium":
        if thickness <= 2:
            return "короткая дуга или импульсный режим, минимальное тепловложение"
        if thickness <= 6:
            return "струйный перенос (spray) в чистом аргоне"
        return "струйный перенос; многопроходная сварка с разделкой кромок"

    if thickness <= 2:
        return "короткая дуга (short arc), точечный или прерывистый шов"
    if thickness <= 6:
        return "короткая дуга или смешанный перенос; со смесью Ar/CO₂ возможен струйный"
    return "струйный перенос (spray) со смесью Ar/CO₂; многопроходная сварка"


def _seam_preparation(thickness: float) -> str:
    if thickness <= 1.5:
        return "стык впритык, зазор 0–0,5 мм; кромки зачистить и обезжирить"
    if thickness <= 4:
        return "V-разделка кромок 30–40°, зазор 1–2 мм, прихватки через 30–50 мм"
    return "V/X-разделка кромок 60–70°, зазор 2–3 мм, многопроходный шов с зачисткой между проходами"


def _build_notes(
    mode: Mode,
    requested_thickness: float,
    thickness: float,
    current: tuple[int, int],
) -> tuple[str, ...]:
    notes: list[str] = []

    if requested_thickness < thickness:
        notes.append(
            f"Для {fmt_thickness(requested_thickness)} данных нет — показан режим "
            f"для {fmt_thickness(thickness)}. Начните с минимума и уменьшите подачу."
        )
    elif requested_thickness > thickness:
        notes.append(
            f"Для {fmt_thickness(requested_thickness)} нужен многопроходный шов; "
            f"показан максимум таблицы — {fmt_thickness(thickness)}."
        )

    if current[1] > 250:
        notes.append(
            "Ток выше 250 А: проверьте возможности аппарата и проводки. "
            "Если мощности не хватает — варите многопроходно на пониженном токе."
        )

    if mode.key == "stainless":
        notes.append(
            "Нержавейка: варите короткими швами с паузами, не перегревайте. "
            "Для труб и ёмкостей делайте продувку аргоном изнутри."
        )
    elif mode.key == "aluminium":
        notes.append(
            "Алюминий: снимите оксид щёткой, используйте тефлоновый канал или спул-ган. "
            "Для толщины больше 6 мм желателен подогрев 100–150 °C."
        )
    elif requested_thickness <= 1.0:
        notes.append(
            "Тонкий металл легко прожечь: начните с минимального тока, "
            "используйте прихватки и прерывистый шов."
        )

    if thickness >= 8:
        notes.append(
            "Толстый металл: без разделки кромок и многопроходного шва "
            "полного провара не будет."
        )

    notes.append("Для вертикальных и потолочных швов снизьте ток и подачу на 10–15%.")
    return tuple(notes)


def calculate(mode_key: str, requested_thickness: float) -> Calculation:
    """Рассчитать настройки полуавтомата для толщины металла."""

    if mode_key not in MODES:
        raise ValueError(f"Неизвестный режим: {mode_key}")
    if requested_thickness <= 0:
        raise ValueError("Толщина должна быть больше нуля")

    mode = MODES[mode_key]
    min_thickness = mode.rows[0].thickness
    max_thickness = mode.rows[-1].thickness
    thickness = min(max(requested_thickness, min_thickness), max_thickness)

    low, high, ratio = _interpolate(mode, thickness)

    if low is high:
        current_raw = (float(low.current[0]), float(low.current[1]))
        voltage_raw = low.voltage
        feed_raw = low.feed
        gas_raw = (float(low.gas_flow[0]), float(low.gas_flow[1]))
    else:
        current_raw = _lerp_pair(
            (float(low.current[0]), float(low.current[1])),
            (float(high.current[0]), float(high.current[1])),
            ratio,
        )
        voltage_raw = _lerp_pair(low.voltage, high.voltage, ratio)
        feed_raw = _lerp_pair(low.feed, high.feed, ratio)
        gas_raw = _lerp_pair(
            (float(low.gas_flow[0]), float(low.gas_flow[1])),
            (float(high.gas_flow[0]), float(high.gas_flow[1])),
            ratio,
        )

    current_pair = _round_pair(current_raw, 5)
    voltage_pair = _round_pair(voltage_raw, 0.5)
    feed_pair = _round_pair(feed_raw, 0.5)
    gas_pair = _round_pair(gas_raw, 1)

    current = (int(current_pair[0]), int(current_pair[1]))
    gas_flow = (int(gas_pair[0]), int(gas_pair[1]))

    # Для диаметра проволоки берём ближайшую толщину сверху:
    # так для 2,5 мм попадёт проволока 0,8–1,0, а не 0,8.
    wire_row = next((row for row in mode.rows if row.thickness >= thickness - 1e-9), mode.rows[-1])

    return Calculation(
        mode=mode,
        requested_thickness=requested_thickness,
        thickness=thickness,
        current=current,
        voltage=voltage_pair,
        wire=wire_row.wire,
        feed=feed_pair,
        gas_flow=gas_flow,
        technique=_technique(mode.key, thickness),
        seam=_seam_preparation(thickness),
        notes=_build_notes(mode, requested_thickness, thickness, current),
    )


def format_calculation(calc: Calculation) -> str:
    """Красиво оформить расчёт для сообщения ВКонтакте."""

    thickness_line = fmt_thickness(calc.requested_thickness)
    if calc.is_clamped:
        thickness_line += f" (расчёт по {fmt_thickness(calc.thickness)})"

    lines = [
        f"⚙️ Режим: {calc.mode.title}",
        f"Толщина: {thickness_line}",
        "",
        "🔧 Настройки полуавтомата:",
        f"• Ток: {_fmt_range(calc.current, fmt_num)} А",
        f"• Напряжение: {_fmt_range(calc.voltage, _fmt_voltage)} В",
        f"• Проволока: ⌀{calc.wire} мм, {calc.mode.wire_type}",
        f"• Подача: {_fmt_range(calc.feed, fmt_num)} м/мин",
        f"• Газ: {calc.mode.gas}",
        f"• Расход газа: {_fmt_range(calc.gas_flow, fmt_num)} л/мин",
        f"• Полярность: {calc.mode.polarity}",
        f"• Вылет электрода: {calc.mode.stickout}",
        "",
        f"📐 Подготовка: {calc.seam}.",
        f"🔥 Перенос: {calc.technique}.",
        "",
        "💡 Советы:",
    ]
    lines.extend(f"• {note}" for note in calc.notes)
    lines.extend(
        [
            "",
            (
                "⚠️ Значения ориентировочные: подстраивайте под свой аппарат, "
                "газ и проволоку. Первый шов сделайте на обрезке."
            ),
        ]
    )
    return "\n".join(lines)


def format_table(mode_key: str) -> str:
    """Компактная таблица всех режимов выбранного материала."""

    if mode_key not in MODES:
        raise ValueError(f"Неизвестный режим: {mode_key}")

    mode = MODES[mode_key]
    lines = [
        f"📊 Таблица режимов: {mode.title}",
        f"Газ: {mode.gas}",
        f"Проволока: {mode.wire_type}",
        "",
    ]
    for row in mode.rows:
        lines.append(
            f"{fmt_thickness(row.thickness)} — "
            f"{_fmt_range(row.current, fmt_num)} А · "
            f"{_fmt_range(row.voltage, _fmt_voltage)} В · "
            f"⌀{row.wire} мм"
        )
    lines.extend(
        [
            "",
            (
                "Нажмите кнопку с толщиной, чтобы получить полный расчёт: "
                "подачу, расход газа и советы."
            ),
        ]
    )
    return "\n".join(lines)
