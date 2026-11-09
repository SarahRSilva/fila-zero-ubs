# IoT: sensor de lotação da sala de espera

Um ESP32 na porta da sala de espera conta quem entra e quem sai e publica a ocupação por MQTT a cada 30 s. A API consome o tópico para o painel da gestora; o coletor grava as leituras no lake para o dashboard.

```
ESP32 (Wokwi)  ──MQTT──▶  Mosquitto  ──▶  API (leitura_sala, GET /sala/agora)  ──▶  painel da gestora
                              └────────▶  iot/coletor.py  ──▶  bronze/lotacao_YYYY-MM.csv  ──▶  fato_lotacao  ──▶  dashboard
```

## Mensagem

Tópico `filazero/ubs/<id_ubs>/sala`, um JSON por leitura:

```json
{"ubs": "UBS Jardim Esperanca", "ocupacao": 18, "capacidade": 30, "temperatura": 27.5,
 "entradas": 42, "saidas": 24, "alerta": false, "origem": "esp32", "ts": "2026-11-09T07:40:00Z"}
```

`alerta` acende quando a ocupação passa de 90% da capacidade. `ts` é opcional: sem ele, quem recebe usa a hora de chegada.

## Montagem no Wokwi

Pasta `sensor_sala/`: abra `diagram.json` e `sensor_sala.ino` em um projeto ESP32 no [wokwi.com](https://wokwi.com).

| Peça | Pino | Função |
| --- | --- | --- |
| HC-SR04 (porta, lado de dentro) | TRIG 5, ECHO 18 | detecta passagem perto da porta |
| HC-SR04 (porta, lado de fora) | TRIG 19, ECHO 21 | a ordem em que os dois disparam diz se foi entrada ou saída |
| DHT22 | DATA 4 | temperatura da sala |
| LED vermelho | 2 | acende no alerta de lotação |
| Botão | 15 | zera a contagem (início do turno) |

No simulador, mova o cursor dos sensores de distância para abaixo de 60 cm, primeiro no de fora e depois no de dentro, para simular uma entrada; o contrário é uma saída.

O Wokwi não enxerga o Mosquitto da sua máquina, então o sketch publica em `broker.hivemq.com`. Para a demo local, rode o mock, que publica no Mosquitto do `docker compose`.

## Mock (sem placa)

```bash
python iot/mock_sensor.py                       # 1 UBS, uma leitura a cada 5 s, no Mosquitto local
python iot/mock_sensor.py --todas --intervalo 2 # as duas UBS
```

Ele simula a manhã de fila: a sala enche entre 6h e 8h e esvazia ao longo do turno.

## Coletor (lake)

```bash
python iot/coletor.py   # assina o tópico e grava bigdata/lake/bronze/lotacao_YYYY-MM.csv
```

Depois, `python bigdata/pipeline.py` leva as leituras para `fato_lotacao` no gold.
