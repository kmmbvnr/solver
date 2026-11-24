# ROADEF/EURO 2026 · Keep the Flow

Поиск подбирает общий набор маршрутов, затем уточняет его по периодам с учётом бюджета изменений.

После установки `.[roadef]` выполните из этого каталога. Для setX-01 используйте `solve.py`, для setX-02 и setX-03 — `run_static.py`, который хранит одинаковые строки таблицы маршрутов один раз.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
work=$(mktemp -d)
case_id=setX-01
python solve.py data "$case_id" --seconds 120 --output "$work/static.json"
python refine.py data "$case_id" "$work/static.json" "$work/plan.json"
checker124 --net "data/$case_id-net.json" --tm "data/$case_id-tm.json" \
  --scenario "data/$case_id-scenario.json" --srpaths "$work/plan.json" \
  --max-decimal-places 6 > "$work/check.json"
python rank.py "$case_id" "$work/check.json" qualification_results/readme.md \
  qualification_results/log qualification_results/loads_vector.csv
```

Входы из снимка `8362c373` уже в `data/`. Валидатор v1.2.4 и файлы для `rank.py` доступны у организаторов. [Материалы и валидатор](https://roadef.org/challenge/2026/en/material.php) · [Протокол квалификации](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41/qualification_results).

В исходных замерах валидатор принял все три плана. Место рассчитано вставкой в таблицу квалификации для каждого входа. Нагрузки сравниваются лексикографически по убыванию.

| Вход | Место | Лидер | Первая отличающаяся загрузка, наша / лидера |
|---|---:|---|---:|
| setX-01 | 36 | J156 | №1 · 38,8174% / 38,8170% |
| setX-02 | 46 | J156 | №8 · 33,4454% / 33,1240% |
| setX-03 | 46 | S33 | №2 · 40,6091% / 34,6417% |
