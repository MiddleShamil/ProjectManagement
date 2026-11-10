#!/usr/bin/env python3
"""Фаза 1. Выбор концепции проекта.

Нечёткий коллективный TOPSIS (трёхточечные оценки) и чёткий коллективный МАИ.
Чистый Python, без сторонних библиотек. Запуск: python3 phase1.py
Скрипт печатает итог и пересобирает README.md в своей папке.
"""
from math import prod, sqrt
from pathlib import Path

# ---------------------------------------------------------------- исходные данные
EXPERTS = ["Абдуллаев Д.", "Хисаметдинов М.", "Саввинов Д."]

ALTS = {
    "A1": ("EventPass", "Веб-сервис записи на студенческие мероприятия с QR-билетом и чек-ином на входе",
           "участник, организатор, администратор; запись, лист ожидания, чек-ин, уведомления, статистика"),
    "A2": ("SplitBot", "Telegram-бот учёта совместных расходов компании (поездки, съёмная квартира)",
           "участник группы; добавить расход, разделить, взаимозачёт, напоминание о долге"),
    "A3": ("RoomBook", "Сервис бронирования аудиторий и переговорных в вузе",
           "студент, сотрудник, администратор; поиск слота, бронь, отмена, согласование, расписание"),
    "A4": ("HabitDuel", "Мобильный трекер привычек с челленджами между друзьями",
           "пользователь, друг; привычка, отметка, челлендж, рейтинг, пуш-напоминания"),
}

# (код, название, тип): benefit — больше лучше, cost — меньше лучше
CRITERIA = [
    ("C1", "Знакомство команды с предметной областью", "benefit"),
    ("C2", "Компактность: MVP укладывается в 10–15 use cases", "benefit"),
    ("C3", "Пригодность для оценки (COSMIC, UCP): разные акторы, явные потоки данных", "benefit"),
    ("C4", "Пригодность для планирования (фазы 4–5): 20–25 задач, разные специальности", "benefit"),
    ("C5", "Техническая неопределённость и риск", "cost"),
]

# Важность критериев, шкала 1–10, по одному числу от каждого эксперта (порядок как в EXPERTS)
IMPORTANCE = {"C1": [7, 6, 8], "C2": [9, 8, 8], "C3": [8, 9, 7], "C4": [6, 7, 8], "C5": [5, 7, 6]}

# Оценки альтернатив по критериям, шкала 1–10 (для C5 — величина риска)
SCORES = {
    "A1": {"C1": [9, 8, 9], "C2": [8, 7, 8], "C3": [9, 8, 9], "C4": [8, 8, 7], "C5": [4, 5, 3]},
    "A2": {"C1": [7, 8, 6], "C2": [9, 9, 8], "C3": [5, 6, 4], "C4": [5, 4, 6], "C5": [3, 2, 4]},
    "A3": {"C1": [8, 7, 8], "C2": [7, 8, 6], "C3": [8, 7, 8], "C4": [7, 7, 8], "C5": [5, 4, 5]},
    "A4": {"C1": [6, 7, 5], "C2": [6, 5, 7], "C3": [6, 7, 6], "C4": [8, 7, 9], "C5": [7, 8, 6]},
}

A = list(ALTS)
C = [c[0] for c in CRITERIA]
KIND = {c[0]: c[2] for c in CRITERIA}
RI = {3: 0.58, 4: 0.90, 5: 1.12}  # случайный индекс согласованности Саати


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def tri(values):
    """Три экспертные оценки -> треугольное число (пессим., ожидаемая, оптим.)."""
    return tuple(sorted(values))


def ftri(t, nd=3):
    return "(" + "; ".join(f"{x:.{nd}f}".rstrip("0").rstrip(".") if nd else str(x) for x in t) + ")"


def ranks(score):
    order = sorted(score, key=score.get, reverse=True)
    return {a: order.index(a) + 1 for a in score}


# ---------------------------------------------------------------- нечёткий TOPSIS
def fuzzy_topsis():
    W = {c: tuple(x / 10 for x in tri(IMPORTANCE[c])) for c in C}
    X = {a: {c: tri(SCORES[a][c]) for c in C} for a in A}
    R = {a: {} for a in A}
    for c in C:
        if KIND[c] == "benefit":
            u_max = max(X[a][c][2] for a in A)
            for a in A:
                R[a][c] = tuple(x / u_max for x in X[a][c])
        else:
            l_min = min(X[a][c][0] for a in A)
            for a in A:
                l, m, u = X[a][c]
                R[a][c] = (l_min / u, l_min / m, l_min / l)
    V = {a: {c: tuple(r * w for r, w in zip(R[a][c], W[c])) for c in C} for a in A}
    fpis = {c: (max(V[a][c][2] for a in A),) * 3 for c in C}
    fnis = {c: (min(V[a][c][0] for a in A),) * 3 for c in C}

    def dist(p, q):
        return sqrt(sum((x - y) ** 2 for x, y in zip(p, q)) / 3)

    d_pos = {a: sum(dist(V[a][c], fpis[c]) for c in C) for a in A}
    d_neg = {a: sum(dist(V[a][c], fnis[c]) for c in C) for a in A}
    cc = {a: d_neg[a] / (d_pos[a] + d_neg[a]) for a in A}
    return dict(W=W, X=X, R=R, V=V, fpis=fpis, fnis=fnis, d_pos=d_pos, d_neg=d_neg, cc=cc)


