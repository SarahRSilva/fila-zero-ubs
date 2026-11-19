# Fila Zero UBS

CitizenTech que prevê quantas pessoas vão chegar a uma Unidade Básica de Saúde amanhã e faz pré-triagem por chat, para que ninguém precise chegar às 5h da manhã para pegar senha.

Global Solution FIAP 2026/2. Entrega em 19/11/2026.

> Os dados deste repositório são **sintéticos**. Nenhum dado real de paciente ou de UBS é usado. O MVP não substitui a classificação de risco do enfermeiro, não integra com o e-SUS e não marca consulta: ele sugere um turno.

## Subir tudo

Requisito: Docker Desktop.

```bash
cp .env.example .env        # preencha JWT_SECRET, PSEUDONIMO_SAL e SEED_SENHA
docker compose up --build
```

| Serviço | Endereço |
| --- | --- |
| Front (React) | http://localhost:5173 |
| API (FastAPI) | http://localhost:8000/docs |
| Dashboard (Streamlit) | http://localhost:8501 |
| PostgreSQL | localhost:5432 |
| MQTT (Mosquitto) | localhost:1883 |

Com `docker compose --profile demo up --build` sobe também o `sensor`, um mock que publica leituras da sala de espera no Mosquitto; sem placa, é o que alimenta o cartão "Sala de espera agora" do painel. O `coletor` grava essas leituras no lake.

Sem `.env`, o compose usa valores de desenvolvimento (senha de demonstração `filazero-demo`). Não use esses valores em ambiente público.

O MVP roda localmente com o Docker Compose; não há versão publicada na internet. O job `deploy` do CI fica desligado até alguém configurar o Render: sem o secret `RENDER_DEPLOY_HOOK_URL`, ele só registra um aviso. Para publicar a API e o front no Render, com deploy automático pelo GitHub Actions, siga [docs/deploy.md](docs/deploy.md).

### Testar no celular

Com tudo no ar no computador e o celular na mesma rede Wi-Fi:

1. Descubra o IP do computador: `ipconfig getifaddr en0` no macOS, `ipconfig` no Windows (IPv4).
2. No celular, abra `http://SEU-IP:5173` (por exemplo `http://192.168.0.15:5173`).

O front procura a API em `http://SEU-IP:8000` sozinho, e a API aceita chamadas vindas de endereços de rede privada. O dashboard fica em `http://SEU-IP:8501`. Se não abrir, confira se o firewall do computador libera as portas 5173, 8000 e 8501.

Usuários de demonstração, criados na primeira subida com a senha de `SEED_SENHA`:

| E-mail | Perfil |
| --- | --- |
| `cidadao@filazero.dev` | cidadão |
| `gestora@filazero.dev` | gestora da UBS Jardim Esperanca |

## Rodar por área

Fora do Docker, com Python 3.13 (as versões são as mesmas do CI e das imagens):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

| Área | Pasta | Como rodar | Situação |
| --- | --- | --- | --- |
| Dataset sintético | `data/` | `python data/gerar_dataset.py` | pronto |
| Big Data: pipeline | `bigdata/` | `python bigdata/pipeline.py` | bronze → silver → gold pronto, com o sensor |
| IA: previsão | `ia/` | `python ia/treinar.py` e notebook `ia/previsao_demanda.ipynb` | modelo treinado e medido |
| IA: pré-triagem | `ia/triagem.py`, `ia/triagem_llm.py`, `ia/prompts/` | `POST /triagem` e `python ia/avaliar_triagem.py` | regras como piso de segurança; LLM com `ANTHROPIC_API_KEY` |
| IA: ganho simulado | `ia/simular_ganho.py` | `python ia/simular_ganho.py` | 100 cidadãos em dia de pico, antes × depois |
| Big Data: dashboard | `bigdata/dashboard/` | `streamlit run bigdata/dashboard/app.py` | 6 indicadores com filtro, incluindo lotação da sala |
| MVP: API | `mvp/api/` | `docker compose up api` | login, atendimento e previsão |
| MVP: front | `mvp/web/` | `docker compose up web` | 4 telas: login, pré-triagem, turno sugerido, painel da gestora |
| IoT | `iot/` | `python iot/mock_sensor.py` e `python iot/coletor.py` | sketch ESP32 para Wokwi, mock, coletor e `fato_lotacao` (`iot/README.md`) |
| Testes | `tests/` | `pytest -q` | T01 a T08 do plano (T08 pela API, sem navegador), mais dataset, dashboard, cadastro e limites de acesso |

Ordem para refazer tudo do zero: dataset, pipeline, treino, testes.

```bash
python data/gerar_dataset.py && python bigdata/pipeline.py && python ia/treinar.py && pytest -q
```

## API

Documentação interativa em `/docs`. Para testar ali, chame `POST /login`, copie o `access_token` e cole em **Authorize**.

