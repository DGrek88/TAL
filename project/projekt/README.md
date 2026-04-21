# k najkrotszych drog rozlacznych w grafie wazonym

Projekt w Pythonie 3 rozwiazuje problem wyznaczenia `k` najkrotszych drog rozlacznych miedzy wierzcholkami `s` i `t` w grafie nieskierowanym, wazonym i o dodatnich wagach.

Domyslnie rozlacznosc rozumiana jest jako rozlacznosc wierzcholkowa poza `s` i `t`, ale mozna przelaczyc program na rozlacznosc krawedziowa parametrem `--disjointness edge`.

## 1. Na czym polega problem

Dane sa:

- graf nieskierowany wazony `G = (V, E)`,
- liczba szukanych sciezek `k`, gdzie `k > 2`,
- wierzcholek zrodlowy `s`,
- wierzcholek docelowy `t`.

Celem jest znalezienie `k` sciezek `s-t`, ktore sa:

- rozlaczne wierzcholkowo poza `s` i `t` albo
- rozlaczne krawedziowo, jesli wybierzemy taki tryb,

oraz minimalizuja laczny koszt wszystkich znalezionych sciezek.

## 2. Zawartosc projektu

Projekt sklada sie z nastepujacych plikow:

- `main.py` - interfejs CLI
- `graph_generator.py` - generator losowych instancji
- `exact_solver.py` - rozwiazanie dokladne
- `greedy_solver.py` - heurystyka zachlanna
- `ant_solver.py` - heurystyka mrowkowa
- `benchmark.py` - pomiary czasu, pamieci i eksperymenty
- `io_utils.py` - reprezentacja grafu, I/O, formatowanie wynikow
- `sample_graph.txt` - przykladowa instancja tekstowa
- `requirements.txt` - opcjonalne zaleznosci

## 3. Jak dziala rozwiazanie dokladne

Solver dokladny modeluje problem jako **optymalizacje przeplywu o minimalnym koszcie** w grafie rozszczepionym:

1. kazdy wierzcholek `v` zostaje rozbity na `v_in` i `v_out`,
2. dla kazdego wierzcholka dodawana jest krawedz `v_in -> v_out`,
3. dla wierzcholkow wewnetrznych pojemnosc tej krawedzi wynosi `1` w trybie rozlacznosci wierzcholkowej,
4. kazda krawedz nieskierowana `{u, v}` jest reprezentowana przez dwa skierowane luki transportowe:
   `u_out -> v_in` oraz `v_out -> u_in`,
5. wysylamy `k` jednostek przeplywu od `s` do `t`,
6. minimalizujemy laczny koszt wykorzystanych luk transportowych.

W praktyce w projekcie zaimplementowano dwa backendy:

- `mcmf` - dokladny algorytm minimalnego kosztu przeplywu napisany w czystym Pythonie,
- `ilp` - opcjonalny backend ILP przez `PuLP`, jesli biblioteka jest zainstalowana.

Domyslne ustawienie `--exact-backend auto` wybiera `ilp`, jesli `PuLP` jest dostepne, a w przeciwnym razie korzysta z `mcmf`.

## 4. Jak dzialaja heurystyki

### 4.1. Heurystyka zachlanna

Algorytm:

1. znajduje najkrotsza sciezke `s-t` algorytmem Dijkstry,
2. zapisuje sciezke,
3. usuwa z dalszego uzycia jej wierzcholki wewnetrzne,
4. dodatkowo blokuje uzyte krawedzie, aby nie powielac tej samej sciezki,
5. powtarza proces, az znajdzie `k` sciezek albo dalsze rozwiazanie stanie sie niemozliwe.

Zaleta:

- bardzo prosty i szybki.

Wada:

- decyzje podjete na poczatku moga zablokowac lepszy uklad kolejnych sciezek.

### 4.2. Heurystyka mrowkowa

Algorytm mrowkowy:

1. utrzymuje feromony na krawedziach,
2. kazda mrowka konstruuje kolejno zestaw sciezek `s-t`,
3. wybor kolejnej krawedzi zalezy od:
   - poziomu feromonow,
   - lokalnej heurystyki zwiazanej z waga krawedzi i szacowana odlegloscia do celu,
4. po iteracji feromony odparowuja,
5. najlepsze znalezione rozwiazania wzmacniaja uzyte krawedzie.