# ---------------------------------------------------------------- МАИ
def saaty(diff):
    """Разница в баллах -> шкала Саати: 0 -> 1, +1 -> 2, ... (не больше 9); минус -> обратная величина."""
    return min(diff + 1, 9) if diff >= 0 else 1 / min(-diff + 1, 9)


def pairwise(values):
    n = len(values)
    return [[saaty(values[i] - values[j]) for j in range(n)] for i in range(n)]


def geo_mean(mats):
    n = len(mats[0])
    k = len(mats)
    return [[prod(m[i][j] for m in mats) ** (1 / k) for j in range(n)] for i in range(n)]


def eigen(M):
    """Главный собственный вектор степенным методом, lambda_max, ИС и ОС."""
    n = len(M)
    w = [1 / n] * n
    for _ in range(200):
        v = [sum(M[i][j] * w[j] for j in range(n)) for i in range(n)]
        s = sum(v)
        w = [x / s for x in v]
    lam = sum(sum(M[i][j] * w[j] for j in range(n)) / w[i] for i in range(n)) / n
    ci = (lam - n) / (n - 1)
    return w, lam, ci, ci / RI[n]


def expert_matrices(e):
    """Матрицы парных сравнений одного эксперта: критерии и альтернативы по каждому критерию."""
    crit = pairwise([IMPORTANCE[c][e] for c in C])
    alts = {}
    for c in C:
        sign = 1 if KIND[c] == "benefit" else -1  # для риска предпочтительнее меньший балл
        alts[c] = pairwise([sign * SCORES[a][c][e] for a in A])
    return crit, alts


def ahp():
    per_expert = [expert_matrices(e) for e in range(len(EXPERTS))]
    worst_cr = max(max(eigen(crit)[3], *(eigen(m)[3] for m in alts.values())) for crit, alts in per_expert)
    g_crit = geo_mean([p[0] for p in per_expert])
    w, lam, ci, cr = eigen(g_crit)
    local, local_cr = {}, {}
    for c in C:
        p, _, _, cr_c = eigen(geo_mean([pe[1][c] for pe in per_expert]))
        local[c], local_cr[c] = p, cr_c
    glob = {a: sum(w[j] * local[c][i] for j, c in enumerate(C)) for i, a in enumerate(A)}
    # индивидуальные итоги — чтобы увидеть, насколько эксперты согласны между собой
    indiv = []
    for crit, alts in per_expert:
        wi = eigen(crit)[0]
        indiv.append({a: sum(wi[j] * eigen(alts[c])[0][i] for j, c in enumerate(C)) for i, a in enumerate(A)})
    return dict(g_crit=g_crit, w=w, lam=lam, ci=ci, cr=cr, local=local, local_cr=local_cr,
                glob=glob, indiv=indiv, worst_cr=worst_cr)


