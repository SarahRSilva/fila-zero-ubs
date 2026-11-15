# Formulário online da pesquisa (Google Forms)

Versão online do [roteiro](roteiro.md), para quem não dá para entrevistar ao vivo. **Link publicado: https://forms.gle/4ejiBVw3jsmzjWex6** (criado com [`criar_formulario.gs`](criar_formulario.gs)). Leva uns 4 minutos. As perguntas seguem as colunas de [`respostas.csv`](respostas.csv): exporte as respostas do Forms para o Planilhas e copie para o CSV, com `entrevistador` = `formulario` e códigos E1, E2… (F1… para funcionário).

## Como montar

1. Em forms.google.com, crie um formulário em branco.
2. Em **Configurações → Respostas**, deixe **"Coletar endereços de e-mail" desligado** e **não exija login**. A pesquisa é anônima.
3. Crie as seções abaixo. Em cada pergunta, o tipo está entre colchetes. Marque como obrigatórias só as que têm (*).
4. Na pergunta 2 da Seção 1, use **"Ir para a seção com base na resposta"** para separar usuário e funcionário.
5. Na Seção 3, insira as imagens `docs/prints/02-triagem-resultado.png` e `docs/prints/03-turno.png` com o botão de imagem.
6. Teste numa aba anônima antes de enviar.

## Título e descrição

**Título:** Fila na UBS: como é para você?

**Descrição:**
> Somos estudantes de Engenharia de Software da FIAP e estamos criando um projeto para diminuir a fila nas Unidades Básicas de Saúde (UBS). Leva uns 4 minutos. A pesquisa é anônima: não pedimos nome, e-mail nem dado que identifique você. As respostas são usadas só neste trabalho acadêmico. Você pode parar quando quiser.

## Seção 1: Participação

1. Você concorda em responder esta pesquisa anônima para um trabalho acadêmico? (*) [Múltipla escolha]
   - Sim, concordo → continuar
   - Não → enviar formulário
2. Qual frase descreve você? (*) [Múltipla escolha]
   - Fui atendido(a) em uma UBS nos últimos 12 meses → Seção 2
   - Trabalho ou trabalhei em uma UBS → Seção 5
   - Nenhuma das duas → enviar formulário

## Seção 2: Você e a UBS

3. Faixa de idade (*) [Múltipla escolha] — Até 29 · 30 a 59 · 60 ou mais
4. Com que frequência você vai à UBS? (*) [Múltipla escolha] — Uma vez por mês ou mais · Algumas vezes por ano · Uma vez por ano ou menos
5. Para que você costuma ir? [Caixas de seleção] — Consulta · Receita · Vacina · Curativo · Exame · Acompanhar filho ou outra pessoa · Outro
6. Na última vez que foi, **a que horas chegou**? [Horário]
7. E **a que horas foi atendido(a)**? [Horário] — descrição: "Se não foi atendido(a), deixe em branco."
8. Por que chegou nesse horário? [Resposta curta]
9. Nos últimos 3 meses, quantas vezes você foi à UBS e voltou sem atendimento? [Múltipla escolha] — Nenhuma · 1 · 2 · 3 ou mais
10. Você já desistiu de ir à UBS por causa da fila? [Múltipla escolha] — Não · Sim, fui à UPA ou pronto-socorro · Sim, fui à farmácia · Sim, fiquei sem atendimento · Outro
11. O que você perdeu para esperar na fila? [Caixas de seleção] — Horas ou dia de trabalho · Precisei de alguém para ficar com filhos ou parentes · Outro compromisso · Nada · Outro

## Seção 3: A ideia

Descrição da seção (com as duas imagens):
> Nossa ideia: você conta no celular o que está sentindo, o app diz se é caso de ir já (vermelho), o quanto antes (amarelo) ou de rotina (verde), e sugere o turno da UBS com menos fila. Ele não substitui o enfermeiro e não marca consulta: só sugere o melhor horário.

12. Você usaria um app assim? (*) [Múltipla escolha] — Sim · Talvez · Não
13. Por quê? [Resposta curta]
14. Se o app dissesse "vá às 18h, quase não tem fila", você iria nesse horário ou chegaria cedo mesmo assim? (*) [Múltipla escolha] — Iria no horário sugerido · Chegaria cedo mesmo assim · Depende
15. O que faria você **não** usar? [Caixas de seleção] — Não tenho celular ou internet boa · Não confio que o horário funcione · Acho difícil usar chat · Prefiro falar com uma pessoa · Nada me impediria · Outro
16. Tem algo que o app deveria fazer e não faz? [Parágrafo]

## Seção 4: Em uma frase

17. Se tivesse que contar para alguém, em uma frase, como é a fila da sua UBS, o que diria? [Parágrafo] — descrição: "Pode ser do seu jeito. Algumas frases podem aparecer, sem identificação, na apresentação do projeto."

→ Depois desta seção: enviar formulário.

## Seção 5: Para quem trabalha em UBS

18. Qual é ou era a sua função? [Múltipla escolha] — Recepção · Enfermagem · Agente comunitário de saúde · Medicina · Gestão · Outro
19. Há quanto tempo trabalha ou trabalhou em UBS? [Múltipla escolha] — Menos de 1 ano · 1 a 5 anos · Mais de 5 anos
20. Como funciona a distribuição de vagas ou senhas? A que horas começa a fila? [Parágrafo]
21. Num dia cheio, quantas pessoas ficam sem atendimento, mais ou menos? Em que dias ou meses piora? [Parágrafo]
22. Se vocês soubessem **no dia anterior** quantas pessoas vão vir em cada turno, o que mudariam? [Parágrafo]
23. Ver num painel quem já avisou que vem, com a cor da pré-triagem, ajudaria a recepção? [Múltipla escolha] — Ajudaria · Ajudaria pouco · Atrapalharia · Não sei
24. Uma pré-triagem por chat que **não substitui** a classificação de risco do enfermeiro ajudaria ou atrapalharia? Por quê? [Parágrafo]
25. O que deixaria vocês desconfiados de um sistema assim? [Parágrafo]

## Mensagem de confirmação

> Obrigado! Suas respostas ajudam a desenhar uma UBS com menos fila de madrugada.

## Cuidados

- Respostas pela internet tendem a vir de quem usa celular e redes sociais. Diga isso no PDF e no pitch, por exemplo: "amostra de N pessoas que responderam um formulário online".
- Para o diferencial "validado com gente real", tente ao menos 1 conversa ao vivo, de preferência com alguém que trabalha em UBS, usando o roteiro.
- Não arredonde para porcentagem quando a amostra for pequena: "7 de 12 pessoas", não "58%".