Heurystyka mrowkowa jest wolniejsza od zachlannej, ale moze unikac niektorych zlych lokalnych wyborow.

## 5. Generator danych

Generator:

- tworzy spojny graf nieskierowany wazony,
- losuje dodatnie wagi z zadanego zakresu,
- buduje szkielet zapewniajacy sensowna szanse znalezienia `k` drog rozlacznych,
- obsluguje ziarno losowosci `seed`,
- obsluguje klasy instancji:
  - `small`
  - `medium`
  - `large`

Generator najpierw tworzy:

- bezposrednia sciezke `s-t`,
- dodatkowe `k-1` sciezek przez rozne wierzcholki posrednie,
- potem dolacza pozostale wierzcholki tak, aby graf byl spojny,
- na koniec dopelnia graf losowymi dodatkowymi krawedziami do zadanego `m`.

## 6. Pomiar czasu, pamieci i jakosci

### Czas

Pomiar wykonywany jest przez `time.perf_counter()`.

### Pamiec

Pamiec mierzona jest przez `tracemalloc`, a raportowana wartosc to:

- `peak memory usage` w KiB.

Uwaga: `tracemalloc` mierzy alokacje Pythona, a nie calkowite zuzycie pamieci procesu na poziomie systemu operacyjnego.

### Jakosc heurystyki

Dla heurystyk raportowane sa:

- `cost_exact`
- `cost_heur`
- `difference_abs`
- `ratio = cost_heur / cost_exact`
- informacja, czy heurystyka znalazla pelne `k` sciezek

## 7. Wymagania i instalacja

Wystarczy Python 3.11+.

Opcjonalnie mozna zainstalowac `PuLP`, aby uzyc backendu ILP:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Projekt dziala rowniez bez `PuLP`, korzystajac z backendu `mcmf`.

## 8. Format pliku wejsciowego

Format:

```text
n m k s t
u1 v1 w1
u2 v2 w2
...
um vm wm
```

Przyklad z pliku `sample_graph.txt`:

```text
10 16 3 0 9
0 1 17
3 0 10
0 4 11
6 0 20
0 7 17
0 9 20
1 5 3
1 9 16
2 7 5
2 9 10
4 3 10
3 8 3
5 4 16
5 7 4
8 6 9
7 9 11
```

## 9. Uruchamianie programu

### 9.1. Generowanie instancji

```bash
python3 main.py --generate --n 20 --m 40 --k 3 --source 0 --target 19
```

Zapis do pliku:

```bash
python3 main.py --generate --n 20 --m 40 --k 3 --source 0 --target 19 --output graph.txt
```

### 9.2. Wczytanie grafu z pliku i solver dokladny

```bash
python3 main.py --input sample_graph.txt --run exact
```

### 9.3. Heurystyka zachlanna

```bash
python3 main.py --input sample_graph.txt --run greedy
```

### 9.4. Heurystyka mrowkowa

```bash
python3 main.py --input sample_graph.txt --run ant --ant-seed 77
```

### 9.5. Porownanie wszystkich algorytmow

```bash
python3 main.py --generate --n 12 --m 22 --k 3 --source 0 --target 11 --seed 7 --run compare --ant-seed 77
```

### 9.6. Benchmark dla wielu rozmiarow

```bash
python3 main.py --benchmark
```

Lub krotsza seria:

```bash
python3 main.py --benchmark --benchmark-classes small medium --benchmark-repetitions 1
```

## 10. Przykladowe uruchomienia i przykladowy output

### 10.1. Solver dokladny dla pliku

Polecenie:

```bash
python3 main.py --input sample_graph.txt --run exact
```

Przykladowy output:

```text
Instancja: n=10, m=16, k=3, s=0, t=9, rozlacznosc=vertex

Solver: exact
Status: Znaleziono optymalny zestaw k rozlacznych sciezek.
Pelne k sciezek: TAK
Sciezki:
  1. 0 -> 1 -> 9 | koszt = 33
  2. 0 -> 7 -> 9 | koszt = 28
  3. 0 -> 9 | koszt = 20
Laczny koszt: 81
Czas: 0.000919 s
Pamiec peak (tracemalloc): 27.88 KiB
backend: mcmf
```

### 10.2. Porownanie solvera dokladnego i heurystyk