| Rota | Acesso | O que faz |
| --- | --- | --- |
| `GET /health` | aberto | Situação do serviço |
| `GET /ubs` | aberto | Lista de unidades |
| `POST /cadastro` | aberto | Cria conta de cidadão e devolve o token |
| `POST /login` | aberto | Devolve o token JWT, o perfil e a UBS; depois de 3 falhas seguidas na mesma conta, cada tentativa espera 1 s, 2 s, 4 s… até 60 s (429 com `Retry-After`) |
| `POST /atendimento` | token | Registra um atendimento; recusa dia fechado e, para o cidadão, data passada. Confirmar de novo no mesmo dia troca o turno |
| `GET /atendimento` | token | Gestora vê só os da própria unidade; cidadão vê só os dele |
| `GET /previsao?data=AAAA-MM-DD` | token | Procura prevista nos três turnos; aceita `ubs`, `temp_max` e `chuva_mm` |
| `POST /triagem` | token | Classifica o relato em verde, amarelo ou vermelho, com pergunta de esclarecimento quando precisa |
| `GET /sala/agora` | token | Última leitura do sensor de lotação da sala de espera (vinda do MQTT) |
| `POST /sala` | gestora | Recebe uma leitura da própria unidade por HTTP, no mesmo formato do MQTT, para ambientes sem broker |

Segurança: senha com bcrypt, JWT com validade, segredos só em variável de ambiente (fora do Docker, a API não sobe sem `JWT_SECRET`; o compose tem um valor só para desenvolvimento), CORS restrito e nenhum dado pessoal no lake (o cidadão vira um hash).

Em dia sem expediente (fim de semana ou feriado) a previsão devolve `aberta: false` e zero nos três turnos. Para data futura sem previsão do tempo informada, o modelo usa a média de clima do mês.

## Front (React)

Rotas: `/` login, `/cadastro` nova conta, `/triagem` chat de pré-triagem, `/turno` turno sugerido e confirmação, `/painel` painel da gestora (só perfil `gestora`). O token fica em `sessionStorage` e some ao fechar a aba. O cidadão escolhe a unidade no topo do chat; a escolha vale para a previsão e o registro. Protótipos das telas: canvas "Fila Zero UBS — Protótipos" no Claude.

A espera estimada por turno e a capacidade da equipe (4 / 3 / 2 profissionais, 18 atendimentos cada) são constantes em `mvp/web/src/lib/api.js` até existir cadastro de equipe na API.

## Previsão de demanda

`ia/treinar.py` lê a camada gold, compara `RandomForestRegressor` e `GradientBoostingRegressor` em 30 dias de validação e mede o escolhido nos últimos 30 dias do histórico, que ele não viu. O resultado fica em `ia/modelo/metricas.json` e o gráfico previsto × real em `docs/previsto_x_real.png`.

Resultado atual (GradientBoosting, teste de 01 a 30/10/2026):

| Turno | MAE (pessoas) | Procura média | MAE em % da média | Meta < 15% | MAE da linha de base |
| --- | --- | --- | --- | --- | --- |
| Manhã | 6,57 | 54,2 | 12,1% | sim | 9,88 |
| Tarde | 5,55 | 39,8 | 13,9% | sim | 7,83 |
| Noite | 4,01 | 17,1 | 23,5% | não | 3,99 |

A linha de base é prever a média móvel dos 7 dias anteriores. A noite não bate a meta: com cerca de 17 pessoas por turno, errar 3 ou 4 já passa de 15%.

O arquivo `ia/modelo/previsao_demanda.pkl` só abre com as versões de scikit-learn e numpy fixadas em `mvp/api/requirements.txt`. Se mudar uma delas, rode o treino de novo.

## Pré-triagem medida

`python ia/avaliar_triagem.py` compara a triagem com dois gabaritos de 30 relatos (10 por cor), em `ia/avaliacao/`. Os relatos e os rótulos foram escritos com ajuda de IA e **revisados pelo grupo em 14/11**, sem mudança de rótulo. Não passaram por um profissional de saúde. O resultado sai em `ia/modelo/metricas_triagem.json`.

| Medição das regras | Acurácia | Vermelho detectado | Vermelho como verde |
| --- | --- | --- | --- |
| Gabarito de ajuste, primeira medição | 63,3% | 2 de 10 | 6 |
| Gabarito de validação, às cegas | 53,3% | 0 de 10 | 8 |
| Gabarito de validação, depois da mudança abaixo (não é mais às cegas) | 56,7% | 0 de 10 | 1 |

Depois da medição às cegas, relato que as regras não reconhecem passou a sair amarelo, e não verde. Isso reduziu de 8 para 1 o vermelho classificado como verde, ao custo de 3 rotinas subirem para amarelo. **As regras continuam sem reconhecer como vermelho emergências descritas com outras palavras**. A triagem só orienta e não substitui o enfermeiro. Para medir o agente com LLM: `python ia/avaliar_triagem.py --llm`, que exige `ANTHROPIC_API_KEY` e tem custo.

