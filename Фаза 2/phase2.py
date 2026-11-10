#!/usr/bin/env python3
"""Фаза 2 (мета). Распределение задач фазы 3 между участниками.

Задача о назначениях с балансом нагрузки: максимум суммарной предпочтительности.
Решается двумя способами:
  1) PuLP + CBC (целочисленное программирование) — если установлен: pip install pulp
  2) полный перебор 3^10 = 59 049 вариантов на чистом Python — для проверки и анализа чувствительности.
Запуск: python3 phase2.py. Скрипт пересобирает README.md и assignment.json в своей папке.
"""
import json
from itertools import product
from pathlib import Path

PEOPLE = ["Абдуллаев Д.", "Хисаметдинов М.", "Саввинов Д."]
SHORT = ["А", "Х", "С"]

# Индивидуальные задачи фазы 3: код -> (название, оценки трудоёмкости в 1-м раунде покера [А, Х, С], согласованная оценка, ч)
TASKS = {
    "T1": ("Черновик use cases (13 шт., основные сценарии)", [5, 3, 5], 5),
    "T2": ("Альтернативные и негативные сценарии, ревью use cases", [3, 3, 2], 3),
    "T3": ("Изучение метода COSMIC", [2, 3, 2], 2),
    "T4": ("Подсчёт COSMIC Function Points", [5, 8, 5], 5),
    "T5": ("Классификация акторов и use cases (UAW, UUCW)", [2, 2, 3], 2),
    "T6": ("Оценка TCF и ECF, расчёт UCP и трудозатрат", [3, 3, 5], 3),
    "T7": ("Подготовка покера планирования: список элементов, сквозные работы", [2, 3, 2], 2),
    "T8": ("Агрегация экспертных оценок в оценку проекта (скрипт)", [2, 2, 3], 2),
    "T9": ("Сравнение оценок, выводы о команде, сроках и фичах", [3, 5, 3], 3),
    "T10": ("Оформление отчёта по фазе 3, актуализация RACI", [3, 2, 3], 3),
}
# Коллективные задачи — участвуют все, в оптимизацию не входят
MEETINGS = {
    "M1": ("Сессия покера планирования по use cases проекта", 1.5),
    "M2": ("Митинг: согласование итоговых выводов фазы 3", 1.0),
}
# Предпочтительность задач, шкала 1–5 (5 — очень хочу), порядок [А, Х, С]
PREF = {
    "T1": [4, 3, 5], "T2": [2, 3, 5], "T3": [3, 5, 2], "T4": [3, 5, 2], "T5": [4, 3, 3],
    "T6": [5, 3, 2], "T7": [3, 2, 4], "T8": [5, 4, 1], "T9": [3, 4, 4], "T10": [2, 2, 4],
}
SAME_PERSON = [("T3", "T4")]  # изучивший COSMIC сам ведёт подсчёт
DELTA = 2                     # допустимое отклонение нагрузки от средней, ч

T = list(TASKS)
HOURS = {j: TASKS[j][2] for j in T}
AVG = sum(HOURS.values()) / len(PEOPLE)


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def loads(assign):
    return [sum(HOURS[j] for j in T if assign[j] == i) for i in range(len(PEOPLE))]


def pref_sum(assign):
    return sum(PREF[j][assign[j]] for j in T)


def feasible(assign, delta, coupled=True):
    if coupled and any(assign[a] != assign[b] for a, b in SAME_PERSON):
        return False
    return delta is None or all(abs(l - AVG) <= delta for l in loads(assign))


def solve_bruteforce(delta, coupled=True):
    """Полный перебор. Возвращает (лучшее назначение, сумма предпочтений, число оптимальных решений)."""
    best, best_key, sums = None, None, []
    for combo in product(range(len(PEOPLE)), repeat=len(T)):
        assign = dict(zip(T, combo))
        if not feasible(assign, delta, coupled):
            continue
        l = loads(assign)
        key = (pref_sum(assign), -(max(l) - min(l)))  # при равной сумме — меньший разброс нагрузки
        sums.append(key[0])
        if best_key is None or key > best_key:
            best, best_key = assign, key
    if best is None:
        return None, None, 0
    return best, best_key[0], sums.count(best_key[0])