Polecenie:

```bash
python3 main.py --generate --n 12 --m 22 --k 3 --source 0 --target 11 --seed 7 --run compare --ant-seed 77
```

Przykladowy output:

```text
Instancja: n=12, m=22, k=3, s=0, t=11, rozlacznosc=vertex

Solver: exact
Status: Znaleziono optymalny zestaw k rozlacznych sciezek.
Pelne k sciezek: TAK
Sciezki:
  1. 0 -> 4 -> 11 | koszt = 17
  2. 0 -> 9 -> 11 | koszt = 9
  3. 0 -> 11 | koszt = 17
Laczny koszt: 43
Czas: 0.004575 s
Pamiec peak (tracemalloc): 34.81 KiB
backend: mcmf

Solver: greedy
Status: Heurystyka zachlanna znalazla pelny zestaw k sciezek.
Pelne k sciezek: TAK
Sciezki:
  1. 0 -> 9 -> 11 | koszt = 9
  2. 0 -> 11 | koszt = 17
  3. 0 -> 4 -> 11 | koszt = 17
Laczny koszt: 43
Czas: 0.000746 s
Pamiec peak (tracemalloc): 2.86 KiB

Porownanie heurystyki: greedy
  koszt_exact: 43
  koszt_heur: 43
  roznica_bezwzgledna: 0
  ratio: 1
  heurystyka_pelna: TAK
  uwaga: Heurystyka znalazla pelne rozwiazanie i mozna porownac koszty.

Solver: ant_colony
Status: Algorytm mrowkowy znalazl pelny zestaw k sciezek.
Pelne k sciezek: TAK
Sciezki:
  1. 0 -> 9 -> 11 | koszt = 9
  2. 0 -> 4 -> 11 | koszt = 17
  3. 0 -> 11 | koszt = 17
Laczny koszt: 43
Czas: 0.488265 s
Pamiec peak (tracemalloc): 33.76 KiB
ants: 24
iterations: 45
```

### 10.3. Benchmark

Polecenie:

```bash
python3 main.py --benchmark --benchmark-classes small --benchmark-repetitions 1 --benchmark-seed 50 --ant-seed 77
```

Przykladowy output:

```text
klasa    rep   n   m   k   exact_cost   greedy_cost   greedy_ratio   exact_t[s]   greedy_t[s]   ant_cost   ant_ratio   ant_t[s]
small      1  12  22   3          49           49             1    0.003759     0.000349         49          1   0.480995

Podsumowanie srednie dla klas:
small: exact_t=0.003759s, greedy_t=0.000349s, greedy_ratio=1, greedy_success=1/1, ant_t=0.480995s, ant_ratio=1, ant_success=1/1
```

## 11. Interpretacja porownania jakosci

Najwazniejsze pola:

- `cost_exact` - najlepszy mozliwy koszt laczny
- `cost_heur` - koszt rozwiazania heurystyki
- `difference_abs` - jak bardzo heurystyka odsunela sie od optimum
- `ratio` - iloraz `cost_heur / cost_exact`

Interpretacja:

- `ratio = 1` oznacza, ze heurystyka trafila w optimum,
- `ratio > 1` oznacza, ze heurystyka dala rozwiazanie gorsze od dokladnego,
- brak `ratio` oznacza, ze nie ma pelnych danych do porownania, np. heurystyka nie znalazla kompletu `k` sciezek.

## 12. Ograniczenia rozwiazania

- backend `mcmf` jest dokladny, ale dla bardzo duzych grafow nadal moze byc kosztowny obliczeniowo,
- heurystyka zachlanna jest szybka, ale moze zablokowac przyszle lepsze sciezki,
- heurystyka mrowkowa jest bardziej elastyczna, ale wolniejsza i zalezna od parametrow,
- pomiar pamieci przez `tracemalloc` dotyczy alokacji Pythona, a nie calego procesu,
- generator tworzy sensowne instancje testowe, ale nie modeluje wszystkich mozliwych klas grafow.

## 13. Podsumowanie

Projekt jest kompletny i zawiera:

- algorytm dokladny,
- dwie heurystyki,
- generator instancji,
- pomiary czasu i pamieci,
- porownanie jakosci rozwiazan,
- interfejs tekstowy w terminalu,
- przyklady uruchomien i wynikow.