Com a chave definida, o relato do cidadão é enviado à API da Anthropic. Em uso real, isso exige base legal e aviso conforme a LGPD. O modelo pode subir a cor dada pelas regras, nunca baixar.

## Ganho simulado

`python ia/simular_ganho.py` sorteia 100 cidadãos a partir das chegadas do dia de maior procura do histórico (06/04/2026, UBS Jardim Esperanca), com 500 rodadas, a mesma equipe e atendimento médio de 14 min. O resultado fica em `ia/modelo/ganho_simulado.json`.

| Cenário | Espera média |
| --- | --- |
| Antes: fila por ordem de chegada | 67,9 min |
| Depois, 100% seguem o turno sugerido | 5,8 min (−91,4%) |
| Depois, 70% seguem | 16,7 min (−75,4%) |
| Depois, 50% seguem | 28,2 min (−58,5%) |

É simulação sobre dados sintéticos, sem medir efeito em UBS real. A espera de quem segue o turno ainda depende de a procura caber na capacidade estimada da equipe.

## Data lake

| Camada | Conteúdo |
| --- | --- |
| `bigdata/lake/bronze/` | CSV como chega: `atendimentos_YYYY-MM.csv`, `clima_diario.csv`, `feriados.csv`, `lotacao_YYYY-MM.csv` (sensor) |
| `bigdata/lake/silver/` | Parquet limpo e tipado: `atendimentos`, `clima`, `lotacao` |
| `bigdata/lake/gold/` | Modelo estrela em Parquet: `fato_atendimento`, `fato_lotacao`, `dim_data`, `dim_turno`, `dim_ubs`, `dim_feriado` e `fato_previsao` (gravada pelo treino) |
| `bigdata/lake/rejeitados/` | Linhas que falharam na validação, com a coluna `motivo_rejeicao` |

O pipeline rejeita linha sem data, data ou hora inválida, espera negativa, atendimento antes da chegada, cor ou turno desconhecidos e id repetido. Cor da triagem é padronizada e turno ausente é derivado da hora de chegada.

O previsto × real fica em `fato_previsao` (uma linha por data, UBS e turno), e não em uma coluna `previsto_turno` de `fato_atendimento`, porque a previsão é por turno e não por pessoa.

## Dataset sintético

`data/gerar_dataset.py` simula 12 meses (01/11/2025 a 31/10/2026) de duas UBS fictícias com fila por ordem de chegada, que é o cenário "antes" da solução. A semente é fixa (`--seed 42`), então rodar de novo gera os mesmos arquivos. O gerador também produz as leituras do sensor da sala a cada 10 min (`lotacao_YYYY-MM.csv`), derivadas de quem já chegou e ainda não foi atendido, com 30 e 20 cadeiras por UBS.

Sazonalidade embutida: mais procura na segunda-feira, nos meses de dengue (fevereiro a maio), no inverno, em semanas de chuva e no dia útil seguinte a um feriado. A UBS não abre em fim de semana nem em feriado nacional. O cidadão é identificado por um hash de um número fictício; não existe CPF em nenhuma etapa.

## Estrutura

```
fila-zero-ubs/
├── docker-compose.yml      # api + db + mqtt + front + pipeline + treino + dashboard
├── .github/workflows/ci.yml
├── data/                   # gerador do dataset sintético
├── ia/                     # treinar.py, previsao.py, notebook, modelo/, prompts/
├── bigdata/                # lake/, pipeline.py, dashboard/
├── mvp/
│   ├── api/                # FastAPI
│   └── web/                # React (Vite)
├── iot/                    # sensor_sala/ (ESP32, Wokwi), mock_sensor.py, coletor.py, Mosquitto
├── tests/
└── docs/                   # PDF, prints, diagrama, roteiro das entrevistas
```

## Uso de IA generativa

| Ferramenta | Para quê |
| --- | --- |
| Claude (Anthropic) | Plano do projeto; estrutura do repositório; gerador do dataset sintético; pipeline do lake; treino e notebook do modelo de previsão; API; dashboard; protótipos e telas do front; sketch do ESP32, mock e coletor do sensor; testes; gabaritos da triagem (revisados pelo grupo em 14/11) e simulação de ganho |
| Claude API (`claude-opus-5-5`) | Agente de pré-triagem em execução, opcional, com `ANTHROPIC_API_KEY` |

Atualizar esta tabela a cada uso novo.

## Vídeo pitch

Link: https://youtu.be/yPdTLDpqZZw

## Equipe

Grupo: **Turno Certo**

| Nome | RM | Área |
| --- | --- | --- |
| Sarah Ribeiro da Silva | 97747 | |
| Alairton Rocha Scabelli | 551454 | |
| Eduardo Marins | 551892 | |
| Mateus Iago Sousa Conceição | 550270 | |
| Leonardo Nicastro Mansur Castillo | 551659 | |
