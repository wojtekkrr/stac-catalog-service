# STAC Catalog Service

Mikroserwis przyjmujący metadane produktów satelitarnych w formacie JSON lub XML, przekształcający je do STAC Item i zapisujący w PostgreSQL/PostGIS z rozszerzeniem pgSTAC.

## Wymagania

- Docker
- Docker Compose

> [!WARNING]

> Dane logowania zapisane w `docker-compose.yml` są przeznaczone wyłącznie dla lokalnego środowiska demonstracyjnego. Nie należy używać ich w środowisku produkcyjnym.

## Uruchomienie

Z katalogu głównego projektu uruchom:

```bash
docker compose up --build
```

Po uruchomieniu dostępne będą:

- API: [http://localhost:8000](http://localhost:8000)
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- kontrola działania: [http://localhost:8000/health](http://localhost:8000/health)

Sprawdzenie stanu kontenerów:

```bash
docker compose ps
```

Zatrzymanie środowiska:

```bash
docker compose down
```

Usunięcie środowiska razem z danymi bazy:

```bash
docker compose down -v
```



## Wczytywanie metadanych

Metadane należy umieścić w katalogu `/samples`.

Polecenia należy wykonywać z katalogu głównego projektu.

W Windows PowerShell należy użyć `curl.exe` zamiast `curl`.

### SkyIsNoLimit — JSON

```bash
curl -X POST "http://localhost:8000/ingest/skyisnolimit" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/SkyIsNoLimit.json"
```



### SpaceIsNoLimit — XML

```bash
curl -X POST "http://localhost:8000/ingest/spaceisnolimit" \
  -H "Content-Type: application/xml" \
  --data-binary "@samples/SpaceIsNoLimit.xml"
```

Ponowne przesłanie produktu o tym samym identyfikatorze aktualizuje istniejący STAC Item.

> [!NOTE]

> Przykładowy plik XML zawiera niespójność pomiędzy `GlobalBBOX` a geometrią `FootprintWKT`. Zgodnie ze specyfikacją STAC `bbox` musi w całości obejmować geometrię `Polygon`.



## Wyszukiwanie produktów



### Wszystkie produkty

```bash
curl "http://localhost:8000/search"
```



### Filtrowanie po obszarze geograficznym

Format `bbox`:

```text
west,south,east,north
```

Przykład:

```bash
curl "http://localhost:8000/search?bbox=20.8,52.1,21.3,52.5"
```



### Filtrowanie po czasie

Pojedyncza data:

```bash
curl --get "http://localhost:8000/search" \
  --data-urlencode "datetime=2026-08-24T09:15:22.451Z"
```

Przedział czasu:

```bash
curl --get "http://localhost:8000/search" \
  --data-urlencode "datetime=2026-08-24T00:00:00Z/2026-08-25T00:00:00Z"
```

Obsługiwane są również otwarte przedziały:

```bash
curl --get "http://localhost:8000/search" \
  --data-urlencode "datetime=2026-08-24T00:00:00Z/.."
```



### Maksymalne zachmurzenie

Produkty z zachmurzeniem nie większym niż 5%:

```bash
curl "http://localhost:8000/search?max_cloud_cover=5"
```



### Poziom przetworzenia

```bash
curl "http://localhost:8000/search?product_level=L1C"
```



### Łączenie filtrów

```bash
curl --get "http://localhost:8000/search" \
  --data-urlencode "bbox=19.9,51.3,21.7,52.5" \
  --data-urlencode "datetime=2026-08-24T00:00:00Z/2026-08-25T00:00:00Z" \
  --data-urlencode "max_cloud_cover=10" \
  --data-urlencode "product_level=L2A"
```

Odpowiedź endpointu `/search` ma format STAC `FeatureCollection`.

## Uruchomienie testów end-to-end

Metadane należy umieścić w katalogu `/samples`.

Po aktywowaniu wirtualnego środowiska należy wykonać komendy:

```bash
python3 -m pip install -e ".[dev]"

docker compose -p crt-e2e up -d --build --wait
python3 -m pytest tests/e2e -q
docker compose -p crt-e2e down -v
```

