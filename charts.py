import io
from datetime import date, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # без окна, только в файл
import matplotlib.pyplot as plt

from sheets import get_operations
from categories import get_type


def weekly_chart() -> bytes:
    """
    Рисует график расходов за последние 7 дней.
    Возвращает PNG в виде байтов (готово к отправке в Telegram).
    """
    today = date.today()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    day_set = set(days)

    totals = defaultdict(float)
    for op in get_operations():
        if op["date"] in day_set:
            # только расходы и долги, не доходы
            t = get_type(op["category"])
            if t in ("expense", "debt"):
                totals[op["date"]] += op["amount"]

    labels = [d.strftime("%d.%m") for d in days]
    values = [totals[d] for d in days]

    # Русский шрифт для сумм на графике
    plt.rcParams["font.family"] = "DejaVu Sans"

    fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=140)
    bars = ax.bar(labels, values, color="#4C8BF5", edgecolor="#2A5FB0")

    ax.set_title("Расходы за последние 7 дней, ₽", fontsize=12)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Пишем суммы над столбцами
    for bar, v in zip(bars, values):
        if v > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{int(v):,}".replace(",", " "),
                ha="center", va="bottom", fontsize=8,
            )

    # Автоматически поднимаем верх, чтобы цифры влезли
    if max(values) > 0:
        ax.set_ylim(0, max(values) * 1.15)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()