# ---------------------------------------------------------------- отчёт
def build():
    t, h = fuzzy_topsis(), ahp()
    rt, rh = ranks(t["cc"]), ranks(h["glob"])
    best_t = min(rt, key=rt.get)
    best_h = min(rh, key=rh.get)
    name = lambda a: f"{a} {ALTS[a][0]}"
    short = ["А", "Х", "С"]

    md = ["# Фаза 1. Выбор концепции проекта", ""]
    md += ["Состав экспертов: " + ", ".join(f"{n} ({s})" for n, s in zip(EXPERTS, short)) + ". "
           "Расчёты — `phase1.py` (чистый Python), этот файл пересобирается скриптом.", ""]

    md += ["## 1. Концепции", ""]
    md += ["К концепциям предъявлялись требования: MVP на 10–15 use cases, несколько типов пользователей, "
           "возможность дальше оценивать проект (COSMIC, UCP) и планировать его (20–25 задач).", ""]
    md += [table(["Код", "Название", "Суть", "Акторы и основные функции"],
                 [[a, f"**{v[0]}**", v[1], v[2]] for a, v in ALTS.items()]), ""]

    md += ["## 2. Критерии", ""]
    md += [table(["Код", "Критерий", "Тип"],
                 [[c, n, "чем больше, тем лучше" if k == "benefit" else "чем меньше, тем лучше"]
                  for c, n, k in CRITERIA]), ""]
    md += ["C1–C4 описывают нашу будущую работу над концепцией по предмету, C5 — сам воображаемый проект.", ""]

    md += ["## 3. Экспертные оценки", ""]
    md += ["Каждый эксперт независимо поставил баллы по шкале 1–10. Три оценки упорядочены по возрастанию и "
           "дальше рассматриваются как треугольное нечёткое число (пессимистичная; ожидаемая; оптимистичная).", ""]
    md += ["**Важность критериев**", ""]
    md += [table(["Критерий"] + short + ["Треугольное число"],
                 [[c] + IMPORTANCE[c] + [ftri(tri(IMPORTANCE[c]), 0)] for c in C]), ""]
    md += ["**Оценки альтернатив** (в ячейке — баллы А / Х / С)", ""]
    md += [table(["Альтернатива"] + C,
                 [[name(a)] + [" / ".join(map(str, SCORES[a][c])) for c in C] for a in A]), ""]
    md += ["**Те же оценки как треугольные числа**", ""]
    md += [table(["Альтернатива"] + C, [[name(a)] + [ftri(t["X"][a][c], 0) for c in C] for a in A]), ""]

    md += ["## 4. Нечёткий коллективный TOPSIS", ""]
    md += ["Шаги:", "",
           "1. Нормализация. Для критериев «больше — лучше»: $\\tilde r_{ij} = (l_{ij}/u_j^*,\\ m_{ij}/u_j^*,\\ u_{ij}/u_j^*)$, "
           "где $u_j^* = \\max_i u_{ij}$. Для риска (C5): $\\tilde r_{ij} = (l_j^-/u_{ij},\\ l_j^-/m_{ij},\\ l_j^-/l_{ij})$, "
           "где $l_j^- = \\min_i l_{ij}$.",
           "2. Веса — треугольные числа важности, делённые на 10. Взвешенная матрица: "
           "$\\tilde v_{ij} = \\tilde r_{ij} \\otimes \\tilde w_j$ (покомпонентное умножение).",
           "3. Идеальное решение $A^*$: по каждому критерию $v_j^* = \\max_i u(\\tilde v_{ij})$; "
           "антиидеальное $A^-$: $v_j^- = \\min_i l(\\tilde v_{ij})$.",
           "4. Расстояние между треугольными числами — вершинный метод: "
           "$d(\\tilde a, \\tilde b) = \\sqrt{\\tfrac13[(l_a-l_b)^2+(m_a-m_b)^2+(u_a-u_b)^2]}$; "
           "$d_i^*$ и $d_i^-$ — суммы расстояний по критериям.",
           "5. Коэффициент близости $CC_i = d_i^- / (d_i^* + d_i^-)$, лучший вариант — с наибольшим $CC$.", ""]
    md += ["**Нечёткие веса**", ""]
    md += [table(C, [[ftri(t["W"][c], 1) for c in C]]), ""]
    md += ["**Взвешенная нормализованная матрица**", ""]
    md += [table(["Альтернатива"] + C, [[name(a)] + [ftri(t["V"][a][c]) for c in C] for a in A]
                 + [["$A^*$"] + [f"{t['fpis'][c][0]:.3f}" for c in C]]
                 + [["$A^-$"] + [f"{t['fnis'][c][0]:.3f}" for c in C]]), ""]
    md += ["**Результат**", ""]
    md += [table(["Альтернатива", "$d^*$", "$d^-$", "$CC$", "Место"],
                 [[name(a), f"{t['d_pos'][a]:.3f}", f"{t['d_neg'][a]:.3f}", f"{t['cc'][a]:.3f}", rt[a]]
                  for a in sorted(A, key=rt.get)]), ""]

    md += ["## 5. Чёткий коллективный МАИ", ""]
    md += ["Иерархия: цель (выбрать концепцию) → 5 критериев → 4 альтернативы.", "",
           "Матрицы парных сравнений каждого эксперта построены из его же балльных оценок: разница в $k$ баллов "
           "переводится в оценку $k+1$ по шкале Саати (равные баллы → 1, разница 1 → 2, …, не больше 9), "
           "обратное сравнение — обратная величина. Для риска (C5) предпочтительнее вариант с меньшим баллом. "
           "Так каждый эксперт даёт 1 матрицу критериев 5×5 и 5 матриц альтернатив 4×4, и его суждения остаются "
           "согласованными с оценками, использованными в TOPSIS.", "",
           "Коллективная матрица — среднее геометрическое индивидуальных суждений по каждой ячейке (сохраняет "
           "обратную симметричность). Приоритеты — главный собственный вектор; согласованность: "
           "$ИС = (\\lambda_{max}-n)/(n-1)$, $ОС = ИС/СИ$ (СИ = 0,90 для $n=4$ и 1,12 для $n=5$), допустимо $ОС \\le 0{,}1$.", ""]
    md += ["**Коллективная матрица сравнений критериев**", ""]
    md += [table([""] + C + ["Вес"],
                 [[c] + [f"{x:.2f}" for x in h["g_crit"][i]] + [f"**{h['w'][i]:.3f}**"] for i, c in enumerate(C)]), ""]
    md += [f"$\\lambda_{{max}}$ = {h['lam']:.3f}, ИС = {h['ci']:.3f}, ОС = {h['cr']:.3f}. "
           f"Наихудшее ОС среди всех 18 индивидуальных матриц — {h['worst_cr']:.3f}.", ""]
    md += ["**Локальные приоритеты альтернатив по критериям и итог**", ""]
    md += [table(["Альтернатива"] + [f"{c} ({h['w'][j]:.3f})" for j, c in enumerate(C)] + ["Глобальный приоритет", "Место"],
                 [[name(a)] + [f"{h['local'][c][i]:.3f}" for c in C] + [f"**{h['glob'][a]:.3f}**", rh[a]]
                  for i, a in enumerate(A)]
                 + [["ОС матрицы"] + [f"{h['local_cr'][c]:.3f}" for c in C] + ["", ""]]), ""]
    md += ["**Глобальные приоритеты по отдельным экспертам** (проверка согласия в группе)", ""]
    md += [table(["Альтернатива"] + short,
                 [[name(a)] + [f"{h['indiv'][e][a]:.3f}" for e in range(3)] for a in A]), ""]

    md += ["## 6. Сравнение методов и выводы", ""]
    md += [table(["Альтернатива", "TOPSIS, $CC$", "Место", "МАИ, приоритет", "Место"],
                 [[name(a), f"{t['cc'][a]:.3f}", rt[a], f"{h['glob'][a]:.3f}", rh[a]] for a in A]), ""]
    same = rt == rh
    indiv_best = {min(ranks(x), key=ranks(x).get) for x in h["indiv"]}
    cc_sorted = sorted(t["cc"].values(), reverse=True)
    gl_sorted = sorted(h["glob"].values(), reverse=True)
    md += [f"- Оба метода ставят на первое место **{name(best_t)}**." if best_t == best_h else
           f"- Методы разошлись в лидере: TOPSIS — {name(best_t)}, МАИ — {name(best_h)}.",
           ("- Порядок всех четырёх альтернатив в двух методах совпал." if same else
            "- Порядок остальных альтернатив различается: 2-е и 3-е места (SplitBot и RoomBook) меняются местами. "
            "SplitBot — «контрастный» вариант: очень силён по компактности и риску, слаб по пригодности для оценки "
            "и планирования. МАИ через шкалу Саати усиливает его крупные преимущества, а TOPSIS штрафует "
            "за удалённость от идеала по слабым критериям, поэтому ровный RoomBook там выше."),
           f"- Отрыв лидера от второго места: в TOPSIS {cc_sorted[0] - cc_sorted[1]:.3f} по $CC$, "
           f"в МАИ {gl_sorted[0] - gl_sorted[1]:.3f} по приоритету "
           f"(в {gl_sorted[0] / gl_sorted[1]:.2f} раза). МАИ разделяет варианты резче: шкала Саати усиливает "
           "разницу в баллах, а TOPSIS работает с исходными баллами и их разбросом.",
           ("- Каждый эксперт по отдельности тоже получает того же лидера — разногласий по главному выводу нет."
            if indiv_best == {best_h} else
            "- У отдельных экспертов лидеры различаются: " + ", ".join(sorted(indiv_best)) + "."),
           f"- Самые весомые критерии в МАИ — {', '.join(c for c, _ in sorted(zip(C, h['w']), key=lambda p: -p[1])[:2])}; "
           "в TOPSIS те же критерии имеют наибольшие нечёткие веса.",
           "- TOPSIS учитывает разброс мнений через трёхточечные оценки, МАИ усредняет суждения геометрически "
           "и даёт проверку согласованности. Совпадение лидера в двух методах разной природы делает выбор устойчивым.",
           "", f"**Решение:** для фаз 2–5 берём концепцию **{name(best_t)}** — {ALTS[best_t][1][0].lower() + ALTS[best_t][1][1:]}.", ""]

    Path(__file__).with_name("README.md").write_text("\n".join(md), encoding="utf-8")
    print("TOPSIS CC:", {a: round(v, 3) for a, v in t["cc"].items()})
    print("МАИ:      ", {a: round(v, 3) for a, v in h["glob"].items()})
    print("ОС критериев:", round(h["cr"], 3), "| худшее индивидуальное ОС:", round(h["worst_cr"], 3))
    print("ОС локальных:", {c: round(v, 3) for c, v in h["local_cr"].items()})
    print("По экспертам:", [{a: round(v, 3) for a, v in x.items()} for x in h["indiv"]])


if __name__ == "__main__":
    build()
