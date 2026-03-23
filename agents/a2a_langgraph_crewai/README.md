# A2A: LangGraph ↔ CrewAI (JSON-RPC) — agent template

Ten katalog jest **szablonem agenta** w stylu pozostałych szablonów w `agents/` (Dockerfile, `k8s/`, `deploy.sh`) i można go **wdrożyć na OpenShift** jako **dwa Deploymenty**: Crew (specjalista A2A) i LangGraph (orkiestrator A2A wołający Crew po HTTP/A2A w klastrze).

## Architektura (OpenShift)

| Zasób | Rola |
|--------|------|
| `Deployment` **a2a-crew-agent** | CrewAI + `A2AStarletteApplication`, port **8080** |
| `Deployment` **a2a-langgraph-agent** | LangGraph + narzędzie `ask_crew_specialist` → `CREW_A2A_URL` |
| `Service` + `Route` ×2 | HTTPS na krawędzi; hosty trafiają do **Agent Card** (`CREW_A2A_PUBLIC_URL`, `LANGGRAPH_A2A_PUBLIC_URL`) |
| Wewnątrz klastra | `CREW_A2A_URL=http://a2a-crew-agent:8080` (DNS usługi) |

Obrazy budowane są z **jednego** `Dockerfile` z argumentem `A2A_ROLE=crew` lub `langgraph`.

## Wymagania lokalne (dev)

- Python **3.12+**, **uv**
- Dostęp do LLM w konwencji OpenAI (`BASE_URL` z `/v1`, `MODEL_ID`, `API_KEY`)

## Uruchomienie lokalne (bez klastra)

```bash
cd agents/a2a_langgraph_crewai
cp template.env .env
# Uzupełnij .env
uv sync

# Terminal 1
uv run python crew_a2a_server.py

# Terminal 2
uv run python langgraph_a2a_server.py

# Terminal 3
uv run python demo_client.py "Twoje pytanie"
```

Lokalnie domyślne porty to **9100** (Crew) i **9200** (LangGraph); **nie** ustawiaj `PORT`, chyba że testujesz jak w kontenerze (`8080`).

## Wdrożenie na OpenShift

### Przygotowanie

1. `oc login …`, wybierz projekt: `oc project <namespace>`
2. Skopiuj `template.env` → `.env` i uzupełnij:
   - `API_KEY`, `BASE_URL`, `MODEL_ID` — ten sam LLM dla obu podów
   - `CONTAINER_IMAGE_CREW`, `CONTAINER_IMAGE_LANGGRAPH` — pełne ścieżki obrazów w rejestrze (np. Quay), tagi **różne** (np. `:crew` i `:langgraph`)
3. Zaloguj się do rejestra i skonfiguruj `docker`/`podman` pod `docker buildx … --push`
4. Zainstaluj **gettext** (polecenie `envsubst`), jeśli go nie ma: `brew install gettext` (macOS)

### Skrypt

```bash
./deploy.sh
```

Skrypt:

1. Buduje i wypycha **dwa** obrazy (`--build-arg A2A_ROLE=…`)
2. Tworzy `Secret` `a2a-langgraph-crewai-secrets` z `API_KEY`
3. Stosuje `Service` i `Route` dla obu agentów
4. Odczytuje **publiczne hosty** z `oc get route …` i ustawia `CREW_A2A_PUBLIC_URL` / `LANGGRAPH_A2A_PUBLIC_URL` na `https://…`
5. Stosuje `Deployment` z tymi URLami (Agent Card dla klientów zewnętrznych)
6. Orkiestrator w podzie używa **wewnętrznego** `CREW_A2A_URL=http://a2a-crew-agent:8080`

### Test z laptopa (demo client)

Po wdrożeniu:

```bash
export LANGGRAPH_A2A_PUBLIC_URL="https://$(oc get route a2a-langgraph-agent -o jsonpath='{.spec.host}')"
uv run python demo_client.py "Pytanie testowe"
```

### Uwagi operacyjne

- **TLS**: Route z `edge` termination (jak inne agenty w repo).
- **Sekrety**: nie commituj `.env`; `API_KEY` tylko w Secret.
- **Zasoby**: limity w YAML możesz dostosować pod vLLM / Llama Stack.
- **Skalowanie**: MVP zakłada **1 replikę** na Deployment (stan w pamięci A2A); skalowanie w poziomie wymaga później współdzielonego task store itd.
- **BASE_URL** musi być osiągalny **z podów** (np. publiczny endpoint Llama Stack lub usługa w klastrze).

## Pliki

| Plik / katalog | Opis |
|----------------|------|
| `crew_a2a_server.py` | Serwer A2A CrewAI |
| `langgraph_a2a_server.py` | Serwer A2A LangGraph (klient A2A → Crew) |
| `a2a_reply.py` | Helper klienta A2A |
| `demo_client.py` | Przykład JSON-RPC do orchestratora |
| `Dockerfile` + `entrypoint.sh` | Obraz z `A2A_ROLE` |
| `k8s/*.yaml` | Deployment / Service / Route |
| `deploy.sh` | Build + apply |

## References

- [A2A Python SDK](https://pypi.org/project/a2a-sdk/)
- Inne agenty w repo: `agents/crewai/websearch_agent/`, `agents/langgraph/react_agent/` (wzorce OpenShift)
