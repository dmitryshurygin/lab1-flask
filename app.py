import base64
import hashlib
import io
import os
import random
import re
import secrets
from datetime import date

import matplotlib

matplotlib.use("Agg")  # Работа без GUI на сервере или в Docker.

import matplotlib.pyplot as plt
import numpy as np
from flask import Flask, make_response, render_template_string, request, session
from PIL import Image, ImageDraw, ImageFont


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(16)

VERIFY_TOKEN = "TUSUR-SHURYGIN-20261123-B1A2C362"

PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Лабораторная работа 1 - Вариант 17</title>
    <style>
        body { font-family: sans-serif; max-width: 1100px; margin: 30px auto; }
        form { background: #f4f4f4; padding: 16px; border-radius: 8px; }
        img { max-width: 480px; margin: 8px 0; border: 1px solid #ccc; }
        .row { display: flex; gap: 24px; flex-wrap: wrap; }
        h2 { margin-top: 24px; }
        .captcha { display: flex; align-items: center; gap: 10px; }
        .captcha img { border: 1px solid #999; max-width: none; }
    </style>
</head>
<body>
    <h1>Лабораторная работа 1 - Вариант 17</h1>

    {% if error %}
        <p style="color: red;"><b>{{ error }}</b></p>
    {% endif %}

    <form method="post" enctype="multipart/form-data">
        <p><input type="file" name="image" accept="image/*" required></p>
        <p>
            Направление полос:
            <label><input type="radio" name="direction" value="vertical" checked> вертикальные</label>
            <label><input type="radio" name="direction" value="horizontal"> горизонтальные</label>
        </p>
        <p>Ширина полосы (в пикселях):
            <input type="number" name="width" value="50" min="1" required>
        </p>
        <p class="captcha">
            <span>Капча:</span>
            <img src="{{ captcha_img }}" alt="капча">
            <input type="text" name="captcha" placeholder="Ответ" required>
        </p>
        <p><button type="submit">Выполнить</button></p>
    </form>

    {% if orig_img %}
    <h2>Результат</h2>
    <div class="row">
        <div>
            <p>Исходное изображение</p>
            <img src="{{ orig_img }}" alt="исходное">
        </div>
        <div>
            <p>Результат</p>
            <img src="{{ result_img }}" alt="результат">
        </div>
    </div>
    <h2>Гистограмма</h2>
    <img src="{{ hist_img }}" alt="гистограмма" style="max-width: 700px;">
    {% endif %}
</body>
</html>
"""


def to_base64(pil_img):
    """Преобразуем изображение в PNG для вставки в HTML."""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def swap_stripes(pil_img, width, direction):
    """Меняем местами соседние полосы. Остаток оставляем без изменений."""
    arr = np.array(pil_img).copy()
    axis = 1 if direction == "vertical" else 0
    n = arr.shape[axis]

    if width < 1 or n < 2 * width:
        return pil_img

    def take(start):
        return np.take(arr, np.arange(start, start + width), axis=axis)

    for i in range(0, n - 2 * width + 1, 2 * width):
        a, b = take(i), take(i + width)
        if axis == 1:
            arr[:, i:i + width] = b
            arr[:, i + width:i + 2 * width] = a
        else:
            arr[i:i + width, :] = b
            arr[i + width:i + 2 * width, :] = a

    return Image.fromarray(arr)


def build_histogram(pil_img):
    """Строим гистограмму распределения цветов RGB."""
    arr = np.array(pil_img.convert("RGB"))
    fig, ax = plt.subplots(figsize=(8, 4))

    for ch, color in enumerate(("r", "g", "b")):
        ax.hist(
            arr[..., ch].ravel(),
            bins=256,
            range=(0, 256),
            color=color,
            alpha=0.5,
            label=f"{color.upper()} канал",
        )

    ax.set_title("Распределение цветов")
    ax.set_xlabel("Яркость канала")
    ax.set_ylabel("Число пикселей")
    ax.legend()

    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def make_captcha():
    """Генерируем арифметическую капчу и сохраняем хеш ответа в сессии."""
    a, b = random.randint(2, 15), random.randint(2, 15)
    op = random.choice(("+", "-"))
    answer = a + b if op == "+" else abs(a - b)

    if op == "-" and a < b:
        a, b = b, a

    text = f"{a} {op} {b} = ?"
    img = Image.new("RGB", (150, 50), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 26)
    except OSError:
        font = ImageFont.load_default()

    x = 15
    for ch in text:
        draw.text(
            (x, random.randint(8, 14)),
            ch,
            fill=(random.randint(0, 100),) * 3,
            font=font,
        )
        x += 11

    for _ in range(4):
        draw.line(
            [
                (random.randint(0, 150), random.randint(0, 50)),
                (random.randint(0, 150), random.randint(0, 50)),
            ],
            fill=(180, 180, 180),
            width=1,
        )

    session["captcha_hash"] = hashlib.sha256(str(answer).encode()).hexdigest()
    return to_base64(img)


def check_captcha(user_answer):
    """Проверяем ответ пользователя и удаляем использованную капчу."""
    expected = session.pop("captcha_hash", None)
    if not expected:
        return False

    user = str(user_answer).strip()
    actual = hashlib.sha256(user.encode()).hexdigest()
    return secrets.compare_digest(actual, expected)


@app.route("/", methods=["GET", "POST"])
def index():
    ctx = dict(orig_img=None, result_img=None, hist_img=None, error=None)

    if request.method == "POST":
        if not check_captcha(request.form.get("captcha")):
            ctx["error"] = "Неверный ответ на капчу. Попробуйте ещё раз."
        else:
            file = request.files.get("image")

            if not (file and file.filename):
                ctx["error"] = "Файл не выбран."
            else:
                try:
                    img = Image.open(file.stream).convert("RGB")
                except Exception:
                    ctx["error"] = "Не удалось открыть файл — это не изображение."
                else:
                    try:
                        width = max(1, int(request.form.get("width", 50) or 50))
                        direction = request.form.get("direction", "vertical")
                        ctx["orig_img"] = to_base64(img)
                        ctx["result_img"] = to_base64(
                            swap_stripes(img, width, direction)
                        )
                        ctx["hist_img"] = build_histogram(img)
                    except Exception as e:
                        ctx["error"] = f"Ошибка обработки: {e}"

    ctx["captcha_img"] = make_captcha()
    return render_template_string(PAGE, **ctx)


def normalize_html(html: str) -> str:
    """Нормализуем HTML по правилам задания перед вычислением хеша."""
    lines = [line.strip() for line in html.split("\n")]
    lines = [line for line in lines if line]
    lines = [re.sub(r"\s+", " ", line) for line in lines]
    return "\n".join(lines)


@app.route("/verify")
def verify():
    today = date.today().isoformat()
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Верификация</title>
</head>
<body>
    <h1>Верификация</h1>
    <p>Token: {VERIFY_TOKEN}</p>
    <p>Date: {today}</p>
</body>
</html>
"""

    normalized = normalize_html(html)
    body_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    response = make_response(html)
    response.headers["X-Verify-Hash"] = body_hash
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