def solve_pulp(delta):
    """Та же модель в PuLP. Возвращает (назначение, значение ЦФ) или None, если PuLP не установлен."""
    try:
        import pulp
    except ImportError:
        return None
    P = range(len(PEOPLE))
    model = pulp.LpProblem("assignment", pulp.LpMaximize)
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", cat="Binary") for i in P for j in T}
    model += pulp.lpSum(PREF[j][i] * x[i, j] for i in P for j in T)          # целевая функция
    for j in T:
        model += pulp.lpSum(x[i, j] for i in P) == 1                         # у задачи один исполнитель
    for i in P:
        load = pulp.lpSum(HOURS[j] * x[i, j] for j in T)
        model += load <= AVG + delta                                         # баланс нагрузки
        model += load >= AVG - delta
        for a, b in SAME_PERSON:
            model += x[i, a] == x[i, b]                                      # связанные задачи
    model.solve(pulp.PULP_CBC_CMD(msg=False))
    assign = {j: next(i for i in P if x[i, j].value() > 0.5) for j in T}
    return assign, pulp.value(model.objective)


def build():
    best, opt, n_opt = solve_bruteforce(DELTA)
    l = loads(best)
    pulp_res = solve_pulp(DELTA)
    greedy = {j: max(range(3), key=lambda i: PREF[j][i]) for j in T}  # каждому — самое желанное, без ограничений

    md = ["# Фаза 2 (мета). Распределение работы фазы 3", ""]
    md += ["Фазы 2 и 3 связаны: сначала работа фазы 3 разбита на задачи и распределена (эта фаза), "
           "затем фаза 3 выполнена по полученному распределению. Расчёты — `phase2.py`.", ""]

    md += ["## 1. Декомпозиция фазы 3", ""]
    md += ["Индивидуальные задачи (T) распределяются оптимизацией. Коллективные (M) выполняют все трое, "
           "поэтому в модель они не входят и нагрузку не перекашивают.", ""]
    md += [table(["Код", "Задача", "Тип"],
                 [[j, TASKS[j][0], "индивидуальная"] for j in T]
                 + [[m, v[0], f"коллективная, {v[1]} ч × 3"] for m, v in MEETINGS.items()]), ""]

    md += ["## 2. Оценка трудоёмкости", ""]
    md += ["Метод — покер планирования, единица — часы чистого времени, карты 1, 2, 3, 5, 8, 13. "
           "В первом раунде оценки вскрываются одновременно; при расхождении крайние оценки объясняются, "
           "затем второй раунд до единой оценки.", ""]
    md += [table(["Код", "Задача"] + SHORT + ["Итог, ч"],
                 [[j, TASKS[j][0]] + TASKS[j][1] + [f"**{HOURS[j]}**"] for j in T]
                 + [["", "**Всего**", "", "", "", f"**{sum(HOURS.values())}**"]]), ""]
    md += [f"Средняя нагрузка на человека: {sum(HOURS.values())} / 3 = {AVG:.0f} ч.", ""]

    md += ["## 3. Предпочтительность задач", ""]
    md += ["Каждый независимо оценил, насколько хочет взять задачу: 1 — совсем не хочу, 5 — очень хочу.", ""]
    md += [table(["Код", "Задача"] + SHORT, [[j, TASKS[j][0]] + PREF[j] for j in T]), ""]

    md += ["## 4. Постановка задачи", ""]
    md += ["Обозначения: $i$ — участник, $j$ — задача, $p_{ij}$ — предпочтительность, $t_j$ — трудоёмкость, "
           f"$\\bar T = {AVG:.0f}$ ч — средняя нагрузка, $\\delta = {DELTA}$ ч — допустимое отклонение. "
           "Переменные $x_{ij} \\in \\{0,1\\}$: 1, если задача $j$ назначена участнику $i$.", "",
           "$$\\max \\sum_i \\sum_j p_{ij} x_{ij}$$", "",
           "при ограничениях", "",
           "$$\\sum_i x_{ij} = 1 \\quad \\forall j \\qquad \\text{(у каждой задачи ровно один исполнитель)}$$", "",
           "$$\\bar T - \\delta \\le \\sum_j t_j x_{ij} \\le \\bar T + \\delta \\quad \\forall i \\qquad \\text{(баланс нагрузки)}$$", "",
           "$$x_{i,T3} = x_{i,T4} \\quad \\forall i \\qquad \\text{(изучивший COSMIC сам считает CFP)}$$", "",
           "Обоснование:", "",
           "- **Целевая функция** — суммарная предпочтительность: люди быстрее и качественнее делают то, что хотят делать.",
           "- **Один исполнитель** — у задачи должен быть ровно один ответственный (R в матрице RACI).",
           "- **Баланс нагрузки** — без него оптимум по предпочтениям перегружает одного человека; "
           "трудоёмкость из покера входит в модель именно здесь. $\\delta = 2$ ч — около 20 % средней нагрузки: "
           "при $\\delta = 0$ точное равенство слишком жёстко для задач разной длины.",
           "- **Связка T3–T4** — передавать подсчёт другому значило бы изучать метод дважды.", "",
           "Рассмотренные альтернативные постановки: (а) минимизировать максимальную нагрузку при ограничении снизу на "
           "предпочтения; (б) свёртка «предпочтения минус штраф за разброс нагрузки» — отвергнута, потому что вес штрафа "
           "пришлось бы назначать произвольно; (в) минимизировать суммарную «нежелательность» — эквивалентна выбранной.", ""]

    md += ["## 5. Решение", ""]
    solver_note = ("Модель решена в PuLP (CBC), значение целевой функции "
                   f"{pulp_res[1]:.0f}; полный перебор дал то же значение {opt}."
                   if pulp_res else
                   "В `phase2.py` модель записана для PuLP (CBC) и решается полным перебором всех "
                   f"3^10 = {3 ** len(T)} назначений. Приведённый результат получен перебором: он гарантирует "
                   "глобальный оптимум и позволяет посчитать число оптимальных решений.")
    md += [solver_note, ""]
    md += [table(["Код", "Задача", "Исполнитель", "Часы", "Предпочтение"],
                 [[j, TASKS[j][0], PEOPLE[best[j]], HOURS[j], PREF[j][best[j]]] for j in T]), ""]
    md += [table(["Участник", "Задачи", "Нагрузка, ч", "Сумма предпочтений"],
                 [[PEOPLE[i], ", ".join(j for j in T if best[j] == i), l[i],
                   sum(PREF[j][i] for j in T if best[j] == i)] for i in range(3)]
                 + [["**Итого**", "", f"**{sum(l)}**", f"**{opt}**"]]), ""]
    max_possible = sum(max(PREF[j]) for j in T)
    md += [f"- Значение целевой функции: **{opt}** из {max_possible} возможных "
           f"(если бы каждый получил самое желанное без ограничений); средняя предпочтительность назначенной задачи — {opt / len(T):.1f} из 5.",
           f"- Оптимальных решений с таким значением: {n_opt}"
           + ("; из них выбрано решение с наименьшим разбросом нагрузки." if n_opt > 1 else "."),
           f"- Нагрузка: {' / '.join(map(str, l))} ч, все в пределах {AVG - DELTA:.0f}–{AVG + DELTA:.0f} ч.",
           f"- Распределение «каждому самое желанное» без ограничений дало бы нагрузку "
           f"{' / '.join(map(str, loads(greedy)))} ч — баланс нарушен, ограничение работает не зря.", ""]

    md += ["## 6. Чувствительность к допуску по нагрузке", ""]
    rows = []
    for d in [0, 1, 2, 3, 4, None]:
        b, o, n = solve_bruteforce(d)
        rows.append(["без ограничения" if d is None else d,
                     o if b else "нет решений", " / ".join(map(str, loads(b))) if b else "—", n if b else "—"])
    md += [table(["$\\delta$, ч", "Сумма предпочтений", "Нагрузка А / Х / С, ч", "Число оптимальных решений"], rows), ""]
    b_free, o_free, _ = solve_bruteforce(DELTA, coupled=False)
    md += [f"Без связки T3–T4 при $\\delta = {DELTA}$ сумма предпочтений равна {o_free} "
           + ("— связка ничего не стоит." if o_free == opt else f"(связка стоит {o_free - opt} балл(а))."), ""]

    md += ["## 7. Вывод", ""]
    md += ["Распределение принято как план фазы 3 и перенесено в матрицу RACI: исполнитель задачи — R, "
           "ответственный за фазу — A, остальные участники — C или I. Коллективные задачи M1 и M2 — R у всех.", ""]

    here = Path(__file__).parent
    (here / "README.md").write_text("\n".join(md), encoding="utf-8")
    (here / "assignment.json").write_text(json.dumps(
        {"people": PEOPLE, "tasks": {j: {"name": TASKS[j][0], "hours": HOURS[j], "person": PEOPLE[best[j]]} for j in T},
         "meetings": {m: {"name": v[0], "hours_each": v[1]} for m, v in MEETINGS.items()},
         "objective": opt, "loads": dict(zip(PEOPLE, l))}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Назначение:", {j: SHORT[best[j]] for j in T})
    print("Сумма предпочтений:", opt, "| нагрузка:", l, "| оптимальных решений:", n_opt)
    print("PuLP:", pulp_res if pulp_res else "не установлен, использован перебор")
    for r in rows:
        print("  delta", r)
    print("без связки:", o_free)


if __name__ == "__main__":
    build()
